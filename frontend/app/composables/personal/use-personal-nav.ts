import {
  mdiAccountGroup,
  mdiCartArrowDown,
  mdiFridgeOutline,
  mdiLightbulbOnOutline,
  mdiPartyPopper,
  mdiRobotOutline,
  mdiShieldCheckOutline,
} from "@mdi/js";
import type { SideBarLink } from "~/types/application-types";

export const personalIcons = {
  people: mdiAccountGroup,
  events: mdiPartyPopper,
  pantry: mdiFridgeOutline,
  shopping: mdiCartArrowDown,
  inspirations: mdiLightbulbOnOutline,
  assistant: mdiRobotOutline,
  dietary: mdiShieldCheckOutline,
};

/** The sidebar entries of the personal edition. */
export function usePersonalSidebarLinks() {
  const i18n = useI18n();

  return computed<SideBarLink[]>(() => [
    { icon: personalIcons.inspirations, to: "/inspirations", title: i18n.t("personal.nav.inspirations"), restricted: true },
    { icon: personalIcons.events, to: "/events", title: i18n.t("personal.nav.events"), restricted: true },
    { icon: personalIcons.people, to: "/people", title: i18n.t("personal.nav.people"), restricted: true },
    { icon: personalIcons.shopping, to: "/shopping-plans", title: i18n.t("personal.nav.shopping-plans"), restricted: true },
    { icon: personalIcons.pantry, to: "/pantry", title: i18n.t("personal.nav.pantry"), restricted: true },
    { icon: personalIcons.dietary, to: "/dietary", title: i18n.t("personal.nav.dietary"), restricted: true },
    { icon: personalIcons.assistant, to: "/assistant", title: i18n.t("personal.nav.assistant"), restricted: true },
  ]);
}

/** The entries that the personal edition adds to the "create" menu. */
export function usePersonalCreateLinks() {
  const i18n = useI18n();

  return computed(() => [
    {
      insertDivider: true,
      icon: personalIcons.events,
      title: i18n.t("personal.nav.plan-a-meal"),
      subtitle: i18n.t("personal.nav.plan-a-meal-subtitle"),
      to: "/events?create=1",
      restricted: true,
      hide: false,
    },
    {
      insertDivider: false,
      icon: personalIcons.shopping,
      title: i18n.t("personal.nav.generate-shopping"),
      subtitle: i18n.t("personal.nav.generate-shopping-subtitle"),
      to: "/shopping-plans?create=1",
      restricted: true,
      hide: false,
    },
  ]);
}
