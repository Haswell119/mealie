<template>
  <BaseDialog
    v-model="dialog"
    :title="event ? $t('personal.events.edit') : $t('personal.events.new')"
    :icon="personalIcons.events"
    max-width="600"
    width="100%"
    can-submit
    :submit-text="event ? $t('personal.common.save') : $t('personal.events.create')"
    :submit-disabled="!canSave"
    :loading="saving"
    disable-submit-on-enter
    keep-open
    @submit="save"
  >
    <v-card-text>
      <v-text-field
        v-model="form.name"
        :label="$t('personal.events.form.name')"
        autofocus
        data-testid="event-name"
      />
      <v-text-field
        v-model="form.startsAt"
        type="datetime-local"
        :label="$t('personal.events.form.starts-at')"
        clearable
        data-testid="event-starts-at"
      />
      <v-text-field
        v-model="form.location"
        :label="$t('personal.events.form.location')"
        data-testid="event-location"
      />
      <v-select
        v-model="form.cookPersonId"
        :items="cookItems"
        :label="$t('personal.events.form.cook')"
        :hint="$t('personal.events.form.cook-help')"
        persistent-hint
        clearable
        class="mb-4"
        data-testid="event-cook"
      />
      <v-text-field
        v-model.number="form.leftoverPortions"
        type="number"
        min="0"
        step="0.5"
        inputmode="decimal"
        :label="$t('personal.events.form.leftover-portions')"
        :hint="$t('personal.events.form.leftover-portions-help')"
        persistent-hint
        :error="!leftoversValid"
        class="mb-4"
        data-testid="event-leftovers"
      />
      <v-textarea
        v-model="form.notes"
        :label="$t('personal.common.notes')"
        rows="2"
        auto-grow
        data-testid="event-notes"
      />
    </v-card-text>
  </BaseDialog>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type { MealEventCreate, MealEventOut, PersonOut } from "~/lib/api/types/personal";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    persons: PersonOut[];
    /** The event to edit. Without it, the dialog creates an event. */
    event?: MealEventOut | null;
  }>(),
  { event: null },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "saved", event: MealEventOut): void;
}>();

interface EventForm {
  name: string;
  startsAt: string | null;
  location: string;
  cookPersonId: string | null;
  leftoverPortions: number | string;
  notes: string;
}

const i18n = useI18n();
const api = usePersonalApi();
const auth = useMealieAuth();

const dialog = computed({
  get: () => props.modelValue,
  set: value => emit("update:modelValue", value),
});

const saving = ref(false);
const form = ref<EventForm>(emptyForm());

const cookItems = computed(() => props.persons.map(person => ({ value: person.id, title: person.displayName })));
const leftovers = computed(() => (form.value.leftoverPortions === "" ? 0 : Number(form.value.leftoverPortions)));
const leftoversValid = computed(() => Number.isFinite(leftovers.value) && leftovers.value >= 0);
const canSave = computed(() => !!form.value.name.trim() && leftoversValid.value);

function emptyForm(): EventForm {
  return { name: "", startsAt: null, location: "", cookPersonId: null, leftoverPortions: 0, notes: "" };
}

/** The value that an `<input type="datetime-local">` expects: local time, without a time zone. */
function toLocalInput(iso: string | null): string | null {
  if (!iso) {
    return null;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toIso(local: string | null): string | null {
  if (!local) {
    return null;
  }
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** The cook is the user by default: the person linked to their account. */
function defaultCookId(): string | null {
  const linked = props.persons.filter(person => person.linkedUserId);
  const me = linked.find(person => person.linkedUserId === auth.user.value?.id) ?? linked[0];
  return me?.id ?? null;
}

function reset() {
  const event = props.event;
  form.value = event
    ? {
        name: event.name,
        startsAt: toLocalInput(event.startsAt),
        location: event.location ?? "",
        cookPersonId: event.cookPersonId,
        leftoverPortions: event.leftoverPortions,
        notes: event.notes ?? "",
      }
    : { ...emptyForm(), cookPersonId: defaultCookId() };
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      reset();
    }
  },
  { immediate: true },
);

// The persons can arrive after the dialog opens: the default cook is set as soon as they are known.
watch(
  () => props.persons,
  () => {
    if (props.modelValue && !props.event && !form.value.cookPersonId) {
      form.value.cookPersonId = defaultCookId();
    }
  },
);

async function save() {
  if (!canSave.value || saving.value) {
    return;
  }
  const payload: MealEventCreate = {
    name: form.value.name.trim(),
    startsAt: toIso(form.value.startsAt),
    location: form.value.location.trim() || null,
    cookPersonId: form.value.cookPersonId || null,
    leftoverPortions: leftovers.value,
    notes: form.value.notes.trim() || null,
  };

  saving.value = true;
  const { data } = props.event
    ? await api.mealEvents.updateOne(props.event.id, payload)
    : await api.mealEvents.createOne(payload);
  saving.value = false;

  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    dialog.value = false;
    emit("saved", data);
  }
}
</script>
