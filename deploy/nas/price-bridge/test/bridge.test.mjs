// Run with: node --test deploy/nas/price-bridge/test/
//
// The tests start the bridge with a stand-in price service (fake-mcp.mjs). They never start the real one.

import assert from "node:assert/strict";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";

process.env.BRIDGE_CALL_TIMEOUT_MS = "400";

const { createBridge, toBridgeAnswer } = await import("../bridge.mjs");

const fake = join(dirname(fileURLToPath(import.meta.url)), "fake-mcp.mjs");
let server;
let base;

before(async () => {
  server = createBridge([process.execPath, fake]);
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
});

async function call(path, body, method = "POST") {
  const response = await fetch(`${base}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: method === "POST" ? (typeof body === "string" ? body : JSON.stringify(body)) : undefined,
  });
  return { status: response.status, body: await response.json() };
}

test("health does not need the price service", async () => {
  assert.deepEqual(await call("/health", null, "GET"), { status: 200, body: { ok: true } });
});

test("a search passes the arguments on and returns the answer of the tool", async () => {
  const { status, body } = await call("/tools/search_products", { query: "spaghetti", chains: ["migros", "coop"], limit: 8 });
  assert.equal(status, 200);
  assert.equal(body.ok, true);
  assert.equal(body.result.byChain.migros[0].name, "Spaghetti");
  assert.deepEqual(body.result.errors, [{ chain: "lidl", message: "blocked" }]);
  assert.deepEqual(body.result.echo, { query: "spaghetti", chains: ["migros", "coop"], limit: 8 });
});

test("a structured answer wins over the text", async () => {
  const { body } = await call("/tools/get_product", { chain: "migros", id: "100" });
  assert.equal(body.ok, true);
  assert.equal(body.result.product.price.current, 1.5);
});

test("a product that the shop no longer lists is not found", async () => {
  const { status, body } = await call("/tools/get_product", { chain: "migros", id: "404" });
  assert.deepEqual({ status, body }, { status: 200, body: { ok: false, error: "not_found" } });
});

test("only the listed tools can be called", async () => {
  for (const path of ["/tools/delete_everything", "/tools/../health", "/tools/", "/other"]) {
    const { status, body } = await call(path, {});
    assert.equal(status, 404, path);
    assert.deepEqual(body, { ok: false, error: "unknown_tool" });
  }
  assert.equal((await call("/tools/search_products", null, "GET")).status, 404);
});

test("a body that is not a JSON object is refused", async () => {
  for (const body of ["{", "[1]", "null", "\"text\""]) {
    const answer = await call("/tools/search_products", body);
    assert.deepEqual(answer, { status: 400, body: { ok: false, error: "bad_request" } }, body);
  }
  const large = await fetch(`${base}/tools/search_products`, { method: "POST", body: JSON.stringify({ query: "x".repeat(20000) }) })
    .then(response => response.status)
    .catch(() => "closed");
  assert.ok(large === 400 || large === "closed");
});

test("an answer that is not JSON is an error, not a result", async () => {
  const { body } = await call("/tools/search_products", { query: "garbage" });
  assert.deepEqual(body, { ok: false, error: "bad_answer" });
});

test("a tool that does not answer times out", async () => {
  const { status, body } = await call("/tools/search_products", { query: "slow" });
  assert.deepEqual({ status, body }, { status: 200, body: { ok: false, error: "timeout" } });
});

test("the price service starts again after it stops", async () => {
  const crashed = await call("/tools/search_products", { query: "crash" });
  assert.deepEqual(crashed.body, { ok: false, error: "unavailable" });
  const again = await call("/tools/search_products", { query: "spaghetti" });
  assert.equal(again.body.ok, true);
});

test("the answer of a tool is read without trusting its shape", () => {
  assert.deepEqual(toBridgeAnswer(undefined), { ok: false, error: "bad_answer" });
  assert.deepEqual(toBridgeAnswer({ content: [] }), { ok: false, error: "bad_answer" });
  assert.deepEqual(toBridgeAnswer({ content: [{ type: "text", text: "null" }] }), { ok: false, error: "not_found" });
  assert.deepEqual(toBridgeAnswer({ content: [{ type: "text", text: "boom" }], isError: true }), { ok: false, error: "tool_error" });
  assert.deepEqual(toBridgeAnswer({ content: [{ type: "image" }, { type: "text", text: "{\"a\":1}" }] }), { ok: true, result: { a: 1 } });
});
