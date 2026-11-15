// A stand-in for the price service, for the tests of the bridge. It speaks MCP over standard input and output.
// It reads no shop: every answer is written below.

import { createInterface } from "node:readline";

const product = {
  chain: "migros",
  id: "100",
  name: "Spaghetti",
  brand: "M-Classic",
  size: { value: 500, unit: "g" },
  price: { current: 1.5, regular: 1.9 },
  unitPrice: { value: 3, per: "kg" },
  tags: ["pasta"],
  productUrl: "https://example.org/p/100",
};

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function text(value, isError = false) {
  return { content: [{ type: "text", text: typeof value === "string" ? value : JSON.stringify(value) }], isError };
}

function call(name, args) {
  if (name === "search_products") {
    if (args.query === "slow") {
      return null; // never answers
    }
    if (args.query === "garbage") {
      return text("this is not JSON");
    }
    if (args.query === "crash") {
      process.exit(3);
    }
    return text({ byChain: { migros: [product], coop: [] }, errors: [{ chain: "lidl", message: "blocked" }], echo: args });
  }
  if (name === "get_product") {
    if (args.id === "100") {
      return { content: [{ type: "text", text: "ignored" }], structuredContent: { product } };
    }
    return text("Product not found", true);
  }
  return text(`Unknown tool ${name}`, true);
}

process.stdout.write("a log line that is not JSON\n");

createInterface({ input: process.stdin }).on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    send({
      jsonrpc: "2.0",
      id: message.id,
      result: { protocolVersion: message.params.protocolVersion, capabilities: { tools: {} }, serverInfo: { name: "fake", version: "0" } },
    });
  }
  else if (message.method === "tools/call") {
    const result = call(message.params.name, message.params.arguments || {});
    if (result) {
      send({ jsonrpc: "2.0", id: message.id, result });
    }
  }
});
