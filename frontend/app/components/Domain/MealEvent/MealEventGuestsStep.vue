<template>
  <div>
    <v-alert
      variant="tonal"
      color="primary"
      :icon="personalIcons.people"
      class="mb-4"
      data-testid="guests-summary"
    >
      <div class="font-weight-medium">
        {{ $t('personal.events.guests.summary-persons', analysis?.totalPersons ?? 0) }}
        · {{ $t('personal.events.guests.summary-portions', { portions: text.quantity(analysis?.totalPortions ?? 0) }) }}
      </div>
      <div
        v-if="event.leftoverPortions > 0"
        class="text-caption"
      >
        {{ $t('personal.events.guests.summary-leftovers', { portions: text.quantity(event.leftoverPortions) }) }}
      </div>
    </v-alert>

    <p class="text-body-2 text-medium-emphasis mb-3">
      {{ $t('personal.events.guests.help') }}
    </p>

    <v-alert
      v-if="!rows.length"
      type="info"
      variant="tonal"
      class="mb-3"
    >
      {{ $t('personal.events.guests.no-person') }}
    </v-alert>

    <v-card
      v-for="row in rows"
      :key="row.personId"
      variant="outlined"
      class="mb-2 px-2 py-1"
      data-testid="guest-row"
      :data-person="row.name"
    >
      <div class="d-flex align-center">
        <v-checkbox
          v-model="row.invited"
          color="primary"
          density="compact"
          hide-details
          class="flex-grow-1 guest-checkbox"
          data-testid="guest-invite"
          @update:model-value="onInvite(row)"
        >
          <template #label>
            <span class="d-flex align-center flex-wrap ga-1">
              <span class="font-weight-medium text-high-emphasis mr-1">{{ row.name }}</span>
              <v-chip
                v-if="row.personId === event.cookPersonId"
                size="x-small"
                color="primary"
                variant="tonal"
              >
                {{ $t('personal.events.cook-badge') }}
              </v-chip>
              <v-chip
                v-for="restriction in row.restrictions"
                :key="restriction"
                size="x-small"
                color="warning"
                variant="tonal"
              >
                {{ restriction }}
              </v-chip>
            </span>
          </template>
        </v-checkbox>
      </div>
      <v-row
        v-if="row.invited"
        density="compact"
        align="center"
        class="mt-0 mb-1 pl-2"
      >
        <v-col
          cols="12"
          sm="5"
        >
          <v-switch
            v-model="row.attending"
            color="primary"
            density="compact"
            hide-details
            :label="row.attending ? $t('personal.events.guests.attending') : $t('personal.events.guests.not-attending')"
            data-testid="guest-attending"
          />
        </v-col>
        <v-col
          cols="12"
          sm="7"
        >
          <v-select
            :model-value="row.appetiteOverride ?? row.appetite"
            :items="appetiteItems(row)"
            :label="$t('personal.events.guests.appetite')"
            :disabled="!row.attending"
            density="compact"
            hide-details
            data-testid="guest-appetite"
            @update:model-value="setAppetite(row, $event)"
          />
        </v-col>
      </v-row>
    </v-card>

    <v-alert
      v-if="dirty"
      type="warning"
      variant="tonal"
      density="compact"
      class="my-3"
    >
      {{ $t('personal.events.unsaved') }}
    </v-alert>

    <div class="d-flex flex-wrap align-center ga-2 mt-4">
      <v-btn
        variant="text"
        to="/people"
        :prepend-icon="$globals.icons.createAlt"
        data-testid="guests-add-person"
      >
        {{ $t('personal.events.guests.add-person') }}
      </v-btn>
      <v-spacer />
      <BaseButton
        save
        :disabled="!dirty"
        :loading="saving"
        data-testid="guests-save"
        @click="save"
      >
        {{ $t('personal.events.guests.save') }}
      </BaseButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { Appetite, MealEventAnalysisOut, MealEventGuestCreate, MealEventOut, PersonOut } from "~/lib/api/types/personal";

const props = defineProps<{
  event: MealEventOut;
  persons: PersonOut[];
  analysis: MealEventAnalysisOut | null;
}>();

const emit = defineEmits<{ (e: "updated", event: MealEventOut): void }>();

interface GuestRow {
  personId: string;
  name: string;
  appetite: Appetite;
  restrictions: string[];
  invited: boolean;
  attending: boolean;
  appetiteOverride: Appetite | null;
}

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();

const rows = ref<GuestRow[]>([]);
const saving = ref(false);

/** One row for each person of the household, with the saved state of the event. */
function savedRows(): GuestRow[] {
  const guests = new Map(props.event.guests.map(guest => [guest.personId, guest]));
  const result: GuestRow[] = props.persons.map((person) => {
    const guest = guests.get(person.id);
    return {
      personId: person.id,
      name: person.displayName,
      appetite: person.appetite,
      restrictions: person.restrictions.map(restriction => restriction.restriction.name),
      invited: !!guest,
      attending: guest?.attending ?? true,
      appetiteOverride: guest?.appetiteOverride ?? null,
    };
  });

  // A guest stays visible even when the list of persons does not hold it.
  const known = new Set(props.persons.map(person => person.id));
  for (const guest of props.event.guests) {
    if (!known.has(guest.personId)) {
      result.push({
        personId: guest.personId,
        name: guest.person.displayName,
        appetite: guest.person.appetite,
        restrictions: [],
        invited: true,
        attending: guest.attending,
        appetiteOverride: guest.appetiteOverride,
      });
    }
  }
  return result;
}

function payloadOf(list: GuestRow[]): MealEventGuestCreate[] {
  return list
    .filter(row => row.invited)
    .map(row => ({ personId: row.personId, attending: row.attending, appetiteOverride: row.appetiteOverride }));
}

const savedPayload = computed(() => JSON.stringify(payloadOf(savedRows())));
const dirty = computed(() => JSON.stringify(payloadOf(rows.value)) !== savedPayload.value);

// The rows follow the saved guests. A change elsewhere in the event leaves unsaved choices alone.
watch(
  () => JSON.stringify(savedRows()),
  () => {
    rows.value = savedRows();
  },
  { immediate: true },
);

function appetiteItems(row: GuestRow) {
  return (["SMALL", "NORMAL", "LARGE"] as Appetite[]).map(value => ({
    value,
    title:
      value === row.appetite
        ? i18n.t("personal.events.guests.appetite-default", { appetite: i18n.t(`personal.enums.appetite.${value}`) })
        : i18n.t(`personal.enums.appetite.${value}`),
  }));
}

function setAppetite(row: GuestRow, value: Appetite) {
  row.appetiteOverride = value === row.appetite ? null : value;
}

function onInvite(row: GuestRow) {
  if (!row.invited) {
    row.attending = true;
    row.appetiteOverride = null;
  }
}

async function save() {
  if (saving.value) {
    return;
  }
  saving.value = true;
  const { data } = await api.mealEvents.setGuests(props.event.id, payloadOf(rows.value));
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    emit("updated", data);
  }
}
</script>

<style scoped>
/* The label wraps instead of widening the page on a phone. */
.guest-checkbox :deep(.v-label) {
  white-space: normal;
  opacity: 1;
}
</style>
