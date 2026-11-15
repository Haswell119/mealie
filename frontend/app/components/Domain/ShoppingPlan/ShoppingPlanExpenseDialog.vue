<template>
  <BaseDialog
    v-model="open"
    :title="$t('personal.budget.record.title')"
    :icon="mdiCartCheck"
    max-width="520"
    width="100%"
    can-submit
    :submit-text="$t('personal.budget.record.save')"
    :submit-icon="$globals.icons.save"
    :submit-disabled="!canSave || saving"
    disable-submit-on-enter
    keep-open
    @submit="save"
  >
    <v-card-text data-testid="plan-expense">
      <p class="text-body-small text-medium-emphasis mb-3">
        {{ $t('personal.budget.record.help') }}
      </p>

      <div
        v-for="expense in existing"
        :key="expense.id"
        class="text-body-small text-medium-emphasis mb-2"
        data-testid="plan-expense-existing"
      >
        {{ $t('personal.budget.record.existing', {
          amount: text.money(expense.amount, expense.currency),
          store: text.store(expense.store),
          date: day(expense.spentOn),
        }) }}
      </div>

      <v-combobox
        v-model="store"
        :items="storeNames"
        :label="$t('personal.budget.expenses.store')"
        :hint="$t('personal.budget.expenses.store-hint')"
        persistent-hint
        maxlength="60"
        data-testid="plan-expense-store"
      />
      <div
        class="text-body-small my-2"
        :class="estimate === null ? 'text-warning' : 'text-medium-emphasis'"
        data-testid="plan-expense-estimate"
      >
        <template v-if="estimate !== null">
          {{ $t('personal.budget.record.estimate', { store: text.store(storeKey), amount: text.money(estimate, budget?.currency) }) }}
        </template>
        <template v-else-if="storeKey">
          {{ $t('personal.budget.record.no-estimate') }}
        </template>
      </div>
      <v-row dense>
        <v-col cols="6">
          <v-text-field
            v-model.number="amount"
            type="number"
            min="0"
            step="0.05"
            inputmode="decimal"
            :label="$t('personal.budget.expenses.amount')"
            :error-messages="amountInvalid ? [$t('personal.budget.expenses.amount-invalid')] : []"
            data-testid="plan-expense-amount"
            @update:model-value="amountTouched = true"
          />
        </v-col>
        <v-col cols="6">
          <v-text-field
            v-model="spentOn"
            type="date"
            :max="today()"
            :label="$t('personal.budget.expenses.date')"
            data-testid="plan-expense-date"
          />
        </v-col>
      </v-row>
      <v-text-field
        v-model="note"
        :label="$t('personal.budget.expenses.note')"
        maxlength="300"
        hide-details
      />
    </v-card-text>
    <template #custom-card-action>
      <v-btn
        variant="text"
        to="/budget"
        data-testid="plan-expense-open-budget"
      >
        {{ $t('personal.budget.record.open-budget') }}
      </v-btn>
    </template>
  </BaseDialog>
</template>

<script setup lang="ts">
import { mdiCartCheck } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { ExpenseOut, PlanBudgetOut } from "~/lib/api/types/personal";

const knownStores = ["migros", "coop", "aldi", "lidl"];

const props = defineProps<{ planId: string; budget: PlanBudgetOut | null }>();
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ saved: [expense: ExpenseOut] }>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();

const store = ref("");
const amount = ref<number | string>("");
const amountTouched = ref(false);
const spentOn = ref("");
const note = ref("");
const saving = ref(false);
const existing = ref<ExpenseOut[]>([]);

function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function day(value: string): string {
  return i18n.d(new Date(`${value}T00:00:00`), "short");
}

/** The shops of the budget first, the cheapest whole shopping at the top, then the other known shops. */
const storeKeys = computed(() => {
  const keys = (props.budget?.stores ?? []).map(total => total.store);
  return [...keys, ...knownStores.filter(key => !keys.includes(key))];
});
const storeNames = computed(() => storeKeys.value.map(key => text.store(key)));

/** The combobox shows names: the key of a known shop comes back from its name. */
const storeKey = computed(() => {
  const typed = (store.value ?? "").trim();
  const known = storeKeys.value.find(key => text.store(key).toLocaleLowerCase() === typed.toLocaleLowerCase());
  return known ?? typed.toLocaleLowerCase();
});

const estimate = computed(() => {
  const total = props.budget?.stores.find(item => item.store === storeKey.value);
  return total ? total.basketTotal : null;
});

const amountInvalid = computed(() => amount.value !== "" && !(typeof amount.value === "number" && amount.value > 0));
const canSave = computed(() => !!storeKey.value && typeof amount.value === "number" && amount.value > 0 && !!spentOn.value);

// The estimate of the chosen shop fills the amount until the person types one.
watch(estimate, (value) => {
  if (!amountTouched.value) {
    amount.value = value !== null ? Math.round(value * 100) / 100 : "";
  }
});

async function loadExisting() {
  const { data } = await api.budget.getAll(1, -1);
  existing.value = (data?.items ?? []).filter(expense => expense.planId === props.planId);
}

async function save() {
  if (!canSave.value) {
    return;
  }
  saving.value = true;
  const { data } = await api.shoppingPlans.recordExpense(props.planId, {
    store: storeKey.value,
    amount: Number(amount.value),
    spentOn: spentOn.value,
    note: note.value.trim() || null,
  });
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.budget.record.saved", { amount: text.money(data.amount, data.currency) }));
    emit("saved", data);
    open.value = false;
  }
}

watch(open, (value) => {
  if (!value) {
    return;
  }
  amountTouched.value = false;
  amount.value = "";
  note.value = "";
  spentOn.value = today();
  const first = props.budget?.recommendedStore ?? props.budget?.stores[0]?.store ?? "";
  store.value = first ? text.store(first) : "";
  if (estimate.value !== null) {
    amount.value = Math.round(estimate.value * 100) / 100;
  }
  loadExisting();
});
</script>
