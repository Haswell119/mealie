import type { ChecklistItemOut, FindingOut, FoodRestrictionEffective } from "~/lib/api/types/personal";

/** Turns the codes that the server returns into sentences. */
export function usePersonalText() {
  const i18n = useI18n();

  function finding(item: Pick<FindingOut, "code" | "term" | "detail" | "personName">): string {
    if (item.code === "STORED" && !item.detail) {
      return i18n.t("personal.enums.finding.STORED_EMPTY");
    }
    return i18n.t(`personal.enums.finding.${item.code}`, {
      term: item.term ?? "",
      detail: item.detail ?? "",
      person: item.personName ?? "",
    });
  }

  function foodStatus(item: FoodRestrictionEffective): string {
    if (!item.code) {
      return "";
    }
    return finding({ code: item.code, term: item.term, detail: item.reason, personName: null });
  }

  function checklist(item: ChecklistItemOut): string {
    return i18n.t(`personal.enums.checklist.${item.code}`, { subject: item.subject });
  }

  function quantity(value: number | null | undefined): string {
    if (value === null || value === undefined) {
      return "";
    }
    return new Intl.NumberFormat(i18n.locale.value, { maximumFractionDigits: 3 }).format(value);
  }

  return { finding, foodStatus, checklist, quantity };
}
