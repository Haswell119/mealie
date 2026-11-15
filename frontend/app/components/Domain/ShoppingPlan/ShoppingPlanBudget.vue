<template>
  <v-card
    v-if="budget && budget.lineCount"
    variant="outlined"
    class="mb-4"
    data-testid="plan-budget"
  >
    <v-card-text class="pa-3">
      <div class="d-flex align-center ga-2 mb-1">
        <v-icon
          :icon="mdiCashMultiple"
          size="small"
        />
        <h2 class="text-title-medium font-weight-medium">
          {{ $t('personal.prices.budget.title') }}
        </h2>
      </div>
      <div class="text-body-small text-medium-emphasis mb-2">
        {{ $t('personal.prices.budget.help') }}
      </div>

      <div
        v-if="!totals.length"
        class="d-flex flex-wrap align-center ga-2"
        data-testid="plan-budget-empty"
      >
        <span class="text-body-medium flex-grow-1">{{ $t('personal.prices.budget.empty') }}</span>
        <v-btn
          variant="tonal"
          color="primary"
          size="small"
          to="/pantry?tab=prices"
        >
          {{ $t('personal.prices.budget.empty-cta') }}
        </v-btn>
      </div>

      <template v-else>
        <div
          v-for="total in totals"
          :key="total.store"
          class="budget-total"
          :class="{ 'budget-total--best': total.store === BEST }"
          data-testid="plan-budget-total"
          :data-store="total.store"
        >
          <div class="d-flex align-baseline flex-wrap ga-2">
            <span class="text-body-large font-weight-medium flex-grow-1 budget-wrap">{{ total.name }}</span>
            <span
              class="text-title-medium font-weight-bold"
              data-testid="plan-budget-amount"
            >{{ money(total.total) }}</span>
          </div>
          <div class="text-body-small text-medium-emphasis">
            <span :class="{ 'text-warning': total.missingLines > 0 }">{{ coverage(total) }}</span>
            <template v-if="total.promotions">
              · {{ $t('personal.prices.budget.promotions', { count: total.promotions }, total.promotions) }}
            </template>
            <template v-if="total.usedTotal < total.total">
              · {{ $t('personal.prices.budget.used', { amount: money(total.usedTotal) }) }}
            </template>
          </div>
        </div>

        <v-expansion-panels
          variant="accordion"
          flat
          class="mt-2"
        >
          <v-expansion-panel data-testid="plan-budget-details">
            <v-expansion-panel-title class="px-0 text-body-medium">
              {{ $t('personal.prices.budget.details') }}
            </v-expansion-panel-title>
            <v-expansion-panel-text class="budget-details">
              <div
                v-for="line in budget.lines"
                :key="line.key"
                class="budget-line"
                data-testid="plan-budget-line"
              >
                <div class="text-body-medium font-weight-medium budget-wrap">
                  {{ line.display || $t('personal.shopping.detail.unnamed') }}
                  <span class="text-medium-emphasis font-weight-regular">· {{ text.quantity(line.quantity) }} {{ line.unitName }}</span>
                </div>
                <div
                  v-if="line.reason"
                  class="text-body-small text-medium-emphasis"
                >
                  {{ reason(line.reason) }}
                </div>
                <div
                  v-for="offer in line.offers"
                  :key="offer.store"
                  class="d-flex flex-wrap ga-2 text-body-small"
                >
                  <span class="flex-grow-1 budget-wrap">
                    {{ storeName(offer.store) }}
                    <template v-if="offer.packs">
                      · {{ $t('personal.prices.budget.line-packs', { count: offer.packs }, offer.packs) }}
                    </template>
                    <template v-if="offer.label">
                      · {{ offer.label }}
                    </template>
                    <v-chip
                      v-if="offer.onPromotion"
                      size="x-small"
                      color="secondary"
                      variant="tonal"
                      label
                      class="ml-1"
                    >
                      {{ $t('personal.prices.promotion') }}
                    </v-chip>
                  </span>
                  <span class="font-weight-medium">{{ money(offer.cost) }}</span>
                </div>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { mdiCashMultiple } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type { BudgetTotal, PlanBudgetOut } from "~/lib/api/types/personal";

/** The store key of the total that takes the cheapest known price of each item. */
const BEST = "*";

const props = defineProps<{ planId: string }>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();

const budget = ref<PlanBudgetOut | null>(null);
let request = 0;

/** The budget is an extra: when it cannot be read, the plan stays usable and the card stays hidden. */
async function refresh() {
  const current = ++request;
  const { data } = await api.shoppingPlans.getBudget(props.planId);
  if (current === request) {
    budget.value = data ?? null;
  }
}

const totals = computed(() => {
  const current = budget.value;
  if (!current) {
    return [];
  }
  const list: (BudgetTotal & { name: string })[] = [];
  // The best-price total says something only when more than one shop has prices.
  if (current.best && current.stores.length > 1) {
    list.push({ ...current.best, name: i18n.t("personal.prices.budget.best") });
  }
  for (const total of current.stores) {
    list.push({ ...total, name: text.store(total.store) });
  }
  return list;
});

function storeName(store: string): string {
  return text.store(store);
}

function money(value: number): string {
  return text.money(value, budget.value?.currency);
}

function coverage(total: BudgetTotal): string {
  if (!total.missingLines) {
    return i18n.t("personal.prices.budget.complete");
  }
  const lineCount = budget.value?.lineCount ?? 0;
  const covered = i18n.t("personal.prices.budget.covered", { priced: total.pricedLines, total: lineCount }, total.pricedLines);
  const missing = i18n.t("personal.prices.budget.missing", { count: total.missingLines }, total.missingLines);
  return `${covered} · ${missing}`;
}

function reason(code: string): string {
  const key = `personal.prices.budget.reason.${code}`;
  return i18n.te(key) ? i18n.t(key) : code;
}

defineExpose({ refresh });

watch(() => props.planId, refresh, { immediate: true });

onBeforeUnmount(() => {
  request++;
});
</script>

<style scoped>
.budget-total {
  padding: 8px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.budget-total--best {
  border-top: none;
}

.budget-total:first-of-type {
  border-top: none;
}

.budget-wrap {
  min-width: 0;
  overflow-wrap: anywhere;
}

.budget-details :deep(.v-expansion-panel-text__wrapper) {
  padding: 0;
}

.budget-line {
  padding: 6px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
