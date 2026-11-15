<template>
  <v-container class="narrow-container pe-page">
    <IdeaGenerateDialog
      v-model="generateDialog"
      @created="reload"
    />

    <PersonalPageHeader
      :icon="personalIcons.ideas"
      :title="$t('personal.ideas.title')"
      :subtitle="$t('personal.ideas.subtitle')"
    />

    <div
      v-if="feed"
      class="d-flex flex-wrap align-center ga-2 mb-3"
    >
      <v-btn
        v-if="feed.assistantEnabled"
        color="primary"
        variant="flat"
        :prepend-icon="personalIcons.assistant"
        data-testid="idea-generate"
        @click="generateDialog = true"
      >
        {{ $t('personal.ideas.generate.button') }}
      </v-btn>
      <span
        v-else
        class="text-body-small text-medium-emphasis flex-grow-1"
        data-testid="idea-assistant-disabled"
      >{{ $t('personal.ideas.generate.disabled') }}</span>
      <v-spacer v-if="feed.assistantEnabled" />
      <v-btn
        variant="text"
        :prepend-icon="mdiShuffleVariant"
        :disabled="loading"
        data-testid="idea-shuffle"
        @click="shuffle"
      >
        {{ $t('personal.ideas.shuffle') }}
      </v-btn>
    </div>

    <v-text-field
      v-model="search"
      :label="$t('personal.ideas.search')"
      :prepend-inner-icon="$globals.icons.search"
      density="compact"
      clearable
      hide-details
      maxlength="100"
      class="mb-3"
      data-testid="idea-search"
    />

    <v-chip-group
      v-model="selectedTags"
      multiple
      column
      selected-class="text-primary"
      :aria-label="$t('personal.ideas.filters-title')"
      data-testid="idea-filters"
    >
      <v-chip
        v-for="item in builtinFilters"
        :key="item.key"
        :value="item.key"
        filter
        variant="outlined"
        :data-testid="`idea-filter-${item.key}`"
      >
        {{ $t('personal.ideas.filter-count', { name: item.title, count: item.count }) }}
      </v-chip>
    </v-chip-group>

    <template v-if="labelFilters.length">
      <div class="text-body-small text-medium-emphasis mt-2">
        {{ $t('personal.ideas.labels-title') }}
      </div>
      <v-chip-group
        v-model="selectedTags"
        multiple
        column
        selected-class="text-primary"
        :aria-label="$t('personal.ideas.labels-title')"
        data-testid="idea-label-filters"
      >
        <v-chip
          v-for="item in labelFilters"
          :key="item.key"
          :value="item.key"
          filter
          size="small"
          variant="outlined"
        >
          {{ $t('personal.ideas.filter-count', { name: item.title, count: item.count }) }}
        </v-chip>
      </v-chip-group>
    </template>

    <v-row
      density="compact"
      class="mt-2"
    >
      <v-col
        v-if="restrictionItems.length"
        cols="12"
        :sm="showMaxCost ? 7 : 12"
      >
        <v-select
          v-model="restrictions"
          :items="restrictionItems"
          :label="$t('personal.ideas.restrictions')"
          :hint="$t('personal.ideas.restrictions-hint')"
          persistent-hint
          multiple
          chips
          closable-chips
          clearable
          density="compact"
          data-testid="idea-restrictions"
        />
      </v-col>
      <v-col
        v-if="showMaxCost"
        cols="12"
        :sm="restrictionItems.length ? 5 : 12"
      >
        <v-text-field
          v-model.number="maxCost"
          type="number"
          min="0"
          step="0.5"
          inputmode="decimal"
          :label="$t('personal.ideas.max-cost')"
          density="compact"
          clearable
          hide-details
          data-testid="idea-max-cost"
        />
      </v-col>
    </v-row>

    <v-progress-linear
      :active="loading"
      indeterminate
      color="primary"
      class="my-2"
    />

    <template v-if="feed">
      <div
        class="text-body-small text-medium-emphasis mb-1"
        data-testid="idea-checked-for"
      >
        {{ checkedFor }}
      </div>

      <div
        v-if="feed.hiddenIncompatible || includeIncompatible"
        class="d-flex flex-wrap align-center ga-2"
      >
        <span
          v-if="feed.hiddenIncompatible"
          class="text-body-small text-medium-emphasis"
          data-testid="idea-hidden"
        >{{ $t('personal.ideas.hidden-incompatible', { count: feed.hiddenIncompatible }, feed.hiddenIncompatible) }}</span>
        <v-switch
          v-model="includeIncompatible"
          color="error"
          density="compact"
          hide-details
          :label="$t('personal.ideas.show-incompatible')"
          data-testid="idea-show-incompatible"
        />
      </div>

      <div
        class="d-flex flex-wrap align-center ga-2 mt-2"
      >
        <span
          class="text-title-medium flex-grow-1"
          data-testid="idea-total"
        >{{ $t('personal.ideas.total', { count: feed.total }, feed.total) }}</span>
        <v-btn
          v-if="hasFilters"
          variant="text"
          size="small"
          data-testid="idea-clear"
          @click="clearFilters"
        >
          {{ $t('personal.ideas.clear-filters') }}
        </v-btn>
      </div>

      <v-alert
        v-if="!cards.length && !loading"
        type="info"
        variant="tonal"
        class="mt-2"
        data-testid="idea-empty"
      >
        {{ hasFilters ? $t('personal.ideas.empty-filtered') : $t('personal.ideas.empty') }}
      </v-alert>

      <IdeaCard
        v-for="card in cards"
        :key="`${card.kind}-${card.id}`"
        :card="card"
        :restriction-names="restrictionNames"
      />

      <div
        v-if="cards.length < feed.total"
        class="d-flex justify-center mt-3"
      >
        <v-btn
          variant="tonal"
          color="primary"
          :loading="loadingMore"
          data-testid="idea-more"
          @click="loadMore"
        >
          {{ $t('personal.ideas.more') }}
        </v-btn>
      </div>

      <div
        v-if="cards.length"
        class="text-body-small text-medium-emphasis mt-4"
      >
        {{ $t('personal.ideas.order-help') }}
        <template v-if="showsHints">
          {{ $t('personal.ideas.hint-help') }}
        </template>
      </div>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { mdiShuffleVariant } from "@mdi/js";
import IdeaCard from "~/components/Domain/Idea/IdeaCard.vue";
import IdeaGenerateDialog from "~/components/Domain/Idea/IdeaGenerateDialog.vue";
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import type { IdeaCard as IdeaCardData, IdeaFeedOut, IdeaTagCount } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

interface FilterItem {
  key: string;
  title: string;
  count: number;
}

const PAGE_SIZE = 30;
const MAX_LABELS = 30;
const SEARCH_DELAY = 300;
/** The order of the filters: what a person asks first when they choose a meal. */
const TAG_ORDER = [
  "QUICK",
  "ALL_IN_STOCK",
  "IN_STOCK",
  "SEASONAL",
  "PROMOTION",
  "COMPATIBLE",
  "TO_CHECK",
  "INCOMPATIBLE",
  "HINT_VEGETARIAN",
  "HINT_VEGAN",
  "NEVER_MADE",
  "NEW",
  "TOP_RATED",
  "INSPIRATION",
];

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();

useSeoMeta({ title: i18n.t("personal.ideas.title") });

const feed = ref<IdeaFeedOut | null>(null);
const cards = ref<IdeaCardData[]>([]);
const loading = ref(true);
const loadingMore = ref(false);
const generateDialog = ref(false);

function tagsFromQuery(): string[] {
  const value = route.query.tags;
  const list = Array.isArray(value) ? value : value ? [value] : [];
  return list.filter((tag): tag is string => typeof tag === "string" && !!tag);
}

const selectedTags = ref<string[]>(tagsFromQuery());
const search = ref<string | null>("");
const restrictions = ref<string[]>([]);
const maxCost = ref<number | string | null>(null);
const includeIncompatible = ref(false);
/** The order stays the same while the user reads more of the feed, even past midnight. */
const seed = ref("");
/** Stays true once a cost was seen, so that the field does not go away when its own filter empties the feed. */
const sawCost = ref(false);

const restrictionNames = ref<Record<string, string>>({});
const restrictionItems = computed(() =>
  Object.entries(restrictionNames.value)
    .map(([value, title]) => ({ value, title }))
    .sort((a, b) => a.title.localeCompare(b.title, i18n.locale.value)),
);

const costLimit = computed(() => (typeof maxCost.value === "number" && maxCost.value > 0 ? maxCost.value : undefined));
const showMaxCost = computed(() => sawCost.value || costLimit.value !== undefined);
const searchTerm = computed(() => (search.value ?? "").trim());
const hasFilters = computed(
  () => !!selectedTags.value.length || !!searchTerm.value || !!restrictions.value.length || costLimit.value !== undefined,
);
const showsHints = computed(() => cards.value.some(card => card.tags.some(tag => tag.key.startsWith("HINT_"))));

function filterItem(entry: IdeaTagCount): FilterItem {
  const title = entry.kind === "LABEL" ? (entry.value ?? entry.key) : i18n.t(`personal.ideas.tag.${entry.key}`);
  return { key: entry.key, title, count: entry.count };
}

/** A selected filter stays in the list when no card carries it any more, so that the user can remove it. */
function withSelected(items: FilterItem[], isLabel: boolean): FilterItem[] {
  const present = new Set(items.map(item => item.key));
  for (const key of selectedTags.value) {
    if (!present.has(key) && key.startsWith("label:") === isLabel) {
      const title = isLabel ? key.slice("label:".length) : i18n.t(`personal.ideas.tag.${key}`);
      items.push({ key, title, count: 0 });
    }
  }
  return items;
}

const builtinFilters = computed(() => {
  const items = (feed.value?.availableTags ?? []).filter(entry => entry.kind !== "LABEL").map(filterItem);
  const rank = (key: string) => (TAG_ORDER.includes(key) ? TAG_ORDER.indexOf(key) : TAG_ORDER.length);
  return withSelected(items, false)
    .filter(item => TAG_ORDER.includes(item.key))
    .sort((a, b) => rank(a.key) - rank(b.key));
});

const labelFilters = computed(() => {
  const items = (feed.value?.availableTags ?? [])
    .filter(entry => entry.kind === "LABEL")
    .map(filterItem)
    .sort((a, b) => b.count - a.count || a.title.localeCompare(b.title, i18n.locale.value))
    .slice(0, MAX_LABELS);
  return withSelected(items, true);
});

const checkedFor = computed(() => {
  const keys = feed.value?.restrictionKeys ?? [];
  if (!keys.length) {
    return i18n.t("personal.ideas.restrictions-none");
  }
  const names = keys.map(key => restrictionNames.value[key] ?? key).join(", ");
  return i18n.t("personal.ideas.restrictions-checked", { names });
});

let request = 0;

async function fetchPage(offset: number) {
  return await api.ideas.getFeed({
    tags: selectedTags.value,
    search: searchTerm.value,
    restrictions: restrictions.value,
    maxCost: costLimit.value,
    includeIncompatible: includeIncompatible.value,
    limit: PAGE_SIZE,
    offset,
    seed: seed.value || undefined,
  });
}

function remember(data: IdeaFeedOut) {
  feed.value = data;
  seed.value = data.seed;
  if (data.items.some(card => card.costPerServing !== null)) {
    sawCost.value = true;
  }
}

/** Load the feed again from its start. A slower answer to an older question is dropped. */
async function reload() {
  const current = ++request;
  loading.value = true;
  const { data } = await fetchPage(0);
  if (current !== request) {
    return;
  }
  loading.value = false;
  if (data) {
    remember(data);
    cards.value = data.items;
  }
}

async function loadMore() {
  const current = ++request;
  loadingMore.value = true;
  const { data } = await fetchPage(cards.value.length);
  loadingMore.value = false;
  if (current !== request || !data) {
    return;
  }
  remember(data);
  const known = new Set(cards.value.map(card => `${card.kind}-${card.id}`));
  cards.value = [...cards.value, ...data.items.filter(card => !known.has(`${card.kind}-${card.id}`))];
}

function shuffle() {
  seed.value = Math.random().toString(36).slice(2, 12);
  reload();
}

function clearFilters() {
  selectedTags.value = [];
  search.value = "";
  restrictions.value = [];
  maxCost.value = null;
}

async function loadRestrictions() {
  const { data } = await api.dietary.getRestrictions();
  restrictionNames.value = Object.fromEntries((data ?? []).map(restriction => [restriction.key, restriction.name]));
}

watch([selectedTags, restrictions, includeIncompatible, costLimit], reload, { deep: true });

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(searchTerm, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(reload, SEARCH_DELAY);
});

onMounted(() => {
  loadRestrictions();
  reload();
});

onBeforeUnmount(() => {
  clearTimeout(searchTimer);
  request++;
});
</script>
