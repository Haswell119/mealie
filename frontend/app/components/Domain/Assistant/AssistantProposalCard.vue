<template>
  <v-card
    variant="outlined"
    class="assistant-proposal"
    data-testid="assistant-proposal"
    :data-kind="proposal.kind"
    :data-status="proposal.status"
  >
    <div class="d-flex align-start ga-2 pa-3 pb-1">
      <v-icon
        color="primary"
        class="mt-1"
        :icon="kindIcon"
      />
      <div class="assistant-proposal__grow">
        <div
          class="text-subtitle-1 font-weight-medium assistant-proposal__wrap"
          data-testid="assistant-proposal-title"
        >
          {{ proposal.title }}
        </div>
        <div class="text-caption text-medium-emphasis">
          {{ $t(`personal.assistant.kind.${proposal.kind}`) }}
          <span v-if="proposal.createdAt"> · {{ $d(new Date(proposal.createdAt), 'short') }}</span>
        </div>
      </div>
      <v-chip
        :color="statusColor"
        size="small"
        variant="flat"
        label
        class="flex-shrink-0"
        data-testid="assistant-proposal-status"
      >
        {{ $t(`personal.assistant.status.${proposal.status}`) }}
      </v-chip>
    </div>

    <v-card-text class="pt-2 pb-2">
      <!-- Shopping list -->
      <template v-if="proposal.kind === 'SHOPPING_LIST'">
        <div
          v-if="!shoppingLines.length"
          class="text-medium-emphasis mb-0"
        >
          {{ $t('personal.assistant.shopping.empty') }}
        </div>
        <ul class="assistant-proposal__list">
          <li
            v-for="(line, index) in shownShoppingLines"
            :key="index"
            class="py-1"
            data-testid="assistant-proposal-line"
          >
            <div class="d-flex flex-wrap align-baseline gc-2">
              <span class="font-weight-medium assistant-proposal__wrap">{{ line.item }}</span>
              <span>{{ line.toBuy === 0
                ? $t('personal.assistant.shopping.nothing-to-buy')
                : $t('personal.assistant.shopping.to-buy', { quantity: amount(line.toBuy, line.unit) }) }}</span>
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ $t('personal.assistant.shopping.needed', { quantity: amount(line.needed, line.unit) }) }}
              · {{ $t('personal.assistant.shopping.from-stock', { quantity: amount(line.fromStock, line.unit) }) }}
            </div>
            <AssistantProposalChecks
              :checks="line.checks"
              :restriction-names="restrictionNames"
            />
          </li>
        </ul>
        <v-btn
          v-if="shoppingLines.length > collapsedLines"
          variant="text"
          size="small"
          class="px-0"
          @click="expanded = !expanded"
        >
          {{ expanded
            ? $t('personal.assistant.show-less')
            : $t('personal.assistant.show-all', { count: shoppingLines.length }) }}
        </v-btn>
      </template>

      <!-- Variant of a recipe -->
      <template v-else-if="proposal.kind === 'RECIPE_VARIANT' || proposal.kind === 'SUBSTITUTION'">
        <div
          v-if="variant.recipeName"
          class="mb-2"
        >
          {{ $t('personal.assistant.variant.of', { recipe: variant.recipeName }) }}
          <span v-if="variant.title"> · {{ variant.title }}</span>
        </div>
        <ul class="assistant-proposal__list">
          <li
            v-for="(substitution, index) in variant.substitutions"
            :key="index"
            class="py-1"
            data-testid="assistant-proposal-substitution"
          >
            <div class="assistant-proposal__wrap">
              <span class="text-decoration-line-through text-medium-emphasis">{{ substitution.ingredient }}</span>
              <v-icon
                size="small"
                class="mx-1"
                :icon="$globals.icons.arrowRightBold"
              />
              <span class="font-weight-medium">{{ substitution.replacement }}</span>
            </div>
            <div
              v-if="substitution.reason"
              class="text-caption text-medium-emphasis assistant-proposal__wrap"
            >
              {{ substitution.reason }}
            </div>
            <AssistantProposalChecks
              :checks="substitution.checks"
              :restriction-names="restrictionNames"
            />
          </li>
        </ul>
        <div
          v-if="variant.notes"
          class="text-body-2 mt-2 mb-0 assistant-proposal__text"
        >
          {{ variant.notes }}
        </div>
      </template>

      <!-- Menu -->
      <template v-else-if="proposal.kind === 'MENU'">
        <ul class="assistant-proposal__list">
          <li
            v-for="(item, index) in menuItems"
            :key="index"
            class="py-1"
            data-testid="assistant-proposal-menu-item"
          >
            <div class="text-caption text-medium-emphasis">
              {{ courseName(item.course) }}
            </div>
            <div class="assistant-proposal__wrap">
              <span class="font-weight-medium">{{ item.recipeName }}</span>
              <span v-if="item.label"> · {{ item.label }}</span>
            </div>
            <AssistantProposalChecks
              :checks="item.checks"
              :restriction-names="restrictionNames"
            />
          </li>
        </ul>
      </template>

      <!-- Draft of a recipe -->
      <template v-else-if="proposal.kind === 'RECIPE_DRAFT'">
        <div class="font-weight-medium assistant-proposal__wrap">
          {{ recipeDraft.name }}
        </div>
        <div
          v-if="recipeDraft.description"
          class="text-body-2 mb-1 assistant-proposal__text"
        >
          {{ recipeDraft.description }}
        </div>
        <div class="text-body-2 mb-2">
          {{ recipeDraft.servings
            ? $t('personal.assistant.draft.servings', { count: text.quantity(recipeDraft.servings) })
            : $t('personal.assistant.draft.no-servings') }}
        </div>
        <template v-if="recipeDraft.ingredients.length">
          <div class="text-caption text-medium-emphasis">
            {{ $t('personal.assistant.draft.ingredients') }}
          </div>
          <ul class="assistant-proposal__bullets mb-2">
            <li
              v-for="(ingredient, index) in recipeDraft.ingredients"
              :key="index"
              class="assistant-proposal__wrap"
            >
              {{ ingredient }}
            </li>
          </ul>
        </template>
        <template v-if="recipeDraft.instructions.length">
          <div class="text-caption text-medium-emphasis">
            {{ $t('personal.assistant.draft.instructions') }}
          </div>
          <ol class="assistant-proposal__bullets mb-2">
            <li
              v-for="(step, index) in recipeDraft.instructions"
              :key="index"
              class="assistant-proposal__wrap"
            >
              {{ step }}
            </li>
          </ol>
        </template>
        <div
          v-if="recipeDraft.notes"
          class="text-body-2 mb-0 assistant-proposal__text"
        >
          {{ recipeDraft.notes }}
        </div>
      </template>

      <!-- Pending: the user decides -->
      <template v-if="proposal.status === 'PENDING'">
        <div
          class="text-caption text-medium-emphasis mt-3 mb-0"
          data-testid="assistant-proposal-hint"
        >
          {{ $t(`personal.assistant.accept-hint.${proposal.kind}`) }}
        </div>
      </template>

      <!-- Accepted: where the change went -->
      <template v-else-if="proposal.status === 'ACCEPTED'">
        <v-divider class="my-3" />
        <div
          v-if="resultSummary"
          class="text-body-2 mb-2"
          data-testid="assistant-proposal-result"
        >
          {{ resultSummary }}
        </div>
        <v-alert
          v-if="unmatched.length"
          type="warning"
          variant="tonal"
          density="compact"
          class="mb-2"
        >
          {{ $t('personal.assistant.result.unmatched', { ingredients: unmatched.join(', ') }) }}
        </v-alert>
        <div class="d-flex flex-wrap ga-2">
          <v-btn
            v-for="link in resultLinks"
            :key="link.to"
            :to="link.to"
            size="small"
            variant="tonal"
            color="primary"
            :prepend-icon="link.icon"
            data-testid="assistant-proposal-link"
          >
            {{ link.label }}
          </v-btn>
        </div>
      </template>
    </v-card-text>

    <v-card-actions
      v-if="proposal.status === 'PENDING' || deletable"
      class="flex-wrap px-3 pb-3"
    >
      <template v-if="proposal.status === 'PENDING'">
        <v-btn
          color="success"
          variant="flat"
          :loading="busy === 'accept'"
          :disabled="!!busy"
          :prepend-icon="$globals.icons.check"
          data-testid="assistant-proposal-accept"
          @click="accept"
        >
          {{ $t('personal.assistant.accept') }}
        </v-btn>
        <v-btn
          variant="tonal"
          :loading="busy === 'reject'"
          :disabled="!!busy"
          :prepend-icon="$globals.icons.close"
          data-testid="assistant-proposal-reject"
          @click="reject"
        >
          {{ $t('personal.assistant.reject') }}
        </v-btn>
      </template>
      <template v-else>
        <v-spacer />
        <v-btn
          variant="text"
          size="small"
          :loading="busy === 'delete'"
          :disabled="!!busy"
          :prepend-icon="$globals.icons.delete"
          data-testid="assistant-proposal-delete"
          @click="remove"
        >
          {{ $t('personal.common.delete') }}
        </v-btn>
      </template>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { mdiSilverwareForkKnife, mdiSwapHorizontal } from "@mdi/js";
import AssistantProposalChecks from "~/components/Domain/Assistant/AssistantProposalChecks.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { AiProposalKind, AiProposalOut, VerificationStatus } from "~/lib/api/types/personal";

/**
 * One change that the assistant suggests.
 *
 * The assistant never changes data: the change happens when the user accepts the proposal here.
 * `payload` and `result` are free JSON with snake_case keys, so every value is read defensively.
 */
const props = defineProps<{
  proposal: AiProposalOut;
  /** Names of the dietary restrictions by key, e.g. `gluten` → `Sans gluten`. */
  restrictionNames?: Record<string, string>;
  /** Show a delete button once the proposal is accepted or rejected. */
  deletable?: boolean;
}>();
const emit = defineEmits<{
  (e: "updated", proposal: AiProposalOut): void;
  (e: "deleted", id: string): void;
}>();

type Json = Record<string, unknown>;
interface Check {
  restriction: string;
  status: VerificationStatus;
}

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const auth = useMealieAuth();

const busy = ref<"" | "accept" | "reject" | "delete">("");
const expanded = ref(false);
const collapsedLines = 6;

// ================================================================
// Reading free JSON

function record(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : {};
}
function list(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
function str(value: unknown): string {
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : "";
}
function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
function toCheck(restriction: unknown, status: unknown): Check | null {
  const key = str(restriction);
  if (!key || (status !== "VERIFIED" && status !== "UNVERIFIED" && status !== "INCOMPATIBLE")) {
    return null;
  }
  return { restriction: key, status };
}
function present<T>(value: T | null): value is T {
  return value !== null;
}

const payload = computed(() => record(props.proposal.payload));
const result = computed(() => record(props.proposal.result));

// ================================================================
// Payload of each kind

const shoppingLines = computed(() =>
  list(payload.value.lines).map(record).map(line => ({
    item: str(line.item),
    needed: num(line.needed),
    fromStock: num(line.from_stock),
    toBuy: num(line.to_buy),
    unit: str(line.unit),
    // "gluten:UNVERIFIED"
    checks: list(line.to_check)
      .map((entry) => {
        const [restriction, status] = str(entry).split(":");
        return toCheck(restriction, status);
      })
      .filter(present),
  })),
);
const shownShoppingLines = computed(() =>
  expanded.value ? shoppingLines.value : shoppingLines.value.slice(0, collapsedLines),
);

const variant = computed(() => {
  const checks = list(payload.value.checks).map(record);
  return {
    recipeName: str(payload.value.recipe_name),
    title: str(payload.value.title),
    notes: str(payload.value.notes),
    substitutions: list(payload.value.substitutions).map(record).map((substitution) => {
      const replacement = str(substitution.replacement);
      return {
        ingredient: str(substitution.ingredient),
        replacement,
        reason: str(substitution.reason),
        checks: checks
          .filter(entry => str(entry.replacement) === replacement)
          .map(entry => toCheck(entry.restriction, entry.status))
          .filter(present),
      };
    }),
  };
});

const menuItems = computed(() =>
  list(payload.value.items).map(record).map(item => ({
    course: str(item.course),
    recipeName: str(item.recipe_name),
    label: str(item.label),
    checks: Object.entries(record(item.statuses))
      .map(([restriction, status]) => toCheck(restriction, status))
      .filter(present),
  })),
);

const recipeDraft = computed(() => {
  const draft = record(payload.value.draft);
  return {
    name: str(draft.name),
    description: str(draft.description),
    servings: num(draft.recipe_servings),
    ingredients: list(draft.ingredients).map(str).filter(Boolean),
    instructions: list(draft.instructions).map(str).filter(Boolean),
    notes: str(draft.notes),
  };
});

// ================================================================
// Texts

const kindIcons: Record<AiProposalKind, string> = {
  SHOPPING_LIST: personalIcons.shopping,
  RECIPE_VARIANT: mdiSwapHorizontal,
  SUBSTITUTION: mdiSwapHorizontal,
  MENU: mdiSilverwareForkKnife,
  RECIPE_DRAFT: personalIcons.inspirations,
};
const kindIcon = computed(() => kindIcons[props.proposal.kind] ?? personalIcons.assistant);

const statusColor = computed(() => ({ PENDING: "info", ACCEPTED: "success", REJECTED: "grey" })[props.proposal.status]);

function courseName(course: string): string {
  const key = `personal.enums.course.${course}`;
  return i18n.te(key) ? i18n.t(key) : course;
}

function amount(quantity: number | null, unit: string): string {
  if (quantity === null) {
    return "–";
  }
  return unit ? `${text.quantity(quantity)} ${unit}` : text.quantity(quantity);
}

// ================================================================
// Result of an accepted proposal

const unmatched = computed(() => list(result.value.unmatched).map(str).filter(Boolean));

const resultSummary = computed(() => {
  switch (props.proposal.kind) {
    case "SHOPPING_LIST":
      return i18n.t("personal.assistant.result.shopping", {
        created: num(result.value.created) ?? 0,
        updated: num(result.value.updated) ?? 0,
      });
    case "MENU":
      return i18n.t("personal.assistant.result.menu", num(result.value.added) ?? 0);
    case "RECIPE_DRAFT":
      return i18n.t("personal.assistant.result.draft");
    default:
      return i18n.t("personal.assistant.result.variant");
  }
});

const resultLinks = computed(() => {
  const links: { to: string; label: string; icon: string }[] = [];
  const id = (key: string) => encodeURIComponent(str(result.value[key]) || str(payload.value[key]));

  switch (props.proposal.kind) {
    case "SHOPPING_LIST":
      if (id("plan_id")) {
        links.push({
          to: `/shopping-plans/${id("plan_id")}`,
          label: i18n.t("personal.assistant.result.open-plan"),
          icon: personalIcons.shopping,
        });
      }
      if (id("shopping_list_id")) {
        links.push({
          to: `/shopping-lists/${id("shopping_list_id")}`,
          label: i18n.t("personal.assistant.result.open-shopping-list"),
          icon: personalIcons.shopping,
        });
      }
      break;
    case "MENU":
      if (id("event_id")) {
        links.push({
          to: `/events/${id("event_id")}`,
          label: i18n.t("personal.assistant.result.open-event"),
          icon: personalIcons.events,
        });
      }
      break;
    case "RECIPE_DRAFT":
      links.push({
        to: id("inspiration_id") ? `/inspirations?open=${id("inspiration_id")}` : "/inspirations",
        label: i18n.t("personal.assistant.result.open-inspirations"),
        icon: personalIcons.inspirations,
      });
      break;
    default: {
      const groupSlug = auth.user.value?.groupSlug;
      if (groupSlug && id("recipe_slug")) {
        links.push({
          to: `/g/${groupSlug}/r/${id("recipe_slug")}`,
          label: i18n.t("personal.assistant.result.open-recipe"),
          icon: mdiSilverwareForkKnife,
        });
      }
    }
  }
  return links;
});

// ================================================================
// Decisions

async function accept() {
  busy.value = "accept";
  const { data } = await api.assistant.acceptProposal(props.proposal.id);
  busy.value = "";
  if (data) {
    alert.success(i18n.t("personal.assistant.accepted"));
    emit("updated", data);
  }
}

async function reject() {
  busy.value = "reject";
  const { data } = await api.assistant.rejectProposal(props.proposal.id);
  busy.value = "";
  if (data) {
    emit("updated", data);
  }
}

async function remove() {
  busy.value = "delete";
  const { data } = await api.assistant.deleteProposal(props.proposal.id);
  busy.value = "";
  if (data) {
    emit("deleted", props.proposal.id);
  }
}
</script>

<style scoped>
.assistant-proposal__grow {
  flex: 1 1 auto;
  min-width: 0;
}

.assistant-proposal__wrap {
  overflow-wrap: anywhere;
}

.assistant-proposal__text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.assistant-proposal__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.assistant-proposal__list > li + li {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.assistant-proposal__bullets {
  padding-left: 1.25rem;
  margin: 0;
}
</style>
