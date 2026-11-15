<template>
  <div>
    <div class="d-flex align-center flex-wrap ga-2 mb-4">
      <span class="text-body-1">{{ $t('personal.events.review.menu-status') }}</span>
      <PersonalStatusChip
        v-if="analysis"
        :status="analysis.status"
      />
    </div>

    <!-- What breaks a restriction -->
    <h3 class="text-h6 mb-2">
      {{ $t('personal.events.review.blocking-title') }}
    </h3>
    <v-alert
      v-if="blocking.length"
      type="error"
      variant="tonal"
      class="mb-4"
      data-testid="review-blocking"
    >
      <p class="mb-2">
        {{ $t('personal.events.review.blocking-help', blocking.length) }}
      </p>
      <MealEventFindingList
        :findings="blocking"
        :restriction-names="restrictionNames"
        show-recipe
      />
    </v-alert>
    <v-alert
      v-else
      type="success"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="review-blocking-empty"
    >
      {{ $t('personal.events.review.blocking-empty') }}
    </v-alert>

    <!-- What nobody verified yet -->
    <h3 class="text-h6 mb-2">
      {{ $t('personal.events.review.to-verify-title') }}
    </h3>
    <v-alert
      v-if="toVerify.length"
      type="warning"
      variant="tonal"
      class="mb-4"
      data-testid="review-to-verify"
    >
      <p class="mb-2">
        {{ $t('personal.events.review.to-verify-help', toVerify.length) }}
      </p>
      <MealEventFindingList
        :findings="toVerify"
        :restriction-names="restrictionNames"
        show-recipe
        verify-links
      />
    </v-alert>
    <v-alert
      v-else
      type="success"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="review-to-verify-empty"
    >
      {{ $t('personal.events.review.to-verify-empty') }}
    </v-alert>

    <!-- What to do in the kitchen -->
    <h3 class="text-h6 mb-2">
      {{ $t('personal.events.review.checklist-title') }}
    </h3>
    <p
      v-if="!checklist.length"
      class="text-body-2 text-medium-emphasis mb-4"
    >
      {{ $t('personal.events.review.checklist-empty') }}
    </p>
    <div
      v-else
      class="mb-4"
      data-testid="review-checklist"
    >
      <p class="text-caption text-medium-emphasis mb-1">
        {{ $t('personal.events.review.checklist-help') }}
      </p>
      <v-checkbox
        v-for="item in checklist"
        :key="item.key"
        v-model="ticked"
        :value="item.key"
        color="primary"
        density="compact"
        hide-details
        class="checklist-item"
        data-testid="review-checklist-item"
      >
        <template #label>
          <span :class="ticked.includes(item.key) ? 'text-decoration-line-through text-medium-emphasis' : 'text-high-emphasis'">
            {{ item.text }}
            <span
              v-if="item.restriction"
              class="text-caption text-medium-emphasis"
            > · {{ item.restriction }}</span>
          </span>
        </template>
      </v-checkbox>
    </div>

    <v-divider class="my-4" />

    <!-- Plan the event -->
    <div class="d-flex align-center flex-wrap ga-2 mb-2">
      <h3 class="text-h6">
        {{ $t('personal.events.review.status-title') }}
      </h3>
      <MealEventStatusChip :status="event.status" />
    </div>

    <template v-if="event.status !== 'PLANNED'">
      <v-alert
        v-if="planBlocker"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        data-testid="review-plan-blocker"
      >
        {{ planBlocker }}
      </v-alert>
      <v-checkbox
        v-else-if="toVerify.length"
        v-model="acknowledged"
        color="warning"
        density="compact"
        hide-details
        class="mb-3 checklist-item"
        data-testid="event-acknowledge"
      >
        <template #label>
          <span class="text-high-emphasis">{{ $t('personal.events.review.acknowledge', toVerify.length) }}</span>
        </template>
      </v-checkbox>
    </template>
    <p
      v-else
      class="text-body-2 text-medium-emphasis"
    >
      {{ $t('personal.events.review.planned-help') }}
    </p>

    <div class="d-flex flex-column flex-sm-row flex-wrap ga-2">
      <v-btn
        v-if="event.status !== 'PLANNED'"
        color="success"
        :prepend-icon="mdiCalendarCheck"
        :disabled="!canPlan"
        :loading="changing === 'PLANNED'"
        data-testid="event-plan"
        @click="setStatus('PLANNED')"
      >
        {{ $t('personal.events.review.plan') }}
      </v-btn>
      <v-btn
        v-if="event.status !== 'DONE'"
        :variant="event.status === 'PLANNED' ? 'elevated' : 'text'"
        :color="event.status === 'PLANNED' ? 'info' : undefined"
        :prepend-icon="$globals.icons.check"
        :loading="changing === 'DONE'"
        data-testid="event-done"
        @click="setStatus('DONE')"
      >
        {{ $t('personal.events.review.mark-done') }}
      </v-btn>
      <v-btn
        v-if="event.status !== 'DRAFT'"
        variant="text"
        :loading="changing === 'DRAFT'"
        data-testid="event-draft"
        @click="setStatus('DRAFT')"
      >
        {{ $t('personal.events.review.back-to-draft') }}
      </v-btn>
    </div>

    <v-divider class="my-4" />

    <!-- Shopping -->
    <h3 class="text-h6 mb-2">
      {{ $t('personal.events.review.shopping-title') }}
    </h3>
    <p class="text-body-2 text-medium-emphasis">
      {{ $t('personal.events.review.shopping-help') }}
    </p>
    <v-btn
      color="primary"
      :prepend-icon="personalIcons.shopping"
      :loading="shopping"
      data-testid="event-shopping"
      @click="generateShopping"
    >
      {{ $t('personal.events.review.shopping') }}
    </v-btn>

    <v-divider class="my-4" />

    <!-- History -->
    <v-expansion-panels data-testid="event-history">
      <v-expansion-panel>
        <v-expansion-panel-title>
          {{ $t('personal.events.review.history-title') }} ({{ history.length }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-caption text-medium-emphasis">
            {{ $t('personal.events.review.history-help') }}
          </p>
          <div
            v-for="entry in history"
            :key="entry.id"
            class="py-1 history-entry"
            data-testid="event-history-entry"
          >
            <div class="text-caption text-medium-emphasis">
              {{ entry.createdAt ? $d(new Date(entry.createdAt), 'long') : '' }}
            </div>
            <div class="text-body-2">
              {{ entry.label }}
              <span v-if="entry.subject"> : {{ entry.subject }}</span>
            </div>
            <div
              v-if="entry.reason"
              class="text-body-2 text-medium-emphasis"
            >
              {{ $t('personal.common.reason') }} : {{ entry.reason }}
            </div>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <div class="d-flex flex-wrap ga-2 mt-6">
      <BaseButton
        edit
        data-testid="event-edit"
        @click="emit('edit')"
      >
        {{ $t('personal.events.edit') }}
      </BaseButton>
      <BaseButton
        delete
        data-testid="event-delete"
        @click="emit('delete')"
      >
        {{ $t('personal.events.delete') }}
      </BaseButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { mdiCalendarCheck } from "@mdi/js";
import MealEventFindingList from "~/components/Domain/MealEvent/MealEventFindingList.vue";
import MealEventStatusChip from "~/components/Domain/MealEvent/MealEventStatusChip.vue";
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { MealEventAnalysisOut, MealEventOut, MealEventStatus } from "~/lib/api/types/personal";

const props = defineProps<{
  event: MealEventOut;
  analysis: MealEventAnalysisOut | null;
  /** The name of each restriction, by its key. */
  restrictionNames: Record<string, string>;
}>();

const emit = defineEmits<{
  (e: "updated", event: MealEventOut): void;
  (e: "edit" | "delete"): void;
}>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const router = useRouter();

const acknowledged = ref(false);
const ticked = ref<string[]>([]);
const changing = ref<MealEventStatus | null>(null);
const shopping = ref(false);

const blocking = computed(() => props.analysis?.blocking ?? []);
const toVerify = computed(() => props.analysis?.toVerify ?? []);

const checklist = computed(() =>
  (props.analysis?.checklist ?? []).map(item => ({
    key: `${item.code}|${item.restrictionKey}|${item.subject}`,
    text: text.checklist(item),
    restriction: props.restrictionNames[item.restrictionKey] ?? "",
  })),
);

// The list of unverified items changed: what the user confirmed no longer covers it.
watch(
  () => toVerify.value.length,
  () => {
    acknowledged.value = false;
  },
);

/** Why the event cannot be planned yet, in the order in which the user fixes it. */
const planBlocker = computed(() => {
  const analysis = props.analysis;
  if (!analysis || analysis.canPlan) {
    return "";
  }
  if (analysis.totalPersons === 0) {
    return i18n.t("personal.events.review.blocker-no-guest");
  }
  if (!analysis.menu.some(item => item.variants.length)) {
    return i18n.t("personal.events.review.blocker-no-menu");
  }
  return i18n.t("personal.events.review.blocker-blocking");
});

const canPlan = computed(() => !!props.analysis?.canPlan && (!toVerify.value.length || acknowledged.value));

const history = computed(() =>
  [...props.event.history]
    .sort((a, b) => (b.createdAt ?? "").localeCompare(a.createdAt ?? ""))
    .map((entry) => {
      const key = `personal.events.history.${entry.action}`;
      const detail = detailOf(entry.detail);
      return {
        id: entry.id,
        createdAt: entry.createdAt,
        label: i18n.te(key) ? i18n.t(key) : entry.action,
        subject: subjectOf(detail),
        reason: reasonOf(detail),
      };
    }),
);

/** The detail of an entry, which the server stores as JSON. */
function detailOf(detail: string | null): Record<string, unknown> {
  if (!detail) {
    return {};
  }
  try {
    const parsed: unknown = JSON.parse(detail);
    return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
  }
  catch {
    return {};
  }
}

/** The reason of an entry: the text that the user gave for an exception, or why the event went back to draft. */
function reasonOf(detail: Record<string, unknown>): string {
  if (typeof detail.reason !== "string") {
    return "";
  }
  const key = `personal.events.history-reason.${detail.reason}`;
  return i18n.te(key) ? i18n.t(key) : detail.reason;
}

/** The restriction and the scope of an exception. */
function subjectOf(detail: Record<string, unknown>): string {
  if (typeof detail.restriction !== "string" || typeof detail.scope !== "string") {
    return "";
  }
  const scopeKey = `personal.enums.scope.${detail.scope}`;
  const scope = i18n.te(scopeKey) ? i18n.t(scopeKey) : detail.scope;
  return `${props.restrictionNames[detail.restriction] ?? detail.restriction} · ${scope}`;
}

async function setStatus(status: MealEventStatus) {
  if (changing.value) {
    return;
  }
  changing.value = status;
  const { data } = await api.mealEvents.setStatus(props.event.id, {
    status,
    acknowledgeUnverified: status === "PLANNED" && acknowledged.value,
  });
  changing.value = null;
  if (data) {
    alert.success(i18n.t(`personal.events.review.status-set.${status}`));
    emit("updated", data);
  }
}

async function generateShopping() {
  if (shopping.value) {
    return;
  }
  shopping.value = true;
  const { data } = await api.shoppingPlans.createOne({
    name: props.event.name,
    sourceType: "EVENT",
    eventId: props.event.id,
  });
  shopping.value = false;
  if (data) {
    await router.push(`/shopping-plans/${data.id}`);
  }
}
</script>

<style scoped>
/* The label wraps instead of widening the page on a phone. */
.checklist-item :deep(.v-label) {
  white-space: normal;
  opacity: 1;
}

.checklist-item :deep(.v-selection-control) {
  align-items: flex-start;
  min-height: 0;
}

.history-entry + .history-entry {
  border-top: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
}
</style>
