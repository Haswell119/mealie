import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const root = resolve(__dirname, "../../../lang/personal");
const reference = "fr-FR";

function keysOf(value: unknown, prefix = ""): string[] {
  if (value === null || typeof value !== "object") {
    return [prefix];
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    keysOf(child, prefix ? `${prefix}.${key}` : key),
  );
}

function load(locale: string, file: string): unknown {
  return JSON.parse(readFileSync(join(root, locale, file), "utf-8"));
}

describe("texts of the personal edition", () => {
  const locales = readdirSync(root);
  const files = readdirSync(join(root, reference)).sort();

  test("French is present and has every section", () => {
    expect(locales).toContain(reference);
    expect(files).toEqual(expect.arrayContaining(["common.json", "enums.json", "nav.json"]));
  });

  test.each(locales.filter(locale => locale !== reference))("%s has the same files as French", (locale) => {
    expect(readdirSync(join(root, locale)).sort()).toEqual(files);
  });

  for (const locale of locales.filter(locale => locale !== reference)) {
    test.each(files)(`${locale}/%s has the same keys as French`, (file) => {
      expect(keysOf(load(locale, file)).sort()).toEqual(keysOf(load(reference, file)).sort());
    });
  }

  test.each(files)("%s has no empty text", (file) => {
    for (const locale of locales) {
      const flat = JSON.stringify(load(locale, file));
      expect(flat).not.toMatch(/:""/);
    }
  });

  test("every status, scope and finding code of the API has a text", () => {
    const enums = load(reference, "enums.json") as Record<string, Record<string, string>>;
    expect(Object.keys(enums.status)).toEqual(["VERIFIED", "UNVERIFIED", "INCOMPATIBLE"]);
    expect(Object.keys(enums.scope)).toEqual(["INDIVIDUAL", "ENTIRE_MEAL", "ENTIRE_PREPARATION"]);

    const types = readFileSync(resolve(__dirname, "../../../lib/api/types/personal.ts"), "utf-8");
    const findingCodes = types.match(/export type FindingCode =([^;]+);/)?.[1].match(/"([A-Z_]+)"/g) ?? [];
    expect(findingCodes.length).toBeGreaterThan(5);
    for (const code of findingCodes) {
      expect(enums.finding, code).toHaveProperty(code.replaceAll("\"", ""));
    }
  });
});
