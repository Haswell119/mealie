import { describe, expect, test } from "vitest";
import { personalLocaleFor } from "../personal-locale";

describe("language of the texts of the personal edition", () => {
  const available = ["en-US", "fr-FR"];

  test("a language with its own texts keeps them", () => {
    expect(personalLocaleFor("fr-FR", available)).toBe("fr-FR");
    expect(personalLocaleFor("en-US", available)).toBe("en-US");
  });

  test("a regional language takes the texts of the same language", () => {
    expect(personalLocaleFor("fr-BE", available)).toBe("fr-FR");
    expect(personalLocaleFor("fr-CA", available)).toBe("fr-FR");
    expect(personalLocaleFor("fr", available)).toBe("fr-FR");
    expect(personalLocaleFor("en-GB", available)).toBe("en-US");
  });

  test("a language without texts falls back to English", () => {
    expect(personalLocaleFor("de-DE", available)).toBe("en-US");
    expect(personalLocaleFor("", available)).toBe("en-US");
  });
});
