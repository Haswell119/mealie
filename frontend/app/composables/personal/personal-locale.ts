/**
 * The language of the texts of the personal edition for a language of Mealie.
 *
 * Mealie has many regional languages (fr-FR, fr-BE, fr-CA…); the personal edition has fewer. A regional
 * language without its own texts takes the texts of the same language from another region, and only
 * then English: a person who reads French in Mealie reads French here too.
 */
export function personalLocaleFor(locale: string, available: Iterable<string>, fallback = "en-US"): string {
  const codes = [...available];
  if (codes.includes(locale)) {
    return locale;
  }
  const language = locale.split("-")[0]?.toLowerCase();
  return codes.find(code => code.split("-")[0]?.toLowerCase() === language) ?? fallback;
}
