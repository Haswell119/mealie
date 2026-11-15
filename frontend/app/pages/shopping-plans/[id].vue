<template>
  <v-container class="narrow-container">
    <BaseDialog
      v-model="editDialog"
      :title="$t('personal.shopping.edit.title')"
      :icon="personalIcons.shopping"
      max-width="700"
      width="100%"
      can-submit
      :submit-text="$t('personal.common.save')"
      :submit-icon="$globals.icons.save"
      :submit-disabled="!canSave || busy"
      disable-submit-on-enter
      keep-open
      @submit="saveEdit"
    >
      <v-card-text>
        <ShoppingPlanForm
          v-model="form"
          editing
        />
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="consumeDialog"
      :title="$t('personal.shopping.consume.confirm-title')"
      :icon="personalIcons.pantry"
      can-confirm
      @confirm="consume"
    >
      <v-card-text data-testid="plan-consume-confirm">
        {{ $t('personal.shopping.consume.confirm') }}
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="deleteDialog"
      :title="$t('general.confirm')"
      :icon="$globals.icons.alertCircle"
      color="error"
      can-confirm
      @confirm="remove"
    >
      <v-card-text>
        {{ $t('personal.shopping.delete-confirm', { name: plan?.name }) }}
      </v-card-text>
    </BaseDialog>

    <v-btn
      variant="text"
      class="mt-2 px-1"
      to="/shopping-plans"
      :prepend-icon="mdiArrowLeft"
      data-testid="plan-back"
    >
      {{ $t('personal.shopping.detail.back') }}
    </v-btn>

    <v-progress-linear
      :active="loading"
      indeterminate
      color="primary"
    />

    <v-alert
      v-if="notFound"
      type="error"
      variant="tonal"
      class="mt-4"
    >
      {{ $t('personal.shopping.detail.not-found') }}
    </v-alert>

    <template v-if="plan">
      <div class="d-flex align-start flex-wrap ga-2 mt-3">
        <h1
          class="text-headline-small flex-grow-1 plan-title"
          data-testid="plan-title"
        >
          {{ plan.name }}
        </h1>
        <v-chip
          size="small"
          :color="plan.status === 'DONE' ? 'success' : 'primary'"
          variant="tonal"
          data-testid="plan-status"
        >
          {{ $t(`personal.shopping.status.${plan.status}`) }}
        </v-chip>
      </div>
      <div class="text-body-medium text-medium-emphasis mb-1">
        {{ sourceSummary }}
      </div>
      <div class="text-body-small text-medium-emphasis">
        {{ plan.computedAt
          ? $t('personal.shopping.computed-at', { date: $d(new Date(plan.computedAt), 'long') })
          : $t('personal.shopping.never-computed') }}
      </div>

      <v-alert
        v-if="plan.status === 'DONE'"
        type="success"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="plan-done-info"
      >
        {{ $t('personal.shopping.detail.done-info') }}
      </v-alert>

      <v-alert
        v-for="(issue, index) in issues"
        :key="`issue-${index}`"
        type="error"
        variant="tonal"
        class="mb-3"
        data-testid="plan-issue"
      >
        <div class="font-weight-medium">
          {{ issueTitle(issue) }}
        </div>
        <div v-if="issueSubject(issue)">
          {{ issueSubject(issue) }}
        </div>
      </v-alert>

      <v-card
        variant="tonal"
        class="mb-4"
      >
        <v-card-text class="d-flex flex-column ga-3">
          <div>
            <v-btn
              color="primary"
              variant="flat"
              block
              class="plan-action"
              :loading="applying"
              :disabled="busy"
              :prepend-icon="personalIcons.shopping"
              data-testid="plan-apply"
              @click="apply"
            >
              {{ $t('personal.shopping.apply.button') }}
            </v-btn>
            <v-checkbox
              v-if="hasDismissed"
              v-model="restoreDismissed"
              :label="$t('personal.shopping.apply.restore-dismissed')"
              density="compact"
              hide-details
              data-testid="plan-restore-dismissed"
            />
          </div>

          <v-alert
            v-if="applyResult"
            type="success"
            variant="tonal"
            density="compact"
            data-testid="plan-apply-result"
          >
            <div class="font-weight-medium">
              {{ $t('personal.shopping.apply.done-title') }}
            </div>
            <div data-testid="plan-apply-summary">
              {{ $t('personal.shopping.apply.done-summary', {
                created: applyResult.created,
                updated: applyResult.updated,
                deleted: applyResult.deleted,
              }) }}
            </div>
          </v-alert>

          <v-btn
            v-if="plan.shoppingListId"
            variant="outlined"
            block
            class="plan-action"
            :to="`/shopping-lists/${plan.shoppingListId}`"
            :prepend-icon="mdiFormatListChecks"
            data-testid="plan-open-list"
          >
            {{ $t('personal.shopping.apply.open-list') }}
          </v-btn>

          <template v-if="plan.shoppingListId">
            <div>
              <v-btn
                variant="outlined"
                block
                class="plan-action"
                :loading="receiving"
                :disabled="busy"
                :prepend-icon="personalIcons.pantry"
                data-testid="plan-receive"
                @click="receive"
              >
                {{ $t('personal.shopping.receive.button') }}
              </v-btn>
              <div class="text-body-small text-medium-emphasis mt-1 mb-0">
                {{ $t('personal.shopping.receive.help') }}
              </div>
            </div>
            <v-alert
              v-if="receiveResult"
              :type="receiveResult.received || receiveResult.skipped ? 'success' : 'info'"
              variant="tonal"
              density="compact"
              data-testid="plan-receive-result"
            >
              {{ receiveResult.received || receiveResult.skipped
                ? $t('personal.shopping.receive.done', { received: receiveResult.received, skipped: receiveResult.skipped })
                : $t('personal.shopping.receive.nothing') }}
            </v-alert>
          </template>

          <v-btn
            v-if="plan.status !== 'DONE'"
            variant="outlined"
            block
            class="plan-action"
            :disabled="busy"
            :prepend-icon="mdiPotSteamOutline"
            data-testid="plan-consume"
            @click="consumeDialog = true"
          >
            {{ $t('personal.shopping.consume.button') }}
          </v-btn>
          <v-alert
            v-if="consumedCount !== null"
            type="success"
            variant="tonal"
            density="compact"
            data-testid="plan-consume-result"
          >
            {{ $t('personal.shopping.consume.done', { count: consumedCount }) }}
          </v-alert>

          <div class="d-flex flex-wrap ga-2">
            <v-btn
              variant="text"
              size="small"
              :disabled="busy"
              :prepend-icon="mdiRefresh"
              data-testid="plan-recompute"
              @click="recompute"
            >
              {{ $t('personal.shopping.recompute') }}
            </v-btn>
            <v-btn
              variant="text"
              size="small"
              :disabled="busy"
              :prepend-icon="$globals.icons.edit"
              data-testid="plan-edit"
              @click="openEdit"
            >
              {{ $t('personal.shopping.edit.button') }}
            </v-btn>
            <v-btn
              variant="text"
              size="small"
              color="error"
              :disabled="busy"
              :prepend-icon="$globals.icons.delete"
              data-testid="plan-delete"
              @click="deleteDialog = true"
            >
              {{ $t('personal.shopping.delete') }}
            </v-btn>
          </div>
        </v-card-text>
      </v-card>

      <h2 class="text-title-large mb-1">
        {{ $t('personal.shopping.detail.lines-title') }} ({{ lines.length }})
      </h2>
      <div
        class="text-body-medium text-medium-emphasis d-flex align-start ga-2"
        data-testid="plan-computed-note"
      >
        <v-icon
          size="small"
          class="mt-1"
          :icon="mdiCalculatorVariantOutline"
        />
        <span>{{ $t('personal.shopping.detail.computed-note') }}</span>
      </div>

      <v-alert
        v-if="!lines.length"
        type="info"
        variant="tonal"
        data-testid="plan-no-lines"
      >
        {{ $t('personal.shopping.detail.no-lines') }}
      </v-alert>

      <ShoppingPlanLineCard
        v-for="line in lines"
        :key="line.key"
        :line="line"
        :restriction-names="restrictionNames"
        :stored-name="storedNames[line.key]"
        :restore-dismissed="restoreDismissed"
      />
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { mdiArrowLeft, mdiCalculatorVariantOutline, mdiFormatListChecks, mdiPotSteamOutline, mdiRefresh } from "@mdi/js";
import ShoppingPlanForm, {
  emptyShoppingPlanForm,
  shoppingPlanFormFrom,
  shoppingPlanFormIsValid,
  shoppingPlanFormPayload,
} from "~/components/Domain/ShoppingPlan/ShoppingPlanForm.vue";
import type { ShoppingPlanFormModel } from "~/components/Domain/ShoppingPlan/ShoppingPlanForm.vue";
import ShoppingPlanLineCard from "~/components/Domain/ShoppingPlan/ShoppingPlanLineCard.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type {
  PantryReceiveOut,
  ShoppingPlanApplyOut,
  ShoppingPlanIssue,
  ShoppingPlanOut,
  ShoppingPlanPreviewLine,
} from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();
const router = useRouter();

const planId = computed(() => String(route.params.id));

const plan = ref<ShoppingPlanOut | null>(null);
const previewLines = ref<ShoppingPlanPreviewLine[]>([]);
const issues = ref<ShoppingPlanIssue[]>([]);
const storedNames = ref<Record<string, string>>({});
const restrictionNames = ref<Record<string, string>>({});
const eventName = ref("");

const loading = ref(true);
const notFound = ref(false);
const applying = ref(false);
const receiving = ref(false);
const consuming = ref(false);
const saving = ref(false);
const busy = computed(() => loading.value || applying.value || receiving.value || consuming.value || saving.value);

const restoreDismissed = ref(false);
const applyResult = ref<ShoppingPlanApplyOut | null>(null);
const receiveResult = ref<PantryReceiveOut | null>(null);
const consumedCount = ref<number | null>(null);

const editDialog = ref(false);
const consumeDialog = ref(false);
const deleteDialog = ref(false);
const form = ref<ShoppingPlanFormModel>(emptyShoppingPlanForm());
const canSave = computed(() => shoppingPlanFormIsValid(form.value));

useSeoMeta({ title: () => plan.value?.name ?? i18n.t("personal.shopping.title") });

/** The lines to buy first, in alphabetical order; the lines that the user removed from the list come last. */
const lines = computed(() => {
  const nameOf = (line: ShoppingPlanPreviewLine) => line.display || storedNames.value[line.key] || "";
  return [...previewLines.value].sort((a, b) => {
    const dismissed = Number(a.state === "DISMISSED") - Number(b.state === "DISMISSED");
    return dismissed || nameOf(a).localeCompare(nameOf(b), i18n.locale.value);
  });
});

const hasDismissed = computed(() => previewLines.value.some(line => line.state === "DISMISSED"));

function day(value: string | null): string {
  return value ? i18n.d(new Date(`${value}T00:00:00`), "short") : "";
}

const sourceSummary = computed(() => {
  const current = plan.value;
  if (!current) {
    return "";
  }
  if (current.sourceType === "EVENT") {
    return eventName.value
      ? i18n.t("personal.shopping.detail.source-event", { name: eventName.value })
      : i18n.t("personal.shopping.source.EVENT");
  }
  if (current.sourceType === "MEALPLAN") {
    return i18n.t("personal.shopping.detail.source-mealplan", { from: day(current.dateFrom), to: day(current.dateTo) });
  }
  return i18n.t("personal.shopping.detail.source-recipes", { count: current.recipes.length });
});

function issueTitle(issue: ShoppingPlanIssue): string {
  const key = `personal.shopping.issue.${issue.code}`;
  return i18n.te(key) ? i18n.t(key) : i18n.t("personal.shopping.issue.unknown", { code: issue.code });
}

/** The recipe and the detail of a problem, once each: the server often sends the same text in both. */
function issueSubject(issue: ShoppingPlanIssue): string {
  return [...new Set([issue.recipeName, issue.detail].filter(Boolean))].join(" · ");
}

/** Compute the plan again. The preview never writes anything. */
async function load() {
  loading.value = true;
  const [preview, stored] = await Promise.all([
    api.shoppingPlans.getPreview(planId.value),
    api.shoppingPlans.getLines(planId.value),
  ]);
  loading.value = false;

  if (!preview.data) {
    notFound.value = !plan.value;
    return;
  }
  plan.value = preview.data.plan;
  previewLines.value = preview.data.lines;
  issues.value = preview.data.issues;
  storedNames.value = Object.fromEntries((stored.data ?? []).map(line => [line.key, line.display]));
  if (!hasDismissed.value) {
    restoreDismissed.value = false;
  }
}

/** A recomputation asked by the user: the messages of the previous actions no longer describe what is shown. */
async function recompute() {
  applyResult.value = null;
  receiveResult.value = null;
  await load();
}

async function loadEventName() {
  if (plan.value?.sourceType !== "EVENT" || !plan.value.eventId) {
    return;
  }
  const { data } = await api.mealEvents.getOne(plan.value.eventId);
  eventName.value = data?.name ?? "";
}

async function loadRestrictions() {
  const { data } = await api.dietary.getRestrictions();
  restrictionNames.value = Object.fromEntries((data ?? []).map(restriction => [restriction.key, restriction.name]));
}

async function apply() {
  applying.value = true;
  const { data } = await api.shoppingPlans.apply(planId.value, { restoreDismissed: restoreDismissed.value });
  applying.value = false;
  if (!data) {
    return;
  }
  applyResult.value = data;
  receiveResult.value = null;
  plan.value = data.plan;
  await load();
}

async function receive() {
  if (!plan.value?.shoppingListId) {
    return;
  }
  receiving.value = true;
  const { data } = await api.pantry.receive(plan.value.shoppingListId);
  receiving.value = false;
  if (!data) {
    return;
  }
  receiveResult.value = data;
  applyResult.value = null;
  await load();
}

async function consume() {
  consuming.value = true;
  const { data } = await api.shoppingPlans.consume(planId.value);
  consuming.value = false;
  if (!data) {
    return;
  }
  consumedCount.value = data.consumed;
  plan.value = data.plan;
  await load();
}

function openEdit() {
  if (!plan.value) {
    return;
  }
  form.value = shoppingPlanFormFrom(plan.value);
  editDialog.value = true;
}

async function saveEdit() {
  if (!canSave.value) {
    return;
  }
  saving.value = true;
  const { data } = await api.shoppingPlans.updateOne(planId.value, shoppingPlanFormPayload(form.value));
  saving.value = false;
  if (!data) {
    return;
  }
  alert.success(i18n.t("personal.common.saved"));
  editDialog.value = false;
  applyResult.value = null;
  await load();
}

async function remove() {
  const { data } = await api.shoppingPlans.deleteOne(planId.value);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await router.push("/shopping-plans");
  }
}

onMounted(async () => {
  loadRestrictions();
  await load();
  await loadEventName();
});
</script>

<style scoped>
.plan-title {
  min-width: 0;
  overflow-wrap: anywhere;
}

/* A long label wraps on a narrow screen instead of widening the page. */
.plan-action {
  height: auto !important;
  min-height: 40px;
  padding-top: 8px;
  padding-bottom: 8px;
}

.plan-action :deep(.v-btn__content) {
  white-space: normal;
  text-align: left;
}
</style>
