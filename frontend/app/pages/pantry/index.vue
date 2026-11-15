<template>
  <v-container class="narrow-container pe-page">
    <PersonalPageHeader
      :icon="personalIcons.pantry"
      :title="$t('personal.pantry.title')"
      :subtitle="$t('personal.pantry.subtitle')"
    />

    <v-tabs
      v-model="tab"
      color="primary"
      grow
      show-arrows
      density="comfortable"
      class="mb-4"
    >
      <v-tab
        v-for="name in tabs"
        :key="name"
        :value="name"
        class="px-2"
        :data-testid="`pantry-tab-${name}`"
      >
        {{ $t(`personal.pantry.tabs.${name}`) }}
      </v-tab>
    </v-tabs>

    <v-tabs-window
      v-model="tab"
      :touch="false"
    >
      <v-tabs-window-item value="stock">
        <PantryStock />
      </v-tabs-window-item>
      <v-tabs-window-item value="packagings">
        <PantryPackagings ref="packagings" />
      </v-tabs-window-item>
      <v-tabs-window-item value="prices">
        <PantryPrices />
      </v-tabs-window-item>
      <v-tabs-window-item value="products">
        <PantryProducts @imported="packagings?.refresh()" />
      </v-tabs-window-item>
    </v-tabs-window>
  </v-container>
</template>

<script setup lang="ts">
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import PantryPackagings from "~/components/Domain/Pantry/PantryPackagings.vue";
import PantryPrices from "~/components/Domain/Pantry/PantryPrices.vue";
import PantryProducts from "~/components/Domain/Pantry/PantryProducts.vue";
import PantryStock from "~/components/Domain/Pantry/PantryStock.vue";
import { personalIcons } from "~/composables/personal/use-personal-nav";

definePageMeta({
  middleware: ["auth"],
});

const tabs = ["stock", "packagings", "prices", "products"] as const;
type PantryTab = (typeof tabs)[number];

const i18n = useI18n();
const route = useRoute();
const router = useRouter();

useSeoMeta({ title: i18n.t("personal.pantry.title") });

function tabFromQuery(): PantryTab {
  const value = route.query.tab;
  return tabs.find(name => name === value) ?? "stock";
}

const tab = ref<PantryTab>(tabFromQuery());
const packagings = ref<InstanceType<typeof PantryPackagings> | null>(null);

// The tab sits in the address, so a link or a reload opens the same section.
watch(tab, (value) => {
  if (value !== tabFromQuery()) {
    router.replace({ query: { ...route.query, tab: value === "stock" ? undefined : value } });
  }
});
</script>
