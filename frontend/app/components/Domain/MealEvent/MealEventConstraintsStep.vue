<template>
  <div>
    <BaseDialog
      v-model="dialog"
      :title="$t('personal.events.constraints.override-add')"
      :icon="personalIcons.dietary"
      max-width="600"
      width="100%"
      can-submit
      :submit-text="$t('personal.events.constraints.override-submit')"
      :submit-disabled="!canSubmit"
      :loading="saving"
      disable-submit-on-enter
      keep-open
      @submit="addOverride"
    >
      <v-card-text>
        <v-alert
          type="info"
          variant="tonal"
          density="compact"
          class="mb-4"
        >
          {{ $t('personal.events.constraints.override-history-notice') }}
        </v-alert>
        <v-select
          v-model="form.personId"
          :items="personItems"
          :label="$t('personal.events.constraints.override-person')"
          data-testid="override-person"
          @update:model-value="form.restrictionId = restrictionItems[0]?.value ?? null"
        />
        <v-select
          v-model="form.restrictionId"
          :items="restrictionItems"
          :label="$t('personal.people.restriction')"
          :disabled="!form.personId"
          :no-data-text="$t('personal.events.constraints.override-no-restriction')"
          data-testid="override-restriction"
        />
        <v-select
          v-model="form.scope"
          :items="scopeItems"
          :label="$t('personal.events.constraints.override-scope')"
          :hint="$t(`personal.enums.scope-help.${form.scope}`)"
          persistent-hint
          class="mb-4"
          data-testid="override-scope"
        />
        <v-select
          v-model="form.menuItemId"
          :items="menuItemItems"
          :label="$t('personal.events.constraints.override-menu-item')"
          :hint="$t('personal.events.constraints.override-menu-item-help')"
          persistent-hint
          clearable
          class="mb-4"
          data-testid="override-menu-item"
        />
        <v-textarea
          v-model="form.reason"
          :label="$t('personal.events.constraints.override-reason')"
          :hint="$t('personal.events.constraints.override-reason-help')"
          persistent-hint
          rows="2"
          auto-grow
          data-testid="override-reason"
        />
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="deleteDialog"
      :title="$t('general.confirm')"
      :icon="$globals.icons.alertCircle"
      color="error"
      can-confirm
      @confirm="removeOverride"
    >
      <v-card-text>
        {{ $t('personal.events.constraints.override-delete-confirm') }}
      </v-card-text>
    </BaseDialog>

    <p class="text-body-2 text-medium-emphasis mb-4">
      {{ $t('personal.events.constraints.help') }}
    </p>

    <h3 class="text-h6 mb-2">
      {{ $t('personal.events.constraints.shared-title') }}
    </h3>
    <v-alert
      v-if="!shared.length"
      type="success"
      variant="tonal"
      density="compact"
      class="mb-4"
      data-testid="constraints-shared-empty"
    >
      {{ $t('personal.events.constraints.shared-empty') }}
    </v-alert>
    <v-card
      v-for="constraint in shared"
      :key="constraint.restrictionKey"
      class="mb-3 left-warning-border"
      data-testid="constraint-shared"
    >
      <v-card-title class="d-flex align-center flex-wrap ga-2 text-wrap">
        <span>{{ constraint.restrictionName }}</span>
        <v-chip
          size="small"
          color="warning"
          variant="flat"
          label
        >
          {{ $t(`personal.enums.scope.${constraint.scope}`) }}
        </v-chip>
      </v-card-title>
      <v-card-text>
        <p class="mb-1">
          {{ $t(`personal.enums.scope-help.${constraint.scope}`) }}
        </p>
        <p class="text-body-2 text-medium-emphasis mb-0">
          {{ $t('personal.events.constraints.from', { names: constraint.personNames.join(', ') }) }}
          · {{ $t(`personal.enums.severity.${constraint.severity}`) }}
          · {{ originLabels(constraint) }}
        </p>
      </v-card-text>
    </v-card>

    <h3 class="text-h6 mt-6 mb-2">
      {{ $t('personal.events.constraints.individual-title') }}
    </h3>
    <p
      v-if="!individual.length"
      class="text-body-2 text-medium-emphasis"
      data-testid="constraints-individual-empty"
    >
      {{ $t('personal.events.constraints.individual-empty') }}
    </p>
    <v-card
      v-for="person in individual"
      :key="person.personId"
      variant="outlined"
      class="mb-2 pa-3"
      data-testid="constraint-individual"
    >
      <div class="font-weight-medium mb-1">
        {{ person.personName }}
      </div>
      <div
        v-for="constraint in person.constraints"
        :key="constraint.restrictionKey"
        class="text-body-2 py-1"
      >
        <v-chip
          size="small"
          variant="tonal"
          class="mr-1"
        >
          {{ constraint.restrictionName }}
        </v-chip>
        {{ $t(`personal.enums.scope-help.${constraint.scope}`) }}
        <span class="text-medium-emphasis">
          ({{ $t(`personal.enums.severity.${constraint.severity}`) }}, {{ originLabels(constraint) }})
        </span>
      </div>
    </v-card>

    <h3 class="text-h6 mt-6 mb-2">
      {{ $t('personal.events.constraints.overrides-title') }}
    </h3>
    <p class="text-body-2 text-medium-emphasis">
      {{ $t('personal.events.constraints.overrides-help') }}
    </p>
    <v-card
      v-for="override in event.overrides"
      :key="override.id"
      variant="outlined"
      class="mb-2 pa-3"
      data-testid="override-row"
    >
      <div class="d-flex align-start">
        <div class="flex-grow-1 override-text">
          <div class="font-weight-medium">
            {{ personNames[override.personId] ?? '' }} · {{ override.restriction.name }}
          </div>
          <div class="text-body-2">
            {{ $t(`personal.enums.scope.${override.scope}`) }}
            <span v-if="override.menuItemId">
              · {{ $t('personal.events.constraints.override-for-item', { item: menuItemLabels[override.menuItemId] ?? '' }) }}
            </span>
            <span v-else> · {{ $t('personal.events.constraints.override-for-event') }}</span>
          </div>
          <div class="text-body-2 text-medium-emphasis">
            {{ $t('personal.common.reason') }} : {{ override.reason }}
            <span v-if="override.createdAt"> · {{ $d(new Date(override.createdAt), 'short') }}</span>
          </div>
        </div>
        <v-btn
          icon
          size="small"
          variant="text"
          :aria-label="$t('personal.common.delete')"
          data-testid="override-delete"
          @click="askDelete(override.id)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </div>
    </v-card>
    <p
      v-if="!event.overrides.length"
      class="text-body-2 text-medium-emphasis"
    >
      {{ $t('personal.events.constraints.overrides-empty') }}
    </p>

    <v-btn
      variant="tonal"
      class="mt-2"
      :prepend-icon="$globals.icons.createAlt"
      :disabled="!personItems.length"
      data-testid="override-add"
      @click="openDialog"
    >
      {{ $t('personal.events.constraints.override-add') }}
    </v-btn>
    <p
      v-if="!personItems.length"
      class="text-caption text-medium-emphasis mt-2"
    >
      {{ $t('personal.events.constraints.override-nobody') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type {
  AppliedConstraintOut,
  MealEventAnalysisOut,
  MealEventOut,
  PersonOut,
  RestrictionScope,
} from "~/lib/api/types/personal";

const props = defineProps<{
  event: MealEventOut;
  persons: PersonOut[];
  analysis: MealEventAnalysisOut | null;
  /** The name of each person, by its id. */
  personNames: Record<string, string>;
  /** The label of each dish of the menu, by its id. */
  menuItemLabels: Record<string, string>;
}>();

const emit = defineEmits<{ (e: "updated", event: MealEventOut): void }>();

interface OverrideForm {
  personId: string | null;
  restrictionId: string | null;
  scope: RestrictionScope;
  menuItemId: string | null;
  reason: string;
}

const REASON_MIN_LENGTH = 3;

const i18n = useI18n();
const api = usePersonalApi();

const dialog = ref(false);
const deleteDialog = ref(false);
const deletingId = ref<string | null>(null);
const saving = ref(false);
const form = ref<OverrideForm>(emptyForm());

const shared = computed(() => props.analysis?.constraints.shared ?? []);
const individual = computed(() =>
  (props.analysis?.constraints.individual ?? []).filter(person => person.constraints.length),
);

/** The guests and the cook: the persons whose restrictions count for this event. */
const involved = computed(() => {
  const ids = new Set(props.event.guests.map(guest => guest.personId));
  if (props.event.cookPersonId) {
    ids.add(props.event.cookPersonId);
  }
  return props.persons.filter(person => ids.has(person.id));
});

const personItems = computed(() =>
  involved.value
    .filter(person => person.restrictions.length)
    .map(person => ({ value: person.id, title: person.displayName })),
);
const restrictionItems = computed(() => {
  const person = involved.value.find(candidate => candidate.id === form.value.personId);
  return (person?.restrictions ?? []).map(restriction => ({
    value: restriction.restrictionId,
    title: `${restriction.restriction.name} (${i18n.t(`personal.enums.scope.${restriction.defaultScope}`)})`,
  }));
});
const scopeItems = computed(() =>
  (["INDIVIDUAL", "ENTIRE_MEAL", "ENTIRE_PREPARATION"] as RestrictionScope[]).map(value => ({
    value,
    title: i18n.t(`personal.enums.scope.${value}`),
  })),
);
const menuItemItems = computed(() =>
  props.event.menuItems.map(item => ({ value: item.id, title: props.menuItemLabels[item.id] ?? "" })),
);

const canSubmit = computed(
  () => !!form.value.personId && !!form.value.restrictionId && form.value.reason.trim().length >= REASON_MIN_LENGTH,
);

function emptyForm(): OverrideForm {
  return { personId: null, restrictionId: null, scope: "INDIVIDUAL", menuItemId: null, reason: "" };
}

function originLabels(constraint: AppliedConstraintOut): string {
  return constraint.origins.map(origin => i18n.t(`personal.enums.origin.${origin}`)).join(", ");
}

function openDialog() {
  form.value = emptyForm();
  form.value.personId = personItems.value[0]?.value ?? null;
  form.value.restrictionId = restrictionItems.value[0]?.value ?? null;
  dialog.value = true;
}

async function addOverride() {
  if (!canSubmit.value || saving.value || !form.value.personId || !form.value.restrictionId) {
    return;
  }
  saving.value = true;
  const { data } = await api.mealEvents.addOverride(props.event.id, {
    personId: form.value.personId,
    restrictionId: form.value.restrictionId,
    scope: form.value.scope,
    menuItemId: form.value.menuItemId || null,
    reason: form.value.reason.trim(),
  });
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.events.constraints.override-saved"));
    dialog.value = false;
    emit("updated", data);
  }
}

function askDelete(id: string) {
  deletingId.value = id;
  deleteDialog.value = true;
}

async function removeOverride() {
  if (!deletingId.value) {
    return;
  }
  const { data } = await api.mealEvents.deleteOverride(props.event.id, deletingId.value);
  deletingId.value = null;
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    emit("updated", data);
  }
}
</script>

<style scoped>
.override-text {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
