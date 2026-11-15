<template>
  <div v-if="visible">
    <nav
      class="pe-tabbar d-print-none"
      :aria-label="$t('personal.nav.main-navigation')"
      data-testid="personal-tabbar"
    >
      <NuxtLink
        v-for="item in leftItems"
        :key="item.to"
        :to="item.to"
        class="pe-tabbar__item"
        :class="{ 'pe-tabbar__item--active': isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
      >
        <v-icon
          :icon="item.icon"
          size="24"
        />
        <span>{{ item.title }}</span>
      </NuxtLink>

      <button
        type="button"
        class="pe-tabbar__add"
        :aria-label="$t('personal.nav.quick-actions-open')"
        data-testid="personal-tabbar-add"
        @click="sheet = true"
      >
        <v-icon
          :icon="mdiPlus"
          size="30"
        />
      </button>

      <NuxtLink
        v-for="item in rightItems"
        :key="item.to"
        :to="item.to"
        class="pe-tabbar__item"
        :class="{ 'pe-tabbar__item--active': isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
      >
        <v-icon
          :icon="item.icon"
          size="24"
        />
        <span>{{ item.title }}</span>
      </NuxtLink>
    </nav>

    <v-bottom-sheet v-model="sheet">
      <v-card data-testid="personal-quick-actions">
        <v-card-title class="pt-5 px-5">
          {{ $t('personal.nav.quick-actions') }}
        </v-card-title>
        <v-list
          lines="two"
          class="pb-4"
        >
          <v-list-item
            v-for="action in actions"
            :key="action.key"
            :to="action.to"
            :title="action.title"
            :subtitle="action.subtitle"
            @click="sheet = false"
          >
            <template #prepend>
              <span class="pe-tile__icon mr-4">
                <v-icon :icon="action.icon" />
              </span>
            </template>
          </v-list-item>
        </v-list>
      </v-card>
    </v-bottom-sheet>
  </div>
</template>

<script setup lang="ts">
import { mdiFormatListChecks, mdiFridgeOutline, mdiLightbulbOnOutline, mdiPlus, mdiSilverwareForkKnife } from "@mdi/js";
import { personalIcons, usePersonalQuickActions } from "~/composables/personal/use-personal-nav";

interface TabItem {
  to: string;
  icon: string;
  title: string;
  match: string[];
}

const i18n = useI18n();
const route = useRoute();
const display = useDisplay();
const auth = useMealieAuth();

const sheet = ref(false);
const groupSlug = computed(() => auth.user.value?.groupSlug || "");
const visible = computed(() => auth.loggedIn.value && display.smAndDown.value && !!groupSlug.value);

const leftItems = computed<TabItem[]>(() => [
  { to: "/hub", icon: personalIcons.hub, title: i18n.t("personal.nav.tab-home"), match: ["/hub"] },
  {
    to: `/g/${groupSlug.value}`,
    icon: mdiSilverwareForkKnife,
    title: i18n.t("personal.nav.tab-recipes"),
    match: [`/g/${groupSlug.value}`, "/inspirations"],
  },
]);

const rightItems = computed<TabItem[]>(() => [
  {
    to: "/shopping-lists",
    icon: mdiFormatListChecks,
    title: i18n.t("personal.nav.tab-shopping"),
    match: ["/shopping-lists", "/shopping-plans", "/pantry"],
  },
  {
    to: "/events",
    icon: personalIcons.events,
    title: i18n.t("personal.nav.tab-events"),
    match: ["/events", "/people", "/dietary"],
  },
]);

function isActive(item: TabItem): boolean {
  return item.match.some(prefix => route.path === prefix || route.path.startsWith(`${prefix}/`));
}

const quickActions = usePersonalQuickActions();
const actions = computed(() => [
  ...quickActions.value,
  {
    key: "stock",
    icon: mdiFridgeOutline,
    title: i18n.t("personal.nav.add-stock"),
    subtitle: i18n.t("personal.nav.add-stock-subtitle"),
    to: "/pantry",
  },
  {
    key: "inspiration",
    icon: mdiLightbulbOnOutline,
    title: i18n.t("personal.nav.new-inspiration"),
    subtitle: i18n.t("personal.nav.new-inspiration-subtitle"),
    to: "/inspirations",
  },
]);

// The stylesheet reads this class to leave room under the content for the floating bar.
watchEffect(() => {
  if (import.meta.client) {
    document.documentElement.classList.toggle("pe-has-tabbar", visible.value);
  }
});

onBeforeUnmount(() => {
  if (import.meta.client) {
    document.documentElement.classList.remove("pe-has-tabbar");
  }
});

watch(() => route.fullPath, () => (sheet.value = false));
</script>
