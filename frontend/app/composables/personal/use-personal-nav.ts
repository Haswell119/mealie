import {
  mdiAccountGroup,
  mdiCartArrowDown,
  mdiFridgeOutline,
  mdiHomeVariantOutline,
  mdiLightbulbOnOutline,
  mdiPartyPopper,
  mdiRobotOutline,
  mdiShieldCheckOutline,
  mdiSilverwareForkKnife,
} from "@mdi/js";
import type { SideBarLink } from "~/types/application-types";

export const personalIcons = {
  hub: mdiHomeVariantOutline,
  people: mdiAccountGroup,
  events: mdiPartyPopper,
  pantry: mdiFridgeOutline,
  shopping: mdiCartArrowDown,
  inspirations: mdiLightbulbOnOutline,
  assistant: mdiRobotOutline,
  dietary: mdiShieldCheckOutline,
};

/** The first entry of the sidebar: the home page of the personal edition. */
export function usePersonalTopLinks() {
  const i18n = useI18n();

  return computed<SideBarLink[]>(() => [
    { icon: personalIcons.hub, to: "/hub", title: i18n.t("personal.nav.hub"), restricted: true },
  ]);
}

/**
 * The sidebar entries of the personal edition, in the order a person uses them. They follow the native
 * shopping lists: first what belongs to shopping, then what belongs to hosting, then ideas and the assistant.
 */
export function usePersonalSidebarLinks() {
  const i18n = useI18n();

  return computed<SideBarLink[]>(() => [
    { icon: personalIcons.shopping, to: "/shopping-plans", title: i18n.t("personal.nav.shopping-plans"), restricted: true },
    { icon: personalIcons.pantry, to: "/pantry", title: i18n.t("personal.nav.pantry"), restricted: true },
    { icon: personalIcons.events, to: "/events", title: i18n.t("personal.nav.events"), restricted: true },
    { icon: personalIcons.people, to: "/people", title: i18n.t("personal.nav.people"), restricted: true },
    { icon: personalIcons.dietary, to: "/dietary", title: i18n.t("personal.nav.dietary"), restricted: true },
    { icon: personalIcons.inspirations, to: "/inspirations", title: i18n.t("personal.nav.inspirations"), restricted: true },
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

export interface PersonalQuickAction {
  key: string;
  icon: string;
  title: string;
  subtitle: string;
  to: string;
  primary?: boolean;
}

/** The actions a person starts most often. The home page and the "+" button of the tab bar share them. */
export function usePersonalQuickActions() {
  const i18n = useI18n();
  const auth = useMealieAuth();
  const groupSlug = computed(() => auth.user.value?.groupSlug || "");

  return computed<PersonalQuickAction[]>(() => [
    {
      key: "recipe",
      icon: mdiSilverwareForkKnife,
      title: i18n.t("personal.nav.add-recipe"),
      subtitle: i18n.t("personal.nav.add-recipe-subtitle"),
      to: `/g/${groupSlug.value}/r/create/url`,
      primary: true,
    },
    {
      key: "event",
      icon: personalIcons.events,
      title: i18n.t("personal.nav.plan-a-meal"),
      subtitle: i18n.t("personal.nav.plan-a-meal-subtitle"),
      to: "/events?create=1",
    },
    {
      key: "shopping",
      icon: personalIcons.shopping,
      title: i18n.t("personal.nav.generate-shopping"),
      subtitle: i18n.t("personal.nav.generate-shopping-subtitle"),
      to: "/shopping-plans?create=1",
    },
  ]);
}
