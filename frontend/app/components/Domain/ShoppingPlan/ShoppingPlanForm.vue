<template>
  <div>
    <template v-if="!editing">
      <v-btn-toggle
        v-model="form.sourceType"
        mandatory
        divided
        variant="outlined"
        color="primary"
        density="comfortable"
        class="w-100"
        :aria-label="$t('personal.shopping.form.source-type')"
      >
        <v-btn
          v-for="source in sourceTypes"
          :key="source"
          :value="source"
          class="flex-grow-1 px-1"
          :data-testid="`plan-source-${source}`"
        >
          {{ $t(`personal.shopping.source.${source}`) }}
        </v-btn>
      </v-btn-toggle>
      <div class="text-body-small text-medium-emphasis mt-2 mb-4">
        {{ $t(`personal.shopping.source-help.${form.sourceType}`) }}
      </div>
    </template>

    <template v-if="form.sourceType === 'EVENT' && !editing">
      <v-select
        v-model="form.eventId"
        :items="eventItems"
        :label="$t('personal.shopping.form.event')"
        :loading="loading"
        data-testid="plan-event"
      />
      <v-alert
        v-if="!loading && !events.length"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        {{ $t('personal.shopping.form.no-events') }}
      </v-alert>
    </template>

    <template v-if="form.sourceType === 'MEALPLAN'">
      <v-row density="compact">
        <v-col cols="6">
          <v-text-field
            v-model="form.dateFrom"
            type="date"
            :label="$t('personal.shopping.form.date-from')"
            data-testid="plan-date-from"
          />
        </v-col>
        <v-col cols="6">
          <v-text-field
            v-model="form.dateTo"
            type="date"
            :label="$t('personal.shopping.form.date-to')"
            :error-messages="datesInvalid ? [$t('personal.shopping.form.dates-invalid')] : []"
            data-testid="plan-date-to"
          />
        </v-col>
      </v-row>
    </template>

    <template v-if="form.sourceType === 'RECIPES'">
      <v-autocomplete
        v-model="recipeIds"
        :items="recipes"
        item-title="name"
        item-value="id"
        :label="$t('personal.shopping.form.recipes')"
        :loading="loading"
        multiple
        hide-details
        data-testid="plan-recipes"
      >
        <template #selection="{ index }">
          <span
            v-if="index === 0"
            class="text-body-medium"
          >
            {{ $t('personal.shopping.form.recipes-selected', { count: form.recipes.length }) }}
          </span>
        </template>
      </v-autocomplete>
      <div class="my-3">
        <div
          v-if="!form.recipes.length"
          class="text-body-medium text-medium-emphasis"
        >
          {{ $t('personal.shopping.form.no-recipes') }}
        </div>
        <div
          v-for="(entry, index) in form.recipes"
          :key="entry.recipeId"
          class="d-flex align-center ga-2 mb-2"
          data-testid="plan-recipe-row"
        >
          <span class="flex-grow-1 text-body-medium plan-recipe-name">{{ recipeName(entry.recipeId) }}</span>
          <v-text-field
            v-model.number="entry.scale"
            type="number"
            min="0.25"
            step="0.25"
            inputmode="decimal"
            density="compact"
            hide-details
            prefix="×"
            :aria-label="$t('personal.shopping.form.scale')"
            :error="!validScale(entry.scale)"
            class="plan-recipe-scale flex-grow-0"
            data-testid="plan-recipe-scale"
          />
          <v-btn
            icon
            size="small"
            variant="text"
            :aria-label="$t('personal.shopping.form.remove-recipe')"
            @click="form.recipes.splice(index, 1)"
          >
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>
      </div>
    </template>

    <v-text-field
      v-model="form.name"
      :label="$t('personal.shopping.form.name')"
      data-testid="plan-name"
    />

    <v-switch
      v-model="form.useStock"
      color="primary"
      hide-details
      :label="$t('personal.shopping.form.use-stock')"
      data-testid="plan-use-stock"
    />
    <div class="text-body-small text-medium-emphasis mb-2">
      {{ $t('personal.shopping.form.use-stock-help') }}
    </div>
    <v-switch
      v-model="form.usePackaging"
      color="primary"
      hide-details
      :label="$t('personal.shopping.form.use-packaging')"
      data-testid="plan-use-packaging"
    />
    <div class="text-body-small text-medium-emphasis mb-4">
      {{ $t('personal.shopping.form.use-packaging-help') }}
    </div>

    <template v-if="!editing">
      <v-select
        v-model="targetList"
        :items="listItems"
        :label="$t('personal.shopping.form.target-list')"
        :hint="$t('personal.shopping.form.target-list-help')"
        persistent-hint
        data-testid="plan-target-list"
      />
    </template>
  </div>
</template>

<script lang="ts">
import { useUserApi } from "~/composables/api";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import type { ShoppingListSummary } from "~/lib/api/types/household";
import type { MealEventSummary, ShoppingPlanCreate, ShoppingPlanOut, ShoppingPlanSource } from "~/lib/api/types/personal";
import type { RecipeSummary } from "~/lib/api/types/recipe";

export interface ShoppingPlanFormModel {
  name: string;
  sourceType: ShoppingPlanSource;
  eventId: string | null;
  dateFrom: string;
  dateTo: string;
  recipes: { recipeId: string; scale: number }[];
  useStock: boolean;
  usePackaging: boolean;
  shoppingListId: string | null;
}

function isoDate(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Monday and Sunday of the current week, in local time. */
function currentWeek(): { from: string; to: string } {
  const today = new Date();
  const sinceMonday = (today.getDay() + 6) % 7;
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - sinceMonday);
  const sunday = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + 6);
  return { from: isoDate(monday), to: isoDate(sunday) };
}

export function emptyShoppingPlanForm(): ShoppingPlanFormModel {
  const week = currentWeek();
  return {
    name: "",
    sourceType: "RECIPES",
    eventId: null,
    dateFrom: week.from,
    dateTo: week.to,
    recipes: [],
    useStock: true,
    usePackaging: true,
    shoppingListId: null,
  };
}

export function shoppingPlanFormFrom(plan: ShoppingPlanOut): ShoppingPlanFormModel {
  const week = currentWeek();
  return {
    name: plan.name,
    sourceType: plan.sourceType,
    eventId: plan.eventId,
    dateFrom: plan.dateFrom ?? week.from,
    dateTo: plan.dateTo ?? week.to,
    recipes: plan.recipes.map(entry => ({ recipeId: entry.recipeId, scale: entry.scale ?? 1 })),
    useStock: plan.useStock,
    usePackaging: plan.usePackaging,
    shoppingListId: plan.shoppingListId,
  };
}

function validScale(scale: unknown): boolean {
  return typeof scale === "number" && Number.isFinite(scale) && scale > 0;
}

export function shoppingPlanFormIsValid(form: ShoppingPlanFormModel): boolean {
  if (!form.name.trim()) {
    return false;
  }
  if (form.sourceType === "EVENT") {
    return !!form.eventId;
  }
  if (form.sourceType === "MEALPLAN") {
    return !!form.dateFrom && !!form.dateTo && form.dateFrom <= form.dateTo;
  }
  return form.recipes.length > 0 && form.recipes.every(entry => validScale(entry.scale));
}

/** The whole body that the server expects, for a creation as for an update. */
export function shoppingPlanFormPayload(form: ShoppingPlanFormModel): ShoppingPlanCreate {
  return {
    name: form.name.trim(),
    sourceType: form.sourceType,
    eventId: form.sourceType === "EVENT" ? form.eventId : null,
    dateFrom: form.sourceType === "MEALPLAN" ? form.dateFrom : null,
    dateTo: form.sourceType === "MEALPLAN" ? form.dateTo : null,
    recipes: form.sourceType === "RECIPES" ? form.recipes.map(entry => ({ recipeId: entry.recipeId, scale: entry.scale })) : [],
    shoppingListId: form.shoppingListId,
    useStock: form.useStock,
    usePackaging: form.usePackaging,
  };
}
</script>

<script setup lang="ts">
const NEW_LIST = "__new__";

const props = withDefaults(defineProps<{ editing?: boolean }>(), { editing: false });
const form = defineModel<ShoppingPlanFormModel>({ required: true });

const i18n = useI18n();
const api = usePersonalApi();
const userApi = useUserApi();

const sourceTypes: ShoppingPlanSource[] = ["EVENT", "MEALPLAN", "RECIPES"];

const events = ref<MealEventSummary[]>([]);
const recipes = ref<RecipeSummary[]>([]);
const lists = ref<ShoppingListSummary[]>([]);
const loading = ref(true);

function shortDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const date = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(i18n.locale.value, { day: "numeric", month: "short" }).format(date);
}

const eventItems = computed(() =>
  events.value.map(event => ({
    value: event.id,
    title: event.startsAt ? `${event.name} · ${shortDate(event.startsAt)}` : event.name,
  })),
);

const listItems = computed(() => [
  { value: NEW_LIST, title: i18n.t("personal.shopping.form.new-list") },
  ...lists.value.map(list => ({ value: list.id, title: list.name || list.id })),
]);

const targetList = computed({
  get: () => form.value.shoppingListId ?? NEW_LIST,
  set: (value: string) => {
    form.value.shoppingListId = value === NEW_LIST ? null : value;
  },
});

const recipeIds = computed({
  get: () => form.value.recipes.map(entry => entry.recipeId),
  set: (ids: string[]) => {
    const current = form.value.recipes;
    form.value.recipes = ids.map(id => current.find(entry => entry.recipeId === id) ?? { recipeId: id, scale: 1 });
  },
});

const datesInvalid = computed(() => !!form.value.dateFrom && !!form.value.dateTo && form.value.dateFrom > form.value.dateTo);

function recipeName(recipeId: string): string {
  return recipes.value.find(recipe => recipe.id === recipeId)?.name ?? "…";
}

/** A name that says what the plan covers. It follows the choices until the user types a name. */
const suggestedName = computed(() => {
  const data = form.value;
  if (data.sourceType === "EVENT") {
    const event = events.value.find(item => item.id === data.eventId);
    return event ? i18n.t("personal.shopping.default-name.EVENT", { name: event.name }) : "";
  }
  if (data.sourceType === "MEALPLAN") {
    const from = shortDate(data.dateFrom);
    const to = shortDate(data.dateTo);
    return from && to ? i18n.t("personal.shopping.default-name.MEALPLAN", { from, to }) : "";
  }
  const first = data.recipes[0] ? recipes.value.find(recipe => recipe.id === data.recipes[0]!.recipeId) : undefined;
  if (!first) {
    return "";
  }
  return data.recipes.length > 1
    ? i18n.t("personal.shopping.default-name.RECIPES_MORE", { name: first.name, count: data.recipes.length - 1 })
    : i18n.t("personal.shopping.default-name.RECIPES", { name: first.name });
});

watch(
  suggestedName,
  (next, previous) => {
    if (props.editing) {
      return;
    }
    const name = form.value.name.trim();
    if (!name || name === previous) {
      form.value.name = next;
    }
  },
  { immediate: true },
);

onMounted(async () => {
  const [eventsResult, recipesResult, listsResult] = await Promise.all([
    props.editing ? null : api.mealEvents.getAll(1, -1),
    userApi.recipes.getAll(1, -1, { orderBy: "name", orderDirection: "asc" }),
    props.editing ? null : userApi.shopping.lists.getAll(),
  ]);
  events.value = eventsResult?.data?.items ?? [];
  recipes.value = recipesResult.data?.items ?? [];
  lists.value = listsResult?.data?.items ?? [];
  loading.value = false;
});
</script>

<style scoped>
.plan-recipe-name {
  min-width: 0;
  overflow-wrap: anywhere;
}

.plan-recipe-scale {
  width: 104px;
  max-width: 104px;
}
</style>
