// Price bridge of Mealie Personal Edition.
//
// The price service is an MCP server that talks over standard input and output. Mealie talks HTTP.
// This file stands between the two: it starts the MCP server as a child process and answers
//
//   POST /tools/<name>   body: the arguments of the tool, as JSON
//   GET  /health
//
// with `{"ok": true, "result": ...}` or `{"ok": false, "error": "<code>"}`.
//
// Only the tools named in ALLOWED_TOOLS can be called. The bridge holds no secret and stores nothing.
// It has no dependency: only the standard library of Node.js.

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, join, resolve } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.BRIDGE_PORT || 8080);
const HOST = process.env.BRIDGE_HOST || "0.0.0.0";
const CALL_TIMEOUT_MS = Number(process.env.BRIDGE_CALL_TIMEOUT_MS || 20000);
const START_TIMEOUT_MS = Number(process.env.BRIDGE_START_TIMEOUT_MS || 15000);
const MAX_BODY_BYTES = 16 * 1024;
const MAX_LINE_BYTES = 8 * 1024 * 1024;
const PACKAGE = process.env.BRIDGE_PACKAGE || "@nicktcode/swissgroceries-mcp";
const ALLOWED_TOOLS = new Set(
  (process.env.BRIDGE_TOOLS || "search_products,get_product")
    .split(",")
    .map(name => name.trim())
    .filter(Boolean),
);
const PROTOCOL_VERSION = "2025-06-18";

function log(message) {
  process.stderr.write(`[price-bridge] ${message}\n`);
}

/** The command that starts the MCP server: BRIDGE_COMMAND (a JSON array), or else the program of the package. */
function serverCommand() {
  if (process.env.BRIDGE_COMMAND) {
    const command = JSON.parse(process.env.BRIDGE_COMMAND);
    if (!Array.isArray(command) || !command.length || !command.every(part => typeof part === "string")) {
      throw new Error("BRIDGE_COMMAND must be a JSON array of strings");
    }
    return command;
  }
  const root = join(here, "node_modules", ...PACKAGE.split("/"));
  const manifest = JSON.parse(readFileSync(join(root, "package.json"), "utf-8"));
  const bin = typeof manifest.bin === "string" ? manifest.bin : Object.values(manifest.bin || {})[0];
  const entry = bin || manifest.main;
  if (!entry) {
    throw new Error(`${PACKAGE} names no program to start`);
  }
  return [process.execPath, resolve(root, entry)];
}

/** One MCP server process, started when the first request comes and started again after it stops. */
class McpClient {
  constructor(command) {
    this.command = command;
    this.child = null;
    this.ready = null;
    this.nextId = 1;
    this.pending = new Map();
  }

  start() {
    if (this.ready) {
      return this.ready;
    }
    const [program, ...args] = this.command;
    const child = spawn(program, args, { stdio: ["pipe", "pipe", "inherit"], cwd: here });
    this.child = child;

    const lines = createInterface({ input: child.stdout, crlfDelay: Infinity });
    lines.on("line", line => this.receive(line));
    child.on("error", error => this.stop(child, `cannot start: ${error.message}`));
    child.on("exit", code => this.stop(child, `stopped with code ${code}`));
    child.stdin.on("error", () => {});

    this.ready = this.request(
      "initialize",
      { protocolVersion: PROTOCOL_VERSION, capabilities: {}, clientInfo: { name: "mealie-pe-price-bridge", version: "1.0.0" } },
      START_TIMEOUT_MS,
    ).then(() => {
      this.send({ jsonrpc: "2.0", method: "notifications/initialized" });
    });
    // A start that fails must not stay cached: the next request starts the server again.
    this.ready.catch(() => this.stop(child, "did not start"));
    return this.ready;
  }

  stop(child, reason) {
    if (this.child !== child) {
      return;
    }
    log(`price service ${reason}`);
    this.child = null;
    this.ready = null;
    for (const { reject, timer } of this.pending.values()) {
      clearTimeout(timer);
      reject(new Error("unavailable"));
    }
    this.pending.clear();
    child.kill();
  }

  send(message) {
    this.child?.stdin.write(`${JSON.stringify(message)}\n`);
  }

  receive(line) {
    if (!line.trim() || line.length > MAX_LINE_BYTES) {
      return;
    }
    let message;
    try {
      message = JSON.parse(line);
    }
    catch {
      return; // a line that is not JSON is a log line of the server
    }
    const waiting = this.pending.get(message.id);
    if (!waiting) {
      return;
    }
    this.pending.delete(message.id);
    clearTimeout(waiting.timer);
    if (message.error) {
      waiting.reject(new Error("rpc_error"));
    }
    else {
      waiting.resolve(message.result);
    }
  }

  request(method, params, timeoutMs = CALL_TIMEOUT_MS) {
    return new Promise((resolvePromise, reject) => {
      if (!this.child) {
        reject(new Error("unavailable"));
        return;
      }
      const id = this.nextId++;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("timeout"));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolvePromise, reject, timer });
      this.send({ jsonrpc: "2.0", id, method, params });
    });
  }

  async callTool(name, args) {
    await this.start();
    return await this.request("tools/call", { name, arguments: args });
  }
}

/** Turn the answer of a tool into the answer of the bridge. */
export function toBridgeAnswer(result) {
  const text = (result?.content || [])
    .filter(part => part?.type === "text" && typeof part.text === "string")
    .map(part => part.text)
    .join("\n");

  if (result?.isError) {
    return { ok: false, error: /not[\s_-]?found|no such|unknown product/i.test(text) ? "not_found" : "tool_error" };
  }
  if (result?.structuredContent && typeof result.structuredContent === "object") {
    return { ok: true, result: result.structuredContent };
  }
  try {
    const parsed = JSON.parse(text);
    return parsed === null ? { ok: false, error: "not_found" } : { ok: true, result: parsed };
  }
  catch {
    return { ok: false, error: "bad_answer" };
  }
}

function readBody(request) {
  return new Promise((resolvePromise, reject) => {
    const chunks = [];
    let size = 0;
    request.on("data", (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error("too_large"));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.on("end", () => resolvePromise(Buffer.concat(chunks).toString("utf-8")));
    request.on("error", reject);
  });
}

function reply(response, status, body) {
  const payload = JSON.stringify(body);
  response.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(payload) });
  response.end(payload);
}

export function createBridge(command = serverCommand()) {
  const client = new McpClient(command);

  const server = createServer(async (request, response) => {
    const path = (request.url || "").split("?")[0];
    if (request.method === "GET" && path === "/health") {
      reply(response, 200, { ok: true });
      return;
    }

    const tool = path.match(/^\/tools\/([a-z_]+)$/)?.[1];
    if (request.method !== "POST" || !tool || !ALLOWED_TOOLS.has(tool)) {
      reply(response, 404, { ok: false, error: "unknown_tool" });
      return;
    }

    let args;
    try {
      args = JSON.parse((await readBody(request)) || "{}");
    }
    catch {
      reply(response, 400, { ok: false, error: "bad_request" });
      return;
    }
    if (args === null || typeof args !== "object" || Array.isArray(args)) {
      reply(response, 400, { ok: false, error: "bad_request" });
      return;
    }

    try {
      reply(response, 200, toBridgeAnswer(await client.callTool(tool, args)));
    }
    catch (error) {
      log(`${tool} failed: ${error.message}`);
      reply(response, 200, { ok: false, error: error.message === "timeout" ? "timeout" : "unavailable" });
    }
  });

  server.on("close", () => {
    if (client.child) {
      client.stop(client.child, "stopped with the bridge");
    }
  });
  return server;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server = createBridge();
  server.listen(PORT, HOST, () => log(`listening on ${HOST}:${PORT}, tools: ${[...ALLOWED_TOOLS].join(", ")}`));
  for (const signal of ["SIGTERM", "SIGINT"]) {
    process.on(signal, () => server.close(() => process.exit(0)));
  }
}
