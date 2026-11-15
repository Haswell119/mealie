<template>
  <v-card
    class="my-2 plan-line"
    :class="[`plan-line--${severity}`, { 'plan-line--muted': dismissed }]"
    variant="outlined"
    data-testid="plan-line"
    :data-line-state="line.state"
    :data-line-action="line.action"
  >
    <v-card-text class="pa-3">
      <div class="d-flex align-start flex-wrap ga-2">
        <span
          class="text-title-medium font-weight-medium flex-grow-1 plan-line-name"
          data-testid="plan-line-name"
        >
          {{ name }}
        </span>
        <v-chip
          v-if="actionColor && !dismissed"
          size="small"
          :color="actionColor"
          variant="tonal"
          label
          data-testid="plan-line-action"
        >
          {{ $t(`personal.shopping.action.${line.action}`) }}
        </v-chip>
      </div>
      <div
        v-if="line.foodName && line.note"
        class="text-body-small text-medium-emphasis mb-0"
      >
        {{ line.note }}
      </div>

      <div class="plan-line-numbers mt-2">
        <div data-testid="plan-line-need">
          <div class="text-body-small text-medium-emphasis">
            {{ $t('personal.shopping.detail.need') }}
          </div>
          <div class="text-body-large">
            {{ amount(line.quantityNeeded) }}
          </div>
        </div>
        <div data-testid="plan-line-stock">
          <div class="text-body-small text-medium-emphasis">
            {{ $t('personal.shopping.detail.in-stock') }}
          </div>
          <div class="text-body-large">
            {{ amount(line.quantityFromStock) }}
          </div>
        </div>
        <div data-testid="plan-line-buy">
          <div class="text-body-small text-medium-emphasis">
            {{ $t('personal.shopping.detail.to-buy') }}
          </div>
          <div class="text-body-large font-weight-bold">
            {{ amount(line.quantityToBuy) }}
          </div>
        </div>
      </div>

      <div
        v-if="line.packs"
        class="text-body-medium mt-2 d-flex align-center ga-1"
        data-testid="plan-line-packs"
      >
        <v-icon
          size="small"
          :icon="mdiPackageVariantClosed"
        />
        <span>
          {{ line.packLabel
            ? $t('personal.shopping.detail.packs', { count: line.packs, label: line.packLabel })
            : $t('personal.shopping.detail.packs-plain', { count: line.packs }) }}
        </span>
      </div>

      <div
        v-if="line.purchasedQuantity > 0"
        class="text-body-medium mt-2 d-flex align-center ga-1 text-success"
        data-testid="plan-line-purchased"
      >
        <v-icon
          size="small"
          :icon="mdiCartCheck"
        />
        <span>{{ $t('personal.shopping.detail.purchased', { quantity: amount(line.purchasedQuantity) }) }}</span>
      </div>

      <div
        v-if="line.action === 'UPDATE' && !dismissed"
        class="text-body-small text-medium-emphasis mt-2 mb-0"
      >
        {{ $t('personal.shopping.detail.list-quantity', { quantity: amount(line.itemQuantity) }) }}
      </div>

      <div
        v-for="warning in line.stockWarnings"
        :key="warning"
        class="text-body-medium mt-2 d-flex align-start ga-1 plan-line-warning"
        data-testid="plan-line-warning"
      >
        <v-icon
          size="small"
          color="warning"
          :icon="mdiAlertOutline"
        />
        <span>{{ $te(`personal.shopping.warning.${warning}`) ? $t(`personal.shopping.warning.${warning}`) : warning }}</span>
      </div>

      <div
        v-for="(check, index) in line.checks"
        :key="`${check.restrictionKey}-${index}`"
        class="d-flex align-center flex-wrap ga-2 mt-2 plan-line-check"
        :class="`plan-line-check--${check.status}`"
        data-testid="plan-line-check"
      >
        <PersonalStatusChip :status="status(check)" />
        <span class="text-body-medium">
          <span class="font-weight-medium">{{ restrictionNames[check.restrictionKey] ?? check.restrictionKey }}</span>
          · {{ finding(check) }}
        </span>
      </div>

      <div
        v-if="dismissed"
        class="text-body-medium font-italic mt-2 mb-0"
        data-testid="plan-line-dismissed"
      >
        {{ restoreDismissed ? $t('personal.shopping.detail.dismissed-restore') : $t('personal.shopping.detail.dismissed') }}
      </div>

      <template v-if="line.sources.length">
        <v-btn
          variant="text"
          size="small"
          class="mt-1 px-1"
          :append-icon="open ? mdiChevronUp : mdiChevronDown"
          :aria-expanded="open"
          data-testid="plan-line-provenance"
          @click="open = !open"
        >
          {{ $t('personal.shopping.detail.provenance') }} ({{ line.sources.length }})
        </v-btn>
        <v-expand-transition>
          <ul
            v-show="open"
            class="plan-line-sources text-body-medium"
          >
            <li
              v-for="(source, index) in line.sources"
              :key="index"
              data-testid="plan-line-source"
            >
              <span class="font-weight-medium">{{ source.recipeName ?? $t('personal.shopping.issue.RECIPE_NOT_FOUND') }}</span>
              {{ sourceScale(source) }}
              <span class="text-medium-emphasis">{{ sourceQuantity(source) }}</span>
            </li>
          </ul>
        </v-expand-transition>
      </template>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { mdiAlertOutline, mdiCartCheck, mdiChevronDown, mdiChevronUp, mdiPackageVariantClosed } from "@mdi/js";
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type {
  FindingCode,
  ShoppingPlanCheckOut,
  ShoppingPlanPreviewLine,
  ShoppingPlanSourceOut,
  VerificationStatus,
} from "~/lib/api/types/personal";

const props = withDefaults(
  defineProps<{
    line: ShoppingPlanPreviewLine;
    /** The name of each restriction, by key. */
    restrictionNames?: Record<string, string>;
    /** The name that the plan last stored for the line: a line that the plan no longer needs comes without one. */
    storedName?: string;
    restoreDismissed?: boolean;
  }>(),
  { restrictionNames: () => ({}), storedName: "", restoreDismissed: false },
);

const i18n = useI18n();
const text = usePersonalText();

const open = ref(false);

const name = computed(() => props.line.display || props.storedName || i18n.t("personal.shopping.detail.unnamed"));
const dismissed = computed(() => props.line.state === "DISMISSED");

const severity = computed(() => {
  if (props.line.checks.some(check => check.status === "INCOMPATIBLE")) {
    return "error";
  }
  if (props.line.checks.some(check => check.status === "UNVERIFIED") || props.line.stockWarnings.length) {
    return "warning";
  }
  return "none";
});

const actionColor = computed(() => ({ CREATE: "success", UPDATE: "info", DELETE: "error" })[props.line.action]);

function amount(value: number): string {
  return [text.quantity(value), props.line.unitName].filter(Boolean).join(" ");
}

/** "· label × 2": the variant of the recipe and how many times the plan prepares it. */
function sourceScale(source: ShoppingPlanSourceOut): string {
  const scale = i18n.t("personal.shopping.detail.source-scale", { scale: text.quantity(source.scale) });
  return source.label ? `· ${source.label} ${scale}` : scale;
}

/** "— 400 g (note)": what one preparation of the recipe asks for. */
function sourceQuantity(source: ShoppingPlanSourceOut): string {
  const quantity = [text.quantity(source.baseQuantity), source.unitName].filter(Boolean).join(" ");
  return source.note ? `— ${quantity} (${source.note})` : `— ${quantity}`;
}

function status(check: ShoppingPlanCheckOut): VerificationStatus {
  return check.status as VerificationStatus;
}

function finding(check: ShoppingPlanCheckOut): string {
  return text.finding({ code: check.code as FindingCode, term: check.term, detail: check.detail, personName: null });
}
</script>

<style scoped>
.plan-line {
  border-left-width: 4px;
}

.plan-line--error {
  border-left-color: rgb(var(--v-theme-error));
}

.plan-line--warning {
  border-left-color: rgb(var(--v-theme-warning));
}

.plan-line--muted {
  opacity: 0.6;
}

.plan-line-name {
  min-width: 0;
  overflow-wrap: anywhere;
}

.plan-line-numbers {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.plan-line-check {
  border-radius: 4px;
  padding: 4px 6px;
}

.plan-line-check--INCOMPATIBLE {
  background: rgba(var(--v-theme-error), 0.12);
}

.plan-line-check--UNVERIFIED {
  background: rgba(var(--v-theme-warning), 0.14);
}

.plan-line-sources {
  padding-left: 20px;
  margin: 4px 0 0;
}
</style>
