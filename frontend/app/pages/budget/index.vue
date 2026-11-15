<template>
  <v-container class="narrow-container pe-page">
    <BaseDialog
      v-model="settingsDialog"
      :title="$t('personal.budget.settings.title')"
      :icon="personalIcons.budget"
      max-width="520"
      width="100%"
      can-submit
      :submit-text="$t('personal.common.save')"
      :submit-icon="$globals.icons.save"
      :submit-disabled="targetInvalid || busy"
      disable-submit-on-enter
      keep-open
      @submit="saveSettings"
    >
      <v-card-text data-testid="budget-settings">
        <v-text-field
          v-model.number="settingsForm.target"
          type="number"
          min="0"
          step="10"
          inputmode="decimal"
          clearable
          :label="$t('personal.budget.settings.target')"
          :hint="$t('personal.budget.settings.target-hint')"
          :error-messages="targetInvalid ? [$t('personal.budget.settings.target-invalid')] : []"
          persistent-hint
          class="mb-3"
          data-testid="budget-settings-target"
        />
        <v-combobox
          v-model="settingsForm.store"
          :items="storeNames"
          clearable
          maxlength="60"
          :label="$t('personal.budget.settings.store')"
          :hint="$t('personal.budget.settings.store-hint')"
          persistent-hint
          data-testid="budget-settings-store"
        />
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="expenseDialog"
      :title="editing ? $t('personal.budget.expenses.edit') : $t('personal.budget.expenses.add')"
      :icon="personalIcons.budget"
      max-width="520"
      width="100%"
      can-submit
      :submit-text="$t('personal.common.save')"
      :submit-icon="$globals.icons.save"
      :submit-disabled="!canSaveExpense || busy"
      disable-submit-on-enter
      keep-open
      @submit="saveExpense"
    >
      <v-card-text data-testid="budget-expense-form">
        <v-row dense>
          <v-col cols="6">
            <v-text-field
              v-model="expenseForm.spentOn"
              type="date"
              :max="isoDay(new Date())"
              :label="$t('personal.budget.expenses.date')"
              data-testid="budget-expense-date"
            />
          </v-col>
          <v-col cols="6">
            <v-text-field
              v-model.number="expenseForm.amount"
              type="number"
              min="0"
              step="0.05"
              inputmode="decimal"
              :label="$t('personal.budget.expenses.amount')"
              :error-messages="expenseAmountInvalid ? [$t('personal.budget.expenses.amount-invalid')] : []"
              data-testid="budget-expense-amount"
            />
          </v-col>
        </v-row>
        <v-combobox
          v-model="expenseForm.store"
          :items="storeNames"
          maxlength="60"
          :label="$t('personal.budget.expenses.store')"
          :hint="$t('personal.budget.expenses.store-hint')"
          persistent-hint
          class="mb-3"
          data-testid="budget-expense-store"
        />
        <v-text-field
          v-model="expenseForm.note"
          :label="$t('personal.budget.expenses.note')"
          maxlength="300"
          hide-details
        />
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="deleteDialog"
      :title="$t('general.confirm')"
      :icon="$globals.icons.alertCircle"
      color="error"
      can-confirm
      @confirm="removeExpense"
    >
      <v-card-text v-if="deleting">
        {{ $t('personal.budget.expenses.delete-confirm', {
          amount: text.money(deleting.amount, deleting.currency),
          store: text.store(deleting.store),
        }) }}
      </v-card-text>
    </BaseDialog>

    <PersonalPageHeader
      :icon="personalIcons.budget"
      :title="$t('personal.budget.title')"
      :subtitle="$t('personal.budget.subtitle')"
    />

    <div
      v-if="loading"
      class="d-flex justify-center py-8"
    >
      <v-progress-circular
        indeterminate
        color="primary"
      />
    </div>

    <template v-else-if="summary">
      <v-card
        variant="outlined"
        class="mb-4"
        data-testid="budget-month"
      >
        <v-card-text class="pa-4">
          <div class="d-flex align-center flex-wrap ga-2">
            <h2 class="text-title-medium font-weight-medium flex-grow-1">
              {{ $t('personal.budget.month.title') }} · {{ monthName(summary.current.month) }}
            </h2>
            <v-btn
              variant="text"
              size="small"
              :prepend-icon="$globals.icons.cog"
              data-testid="budget-settings-open"
              @click="openSettings"
            >
              {{ $t('personal.budget.settings.button') }}
            </v-btn>
          </div>
          <div class="d-flex align-baseline flex-wrap ga-2 mt-1">
            <span
              class="text-headline-medium font-weight-bold"
              data-testid="budget-month-total"
            >{{ money(summary.current.total) }}</span>
            <span class="text-body-medium text-medium-emphasis">{{ $t('personal.budget.month.spent') }}</span>
          </div>

          <template v-if="summary.monthlyTarget !== null">
            <v-progress-linear
              :model-value="targetShare"
              :color="over ? 'error' : 'primary'"
              height="10"
              rounded
              class="my-2"
              :aria-label="$t('personal.budget.month.target', { amount: money(summary.monthlyTarget) })"
            />
            <div class="d-flex flex-wrap ga-2 text-body-medium">
              <span
                class="flex-grow-1 font-weight-medium"
                :class="over ? 'text-error' : ''"
                data-testid="budget-month-remaining"
              >{{ remainingText }}</span>
              <span class="text-medium-emphasis">{{ $t('personal.budget.month.target', { amount: money(summary.monthlyTarget) }) }}</span>
            </div>
          </template>
          <div
            v-else
            class="text-body-medium text-medium-emphasis mt-1"
            data-testid="budget-no-target"
          >
            {{ $t('personal.budget.month.no-target') }}
          </div>

          <div class="text-body-small text-medium-emphasis mt-2">
            <template v-if="summary.current.count">
              {{ $t('personal.budget.month.count', { count: summary.current.count }, summary.current.count) }}
            </template>
            <template v-if="summary.current.count && summary.averageMonth !== null">
              ·
            </template>
            <template v-if="summary.averageMonth !== null">
              {{ $t('personal.budget.month.average', { amount: money(summary.averageMonth) }) }}
            </template>
          </div>
        </v-card-text>
      </v-card>

      <v-card
        variant="outlined"
        class="mb-4"
        data-testid="budget-chart"
      >
        <v-card-text class="pa-4">
          <h2 class="text-title-medium font-weight-medium mb-2">
            {{ $t('personal.budget.chart.title') }}
          </h2>
          <div
            v-if="!summary.expenseCount"
            class="text-body-medium text-medium-emphasis"
          >
            {{ $t('personal.budget.chart.empty') }}
          </div>
          <div
            v-else
            class="chart"
            role="list"
          >
            <div
              v-for="month in chartMonths"
              :key="month.month"
              class="chart__col"
              role="listitem"
              :aria-label="$t('personal.budget.chart.bar', { month: monthName(month.month), amount: money(month.total) })"
              :title="$t('personal.budget.chart.bar', { month: monthName(month.month), amount: money(month.total) })"
              data-testid="budget-chart-bar"
            >
              <div class="chart__track">
                <div
                  v-if="month.total"
                  class="chart__value"
                  :style="{ bottom: `${month.share}%` }"
                >
                  {{ Math.round(month.total) }}
                </div>
                <div
                  v-if="targetLine !== null"
                  class="chart__target"
                  :style="{ bottom: `${targetLine}%` }"
                />
                <div
                  class="chart__bar"
                  :class="{
                    'chart__bar--current': month.current,
                    'chart__bar--over': month.over,
                  }"
                  :style="{ height: `${month.share}%` }"
                />
              </div>
              <div class="chart__label">
                {{ month.label }}
              </div>
            </div>
          </div>
          <div
            v-if="summary.expenseCount && targetLine !== null"
            class="text-body-small text-medium-emphasis mt-2 d-flex align-center ga-2"
          >
            <span class="chart__legend" />
            {{ $t('personal.budget.chart.target-line') }} · {{ money(summary.monthlyTarget ?? 0) }}
          </div>
        </v-card-text>
      </v-card>

      <v-card
        v-if="summary.stores.length"
        variant="outlined"
        class="mb-4"
        data-testid="budget-stores"
      >
        <v-card-text class="pa-4">
          <h2 class="text-title-medium font-weight-medium">
            {{ $t('personal.budget.stores.title') }}
          </h2>
          <div class="text-body-small text-medium-emphasis mb-2">
            {{ $t('personal.budget.stores.period', { months: summary.months.length }) }}
          </div>
          <div
            v-for="store in summary.stores"
            :key="store.store"
            class="mb-2"
            data-testid="budget-store"
          >
            <div class="d-flex flex-wrap ga-2 text-body-medium">
              <span class="flex-grow-1 font-weight-medium budget-wrap">{{ text.store(store.store) }}
                <span class="text-body-small text-medium-emphasis font-weight-regular">· {{ $t('personal.budget.stores.visits', { count: store.count }, store.count) }}</span>
              </span>
              <span class="font-weight-medium">{{ money(store.total) }}</span>
            </div>
            <v-progress-linear
              :model-value="summary.total ? (store.total / summary.total) * 100 : 0"
              color="primary"
              height="6"
              rounded
            />
          </div>
          <div
            v-if="summary.estimateCheck.count"
            class="text-body-small text-medium-emphasis mt-3"
            data-testid="budget-estimate-check"
          >
            {{ $t('personal.budget.check', {
              count: summary.estimateCheck.count,
              estimated: money(summary.estimateCheck.estimated),
              paid: money(summary.estimateCheck.paid),
            }, summary.estimateCheck.count) }}
          </div>
        </v-card-text>
      </v-card>

      <v-card
        variant="outlined"
        class="mb-4"
        data-testid="budget-expenses"
      >
        <v-card-text class="pa-4">
          <div class="d-flex align-center flex-wrap ga-2 mb-2">
            <h2 class="text-title-medium font-weight-medium flex-grow-1">
              {{ $t('personal.budget.expenses.title') }}
            </h2>
            <v-btn
              color="primary"
              variant="flat"
              size="small"
              :prepend-icon="$globals.icons.createAlt"
              data-testid="budget-expense-add"
              @click="openExpense(null)"
            >
              {{ $t('personal.budget.expenses.add') }}
            </v-btn>
          </div>
          <div
            v-if="!expenses.length"
            class="text-body-medium text-medium-emphasis"
            data-testid="budget-expenses-empty"
          >
            {{ $t('personal.budget.expenses.empty') }}
          </div>
          <div
            v-for="expense in shownExpenses"
            :key="expense.id"
            class="row-line d-flex align-center ga-2"
            data-testid="budget-expense"
          >
            <div class="flex-grow-1 budget-wrap">
              <div class="text-body-medium font-weight-medium">
                {{ text.store(expense.store) }}
                <span class="text-medium-emphasis font-weight-regular">· {{ day(expense.spentOn) }}</span>
              </div>
              <div
                v-if="expenseDetail(expense)"
                class="text-body-small text-medium-emphasis"
              >
                {{ expenseDetail(expense) }}
              </div>
            </div>
            <span class="text-body-large font-weight-medium">{{ text.money(expense.amount, expense.currency) }}</span>
            <v-btn
              icon
              variant="text"
              size="small"
              :aria-label="$t('personal.budget.expenses.edit')"
              data-testid="budget-expense-edit"
              @click="openExpense(expense)"
            >
              <v-icon
                :icon="$globals.icons.edit"
                size="small"
              />
            </v-btn>
            <v-btn
              icon
              variant="text"
              size="small"
              :aria-label="$t('general.delete')"
              data-testid="budget-expense-delete"
              @click="askDelete(expense)"
            >
              <v-icon
                :icon="$globals.icons.delete"
                size="small"
              />
            </v-btn>
          </div>
          <v-btn
            v-if="expenses.length > shownExpenses.length"
            variant="text"
            size="small"
            class="mt-1"
            @click="showAllExpenses = true"
          >
            {{ $t('personal.budget.expenses.more') }}
          </v-btn>
        </v-card-text>
      </v-card>

      <v-card
        variant="outlined"
        class="mb-4"
        data-testid="budget-meals"
      >
        <v-card-text class="pa-4">
          <h2 class="text-title-medium font-weight-medium">
            {{ $t('personal.budget.meals.title') }}
          </h2>
          <div class="text-body-small text-medium-emphasis mb-3">
            {{ $t('personal.budget.meals.help') }}
          </div>
          <v-select
            v-model="mealStore"
            :items="mealStoreItems"
            :label="$t('personal.budget.meals.prices-of')"
            density="compact"
            hide-details
            class="mb-3"
            data-testid="budget-meal-store"
          />
          <div class="d-flex align-center ga-1 mb-1">
            <v-btn
              icon
              variant="text"
              size="small"
              :aria-label="$t('personal.budget.meals.previous')"
              data-testid="budget-week-previous"
              @click="moveWeek(-1)"
            >
              <v-icon :icon="mdiChevronLeft" />
            </v-btn>
            <span
              class="text-body-medium font-weight-medium flex-grow-1 text-center"
              data-testid="budget-week"
            >{{ $t('personal.budget.meals.week', { from: day(weekFrom), to: day(weekTo) }) }}</span>
            <v-btn
              icon
              variant="text"
              size="small"
              :aria-label="$t('personal.budget.meals.next')"
              data-testid="budget-week-next"
              @click="moveWeek(1)"
            >
              <v-icon :icon="mdiChevronRight" />
            </v-btn>
          </div>

          <div
            v-if="meals && !meals.meals.length"
            class="d-flex flex-wrap align-center ga-2"
            data-testid="budget-meals-empty"
          >
            <span class="text-body-medium text-medium-emphasis flex-grow-1">{{ $t('personal.budget.meals.empty') }}</span>
            <v-btn
              variant="tonal"
              color="primary"
              size="small"
              to="/household/mealplan/planner/view"
            >
              {{ $t('personal.budget.meals.empty-cta') }}
            </v-btn>
          </div>
          <template v-else-if="meals">
            <div
              v-for="(meal, index) in meals.meals"
              :key="`${meal.date}-${meal.recipeId}-${index}`"
              class="row-line d-flex align-center ga-2"
              data-testid="budget-meal"
            >
              <div class="flex-grow-1 budget-wrap">
                <div class="text-body-small text-medium-emphasis">
                  {{ weekday(meal.date) }} · {{ mealType(meal.entryType) }}
                </div>
                <NuxtLink
                  v-if="meal.recipeSlug"
                  :to="recipeLink(meal.recipeSlug)"
                  class="text-body-medium font-weight-medium recipe-link"
                >
                  {{ meal.recipeName }}
                </NuxtLink>
                <div class="text-body-small text-medium-emphasis">
                  {{ costDetail(meal) }}
                </div>
              </div>
              <span
                v-if="meal.total !== null"
                class="text-body-large font-weight-medium"
              >{{ money(meal.total) }}</span>
              <span
                v-else
                class="text-body-small text-medium-emphasis"
              >{{ $t('personal.budget.meals.no-cost') }}</span>
            </div>
            <div class="row-line d-flex align-baseline ga-2">
              <span class="text-body-medium font-weight-medium flex-grow-1">{{ $t('personal.budget.meals.total') }}</span>
              <span
                class="text-title-medium font-weight-bold"
                data-testid="budget-meals-total"
              >{{ money(meals.total) }}</span>
            </div>
          </template>
        </v-card-text>
      </v-card>

      <v-card
        variant="outlined"
        class="mb-4"
        data-testid="budget-recipes"
      >
        <v-card-text class="pa-4">
          <h2 class="text-title-medium font-weight-medium">
            {{ $t('personal.budget.recipes.title') }}
          </h2>
          <div class="text-body-small text-medium-emphasis mb-2">
            {{ $t('personal.budget.recipes.help') }}
          </div>
          <div
            v-if="recipes && !recipes.pricedCount"
            class="text-body-medium text-medium-emphasis"
            data-testid="budget-recipes-empty"
          >
            {{ $t('personal.budget.recipes.empty') }}
          </div>
          <template v-else-if="recipes">
            <div class="text-body-small text-medium-emphasis mb-1">
              {{ $t('personal.budget.recipes.counted', { priced: recipes.pricedCount, total: recipes.recipes.length }, recipes.pricedCount) }}
            </div>
            <div
              v-for="recipe in shownRecipes"
              :key="recipe.recipeId"
              class="row-line d-flex align-center ga-2"
              data-testid="budget-recipe"
            >
              <div class="flex-grow-1 budget-wrap">
                <NuxtLink
                  v-if="recipe.recipeSlug"
                  :to="recipeLink(recipe.recipeSlug)"
                  class="text-body-medium font-weight-medium recipe-link"
                >
                  {{ recipe.recipeName }}
                </NuxtLink>
                <div class="text-body-small text-medium-emphasis">
                  {{ costDetail(recipe) }}
                </div>
              </div>
              <span
                v-if="recipe.perServing !== null"
                class="text-body-medium font-weight-medium text-right"
              >{{ $t('personal.budget.meals.per-serving', { amount: money(recipe.perServing) }) }}</span>
              <span
                v-else-if="recipe.total !== null"
                class="text-body-medium font-weight-medium"
              >{{ money(recipe.total) }}</span>
            </div>
            <v-btn
              v-if="recipes.pricedCount > shownRecipes.length"
              variant="text"
              size="small"
              class="mt-1"
              data-testid="budget-recipes-all"
              @click="showAllRecipes = true"
            >
              {{ $t('personal.budget.recipes.show-all') }}
            </v-btn>
          </template>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { mdiChevronLeft, mdiChevronRight } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { BudgetSummaryOut, ExpenseOut, MealCostsOut, RecipeCostsOut } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

/** The value of "the cheapest price of each food" in the list of shops. The server reads an empty shop so. */
const CHEAPEST = "";
const knownStores = ["migros", "coop", "aldi", "lidl"];
const FIRST_EXPENSES = 8;
const FIRST_RECIPES = 8;

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const auth = useMealieAuth();

useSeoMeta({ title: i18n.t("personal.budget.title") });

const loading = ref(true);
const busy = ref(false);
const summary = ref<BudgetSummaryOut | null>(null);
const expenses = ref<ExpenseOut[]>([]);
const meals = ref<MealCostsOut | null>(null);
const recipes = ref<RecipeCostsOut | null>(null);
const showAllExpenses = ref(false);
const showAllRecipes = ref(false);

// ----------------------------------------------------------------
// Dates

function isoDay(value: Date): string {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
}

function localDate(value: string): Date {
  return new Date(`${value}T00:00:00`);
}

function day(value: string): string {
  return i18n.d(localDate(value), "short");
}

function weekday(value: string): string {
  return new Intl.DateTimeFormat(i18n.locale.value, { weekday: "long", day: "numeric", month: "long" }).format(localDate(value));
}

function monthName(month: string): string {
  return new Intl.DateTimeFormat(i18n.locale.value, { month: "long", year: "numeric" }).format(localDate(`${month}-01`));
}

function monday(value: Date): Date {
  const start = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

const weekStart = ref(monday(new Date()));
const weekFrom = computed(() => isoDay(weekStart.value));
const weekTo = computed(() => {
  const end = new Date(weekStart.value);
  end.setDate(end.getDate() + 6);
  return isoDay(end);
});

// ----------------------------------------------------------------
// Shops

const storeNames = computed(() => knownStores.map(key => text.store(key)));

/** A combobox shows names: the key of a known shop comes back from its name. */
function storeKeyOf(typed: string | null | undefined): string {
  const value = (typed ?? "").trim();
  const known = knownStores.find(key => text.store(key).toLocaleLowerCase() === value.toLocaleLowerCase());
  return known ?? value.toLocaleLowerCase();
}

const mealStore = ref(CHEAPEST);
const mealStoreItems = computed(() => {
  const keys = [...knownStores];
  for (const key of [summary.value?.usualStore, mealStore.value]) {
    if (key && !keys.includes(key)) {
      keys.push(key);
    }
  }
  return [
    { value: CHEAPEST, title: i18n.t("personal.budget.meals.cheapest") },
    ...keys.map(key => ({ value: key, title: text.store(key) })),
  ];
});

// ----------------------------------------------------------------
// The month and the chart

function money(value: number): string {
  return text.money(value, summary.value?.currency);
}

const over = computed(() => (summary.value?.remaining ?? 0) < 0);
const targetShare = computed(() => {
  const current = summary.value;
  if (!current?.monthlyTarget) {
    return 0;
  }
  return Math.min((current.current.total / current.monthlyTarget) * 100, 100);
});
const remainingText = computed(() => {
  const remaining = summary.value?.remaining ?? 0;
  return remaining < 0
    ? i18n.t("personal.budget.month.over", { amount: money(-remaining) })
    : i18n.t("personal.budget.month.remaining", { amount: money(remaining) });
});

const chartTop = computed(() => {
  const current = summary.value;
  const highest = Math.max(...(current?.months ?? []).map(month => month.total), current?.monthlyTarget ?? 0);
  // Some room above the highest bar for its amount.
  return highest > 0 ? highest * 1.15 : 1;
});
const targetLine = computed(() => {
  const target = summary.value?.monthlyTarget;
  return target ? (target / chartTop.value) * 100 : null;
});
const chartMonths = computed(() => {
  const current = summary.value;
  if (!current) {
    return [];
  }
  const short = new Intl.DateTimeFormat(i18n.locale.value, { month: "short" });
  return current.months.map(month => ({
    ...month,
    label: short.format(localDate(`${month.month}-01`)),
    share: (month.total / chartTop.value) * 100,
    current: month.month === current.current.month,
    over: current.monthlyTarget !== null && month.total > current.monthlyTarget,
  }));
});

// ----------------------------------------------------------------
// Expenses

const shownExpenses = computed(() => (showAllExpenses.value ? expenses.value : expenses.value.slice(0, FIRST_EXPENSES)));

function expenseDetail(expense: ExpenseOut): string {
  const parts: string[] = [];
  if (expense.planName) {
    parts.push(i18n.t("personal.budget.expenses.plan", { name: expense.planName }));
  }
  if (expense.estimatedAmount !== null) {
    parts.push(i18n.t("personal.budget.expenses.estimated", { amount: text.money(expense.estimatedAmount, expense.currency) }));
  }
  if (expense.note) {
    parts.push(expense.note);
  }
  return parts.join(" · ");
}

interface ExpenseForm {
  spentOn: string;
  store: string;
  amount: number | string;
  note: string;
}
const expenseDialog = ref(false);
const editing = ref<ExpenseOut | null>(null);
const expenseForm = ref<ExpenseForm>({ spentOn: "", store: "", amount: "", note: "" });
const deleteDialog = ref(false);
const deleting = ref<ExpenseOut | null>(null);

const expenseAmountInvalid = computed(
  () => expenseForm.value.amount !== "" && !(typeof expenseForm.value.amount === "number" && expenseForm.value.amount > 0),
);
const canSaveExpense = computed(
  () =>
    !!expenseForm.value.spentOn
    && !!storeKeyOf(expenseForm.value.store)
    && typeof expenseForm.value.amount === "number"
    && expenseForm.value.amount > 0,
);

function openExpense(expense: ExpenseOut | null) {
  editing.value = expense;
  expenseForm.value = expense
    ? { spentOn: expense.spentOn, store: text.store(expense.store), amount: expense.amount, note: expense.note ?? "" }
    : { spentOn: isoDay(new Date()), store: summary.value?.usualStore ? text.store(summary.value.usualStore) : "", amount: "", note: "" };
  expenseDialog.value = true;
}

async function saveExpense() {
  if (!canSaveExpense.value) {
    return;
  }
  const current = editing.value;
  const payload = {
    spentOn: expenseForm.value.spentOn,
    store: storeKeyOf(expenseForm.value.store),
    amount: Number(expenseForm.value.amount),
    note: expenseForm.value.note.trim() || null,
    // An edit keeps the plan and the estimate of the expense.
    estimatedAmount: current?.estimatedAmount ?? null,
    planId: current?.planId ?? null,
  };
  busy.value = true;
  const { data } = current ? await api.budget.updateOne(current.id, payload) : await api.budget.createOne(payload);
  busy.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    expenseDialog.value = false;
    await loadSpending();
  }
}

function askDelete(expense: ExpenseOut) {
  deleting.value = expense;
  deleteDialog.value = true;
}

async function removeExpense() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.budget.deleteOne(deleting.value.id);
  deleting.value = null;
  if (data) {
    await loadSpending();
  }
}

// ----------------------------------------------------------------
// Settings

const settingsDialog = ref(false);
const settingsForm = ref<{ target: number | string | null; store: string | null }>({ target: "", store: "" });
const targetInvalid = computed(() => {
  const value = settingsForm.value.target;
  return value !== "" && value !== null && !(typeof value === "number" && value > 0);
});

function openSettings() {
  const current = summary.value;
  settingsForm.value = {
    target: current?.monthlyTarget ?? "",
    store: current?.usualStore ? text.store(current.usualStore) : "",
  };
  settingsDialog.value = true;
}

async function saveSettings() {
  if (targetInvalid.value) {
    return;
  }
  const target = settingsForm.value.target;
  busy.value = true;
  const { data } = await api.budget.setSettings({
    monthlyTarget: typeof target === "number" ? target : null,
    usualStore: storeKeyOf(settingsForm.value.store) || null,
  });
  busy.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    settingsDialog.value = false;
    await loadSpending();
    // The usual shop is the shop that prices the meals, until the person picks another one.
    mealStore.value = data.usualStore ?? CHEAPEST;
  }
}

// ----------------------------------------------------------------
// Meals and recipes

const groupSlug = computed(() => auth.user.value?.groupSlug || "");

function recipeLink(slug: string): string {
  return `/g/${groupSlug.value}/r/${slug}`;
}

function mealType(entryType: string): string {
  const key = `personal.budget.meals.types.${entryType}`;
  return i18n.te(key) ? i18n.t(key) : entryType;
}

function costDetail(item: { servings: number; perServing: number | null; pricedIngredients: number; ingredientCount: number }): string {
  const parts: string[] = [];
  if (item.servings > 0) {
    parts.push(i18n.t("personal.budget.meals.servings", { count: text.quantity(item.servings) }, Math.round(item.servings)));
  }
  if (item.pricedIngredients < item.ingredientCount) {
    parts.push(
      i18n.t("personal.budget.meals.partial", { priced: item.pricedIngredients, total: item.ingredientCount }, item.pricedIngredients),
    );
  }
  return parts.join(" · ");
}

const shownRecipes = computed(() => {
  const priced = (recipes.value?.recipes ?? []).filter(recipe => recipe.total !== null);
  return showAllRecipes.value ? priced : priced.slice(0, FIRST_RECIPES);
});

let mealRequest = 0;
async function loadMeals() {
  const current = ++mealRequest;
  const { data } = await api.budget.getMealCosts(weekFrom.value, weekTo.value, mealStore.value);
  if (current === mealRequest) {
    meals.value = data ?? null;
  }
}

let recipeRequest = 0;
async function loadRecipes() {
  const current = ++recipeRequest;
  const { data } = await api.budget.getRecipeCosts(mealStore.value);
  if (current === recipeRequest) {
    recipes.value = data ?? null;
  }
}

function moveWeek(weeks: number) {
  const start = new Date(weekStart.value);
  start.setDate(start.getDate() + weeks * 7);
  weekStart.value = start;
}

// ----------------------------------------------------------------
// Loading

async function loadSpending() {
  const [summaryResult, expensesResult] = await Promise.all([api.budget.getSummary(12), api.budget.getAll(1, -1)]);
  summary.value = summaryResult.data ?? null;
  expenses.value = [...(expensesResult.data?.items ?? [])].sort(
    (a, b) => b.spentOn.localeCompare(a.spentOn) || (b.createdAt ?? "").localeCompare(a.createdAt ?? ""),
  );
}

onMounted(async () => {
  await loadSpending();
  mealStore.value = summary.value?.usualStore ?? CHEAPEST;
  loading.value = false;
  await Promise.all([loadMeals(), loadRecipes()]);
  watch([weekFrom, mealStore], loadMeals);
  watch(mealStore, loadRecipes);
});
</script>

<style scoped>
.budget-wrap {
  min-width: 0;
  overflow-wrap: anywhere;
}

.row-line {
  padding: 8px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.recipe-link {
  color: inherit;
  text-decoration: none;
}

.recipe-link:hover,
.recipe-link:focus-visible {
  text-decoration: underline;
}

.chart {
  display: flex;
  align-items: stretch;
  gap: 4px;
}

.chart__col {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.chart__value {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  padding-bottom: 2px;
  font-size: 0.6875rem;
  line-height: 1;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.chart__track {
  position: relative;
  width: 100%;
  height: 150px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.chart__bar {
  width: 70%;
  max-width: 34px;
  min-height: 0;
  border-radius: 4px 4px 0 0;
  background: rgba(var(--v-theme-primary), 0.45);
}

.chart__bar--current {
  background: rgb(var(--v-theme-primary));
}

.chart__bar--over {
  background: rgb(var(--v-theme-error));
}

.chart__target {
  position: absolute;
  left: -2px;
  right: -2px;
  border-top: 2px dashed rgba(var(--v-theme-on-surface), 0.55);
}

.chart__legend {
  display: inline-block;
  width: 18px;
  border-top: 2px dashed rgba(var(--v-theme-on-surface), 0.55);
}

.chart__label {
  margin-top: 4px;
  font-size: 0.6875rem;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}
</style>
