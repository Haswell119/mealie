<template>
  <v-card
    v-if="budget && budget.lineCount"
    variant="outlined"
    class="mb-4"
    data-testid="plan-budget"
  >
    <ShoppingPlanStoreMatch
      v-model="matchDialog"
      :plan-id="planId"
      @kept="refresh"
    />
    <ShoppingPlanExpenseDialog
      v-model="expenseDialog"
      :plan-id="planId"
      :budget="budget"
    />

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
        v-if="!budget.stores.length"
        class="text-body-medium mb-2"
        data-testid="plan-budget-empty"
      >
        {{ $t('personal.prices.budget.empty') }}
      </div>

      <template v-else>
        <div
          v-for="total in budget.stores"
          :key="total.store"
          class="budget-total"
          :class="{ 'budget-total--best': isRecommended(total) }"
          data-testid="plan-budget-total"
          :data-store="total.store"
        >
          <div class="d-flex align-baseline ga-2">
            <span class="text-body-large font-weight-medium flex-grow-1 budget-wrap">
              {{ text.store(total.store) }}
            </span>
            <!-- A shop with too few prices has a total that is mostly an estimate: the total is not shown. -->
            <span
              v-if="total.comparable"
              class="text-title-medium font-weight-bold text-no-wrap"
              data-testid="plan-budget-amount"
            >{{ money(total.basketTotal) }}</span>
          </div>
          <v-chip
            v-if="isRecommended(total)"
            size="small"
            color="success"
            variant="tonal"
            label
            class="mb-1"
            data-testid="plan-budget-recommended"
          >
            {{ $t('personal.prices.budget.recommended') }}
          </v-chip>
          <div class="text-body-small text-medium-emphasis">
            {{ coverage(total) }}
            <template v-if="total.promotions">
              · {{ $t('personal.prices.budget.promotions', { count: total.promotions }, total.promotions) }}
            </template>
          </div>
          <div
            v-if="isRecommended(total) && saving"
            class="text-body-small text-success"
            data-testid="plan-budget-saving"
          >
            {{ saving }}
          </div>
          <div
            v-if="!total.comparable"
            class="text-body-small text-warning"
          >
            {{ $t('personal.prices.budget.not-comparable') }}
          </div>
        </div>

        <div
          v-if="budget.unpricedLines"
          class="text-body-small text-medium-emphasis mt-1"
          data-testid="plan-budget-unpriced"
        >
          {{ $t('personal.prices.budget.unpriced', { count: budget.unpricedLines }, budget.unpricedLines) }}
        </div>
      </template>

      <div class="d-flex flex-wrap ga-2 mt-3">
        <v-btn
          v-if="sourceEnabled"
          color="primary"
          variant="flat"
          size="small"
          :prepend-icon="mdiStoreSearchOutline"
          data-testid="plan-budget-match"
          @click="matchDialog = true"
        >
          {{ $t('personal.prices.budget.match') }}
        </v-btn>
        <v-btn
          v-else-if="!budget.stores.length"
          variant="tonal"
          color="primary"
          size="small"
          to="/pantry?tab=prices"
        >
          {{ $t('personal.prices.budget.empty-cta') }}
        </v-btn>
        <v-btn
          variant="tonal"
          size="small"
          :prepend-icon="mdiCartCheck"
          data-testid="plan-budget-record"
          @click="expenseDialog = true"
        >
          {{ $t('personal.prices.budget.record') }}
        </v-btn>
      </div>

      <v-expansion-panels
        v-if="budget.stores.length"
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
                  {{ text.store(offer.store) }}
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
                  <span
                    v-if="offer.approximate"
                    class="text-medium-emphasis"
                  > · {{ $t('personal.prices.budget.approximate') }}</span>
                </span>
                <span class="font-weight-medium">{{ money(offer.cost) }}</span>
              </div>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { mdiCartCheck, mdiCashMultiple, mdiStoreSearchOutline } from "@mdi/js";
import ShoppingPlanExpenseDialog from "~/components/Domain/ShoppingPlan/ShoppingPlanExpenseDialog.vue";
import ShoppingPlanStoreMatch from "~/components/Domain/ShoppingPlan/ShoppingPlanStoreMatch.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type { BudgetTotal, PlanBudgetOut } from "~/lib/api/types/personal";

const props = defineProps<{ planId: string }>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();

const budget = ref<PlanBudgetOut | null>(null);
const sourceEnabled = ref(false);
const matchDialog = ref(false);
const expenseDialog = ref(false);
let request = 0;

/** The budget is an extra: when it cannot be read, the plan stays usable and the card stays hidden. */
async function refresh() {
  const current = ++request;
  const { data } = await api.shoppingPlans.getBudget(props.planId);
  if (current === request) {
    budget.value = data ?? null;
  }
}

/** A person shops in one shop: the shop to name is the cheapest for the whole shopping. */
function isRecommended(total: BudgetTotal): boolean {
  const current = budget.value;
  return !!current && current.stores.length > 1 && current.recommendedStore === total.store;
}

/** What the recommended shop saves against the next shop that can be compared. */
const saving = computed(() => {
  const comparable = (budget.value?.stores ?? []).filter(total => total.comparable);
  const [best, next] = comparable;
  if (!best || !next || next.basketTotal - best.basketTotal < 0.01) {
    return "";
  }
  return i18n.t("personal.prices.budget.saving", {
    amount: money(next.basketTotal - best.basketTotal),
    store: text.store(next.store),
  });
});

function money(value: number): string {
  return text.money(value, budget.value?.currency);
}

function coverage(total: BudgetTotal): string {
  if (!total.missingLines) {
    return i18n.t("personal.prices.budget.complete");
  }
  const lineCount = budget.value?.lineCount ?? 0;
  const covered = i18n.t("personal.prices.budget.covered", { priced: total.pricedLines, total: lineCount }, total.pricedLines);
  // The lines that another shop prices and this shop does not: the estimate stands for them.
  const count = total.missingLines - (budget.value?.unpricedLines ?? 0);
  if (!total.comparable || total.estimatedMissing <= 0 || count <= 0) {
    return covered;
  }
  return `${covered} · ${i18n.t("personal.prices.budget.estimated", { amount: money(total.estimatedMissing), count }, count)}`;
}

function reason(code: string): string {
  const key = `personal.prices.budget.reason.${code}`;
  return i18n.te(key) ? i18n.t(key) : code;
}

defineExpose({ refresh });

watch(() => props.planId, refresh, { immediate: true });

onMounted(async () => {
  const { data } = await api.prices.getStatus();
  sourceEnabled.value = !!data?.enabled;
});

onBeforeUnmount(() => {
  request++;
});
</script>

<style scoped>
.budget-total {
  padding: 8px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.budget-total:first-of-type {
  border-top: none;
}

.budget-total--best {
  padding-left: 10px;
  border-left: 3px solid rgb(var(--v-theme-success));
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
