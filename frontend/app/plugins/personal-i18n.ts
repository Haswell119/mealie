/**
 * Adds the texts of the personal edition to the translations of Mealie.
 *
 * The texts live in their own files, so that the translation files that Crowdin rewrites stay untouched.
 * Every text sits under the `personal` key. A language without its own files falls back to English.
 */
const files = import.meta.glob<Record<string, unknown>>("../lang/personal/*/*.json", { eager: true, import: "default" });

function messagesFor(locale: string): Record<string, unknown> {
  const messages: Record<string, unknown> = {};
  for (const [path, content] of Object.entries(files)) {
    const [, fileLocale, section] = path.match(/personal\/([^/]+)\/([^/]+)\.json$/) || [];
    if (fileLocale === locale && section) {
      messages[section] = content;
    }
  }
  return messages;
}

export default defineNuxtPlugin((nuxtApp) => {
  const i18n = nuxtApp.$i18n as any;
  const available = new Set(Object.keys(files).map(path => path.match(/personal\/([^/]+)\//)?.[1]));

  function merge(locale: string) {
    const source = available.has(locale) ? locale : "en-US";
    i18n.mergeLocaleMessage(locale, { personal: messagesFor(source) });
  }

  merge("en-US");
  merge(unref(i18n.locale));
  nuxtApp.hook("i18n:localeSwitched", ({ newLocale }: { newLocale: string }) => merge(newLocale));
});
