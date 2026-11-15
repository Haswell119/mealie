/**
 * Adds the texts of the personal edition to the translations of Mealie.
 *
 * The texts live in their own files, so that the translation files that Crowdin rewrites stay untouched.
 * Every text sits under the `personal` key. A language without its own files takes the files of the same
 * language from another region (fr-BE reads fr-FR), and only then English.
 */
import { personalLocaleFor } from "~/composables/personal/personal-locale";

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
  const available = new Set(
    Object.keys(files)
      .map(path => path.match(/personal\/([^/]+)\//)?.[1])
      .filter((code): code is string => !!code),
  );

  // Merging the same texts twice changes nothing, so every signal below may call this.
  function merge(locale: string) {
    if (locale) {
      i18n.mergeLocaleMessage(locale, { personal: messagesFor(personalLocaleFor(locale, available)) });
    }
  }

  merge("en-US");
  merge(unref(i18n.locale));
  // The language can change in two ways: a switch by the user, and the detection of the browser language
  // at start. The hook sees the first; the watch sees both.
  nuxtApp.hook("i18n:localeSwitched", ({ newLocale }: { newLocale: string }) => merge(newLocale));
  if (isRef(i18n.locale)) {
    watch(i18n.locale, value => merge(String(value)));
  }
});
