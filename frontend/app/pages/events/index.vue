<template>
  <v-container class="narrow-container pe-page">
    <MealEventFormDialog
      v-model="dialog"
      :persons="persons"
      @saved="onCreated"
    />

    <PersonalPageHeader
      :icon="personalIcons.events"
      :title="$t('personal.events.title')"
      :subtitle="$t('personal.events.subtitle')"
    />

    <div class="d-flex justify-end mb-4">
      <BaseButton
        create
        data-testid="event-create"
        @click="dialog = true"
      >
        {{ $t('personal.events.new') }}
      </BaseButton>
    </div>

    <v-alert
      v-if="loaded && !events.length"
      type="info"
      variant="tonal"
      data-testid="event-empty"
    >
      {{ $t('personal.events.empty') }}
    </v-alert>

    <section
      v-for="group in groups"
      :key="group.key"
      class="mb-6"
    >
      <h3
        v-if="groups.length > 1"
        class="text-subtitle-1 text-medium-emphasis mb-1"
      >
        {{ group.title }}
      </h3>
      <v-card
        v-for="event in group.events"
        :key="event.id"
        :to="`/events/${event.id}`"
        class="my-2 left-border"
        data-testid="event-card"
      >
        <v-card-title class="d-flex align-center flex-wrap ga-2 text-wrap">
          <span class="event-name">{{ event.name }}</span>
          <v-spacer />
          <MealEventStatusChip :status="event.status" />
        </v-card-title>
        <v-card-text class="d-flex flex-wrap gc-4 gr-1">
          <span
            v-if="event.startsAt"
            data-testid="event-card-date"
          >
            <v-icon
              size="small"
              start
              :icon="mdiCalendar"
            />{{ $d(new Date(event.startsAt), "medium") }} · {{ formatTime(event.startsAt) }}
          </span>
          <span v-if="event.location">
            <v-icon
              size="small"
              start
              :icon="mdiMapMarkerOutline"
            />{{ event.location }}
          </span>
          <span data-testid="event-card-guests">
            <v-icon
              size="small"
              start
              :icon="personalIcons.people"
            />{{ $t('personal.events.guest-count', attendingCount(event)) }}
          </span>
        </v-card-text>
      </v-card>
    </section>
  </v-container>
</template>

<script setup lang="ts">
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import { mdiCalendar, mdiMapMarkerOutline } from "@mdi/js";
import MealEventFormDialog from "~/components/Domain/MealEvent/MealEventFormDialog.vue";
import MealEventStatusChip from "~/components/Domain/MealEvent/MealEventStatusChip.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import type { MealEventOut, MealEventSummary, PersonOut } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();
const router = useRouter();

useSeoMeta({ title: i18n.t("personal.events.title") });

const events = ref<MealEventSummary[]>([]);
const persons = ref<PersonOut[]>([]);
const loaded = ref(false);
const dialog = ref(false);

function time(event: MealEventSummary): number | null {
  return event.startsAt ? new Date(event.startsAt).getTime() : null;
}

/** Events to come first, the nearest on top. Past and finished events after them, the latest on top. */
const groups = computed(() => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const isPast = (event: MealEventSummary) => event.status === "DONE" || (time(event) ?? Infinity) < today.getTime();

  const upcoming = events.value
    .filter(event => !isPast(event))
    .sort((a, b) => (time(a) ?? Infinity) - (time(b) ?? Infinity) || a.name.localeCompare(b.name));
  const past = events.value
    .filter(isPast)
    .sort((a, b) => (time(b) ?? -Infinity) - (time(a) ?? -Infinity) || a.name.localeCompare(b.name));

  return [
    { key: "upcoming", title: i18n.t("personal.events.upcoming"), events: upcoming },
    { key: "past", title: i18n.t("personal.events.past"), events: past },
  ].filter(group => group.events.length);
});

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(i18n.locale.value, { hour: "2-digit", minute: "2-digit" });
}

function attendingCount(event: MealEventSummary): number {
  return event.guests.filter(guest => guest.attending).length;
}

async function refresh() {
  const [eventsResult, personsResult] = await Promise.all([
    api.mealEvents.getAll(1, -1),
    api.persons.getAll(1, -1, { orderBy: "display_name", orderDirection: "asc" }),
  ]);
  events.value = eventsResult.data?.items ?? [];
  persons.value = personsResult.data?.items ?? [];
  loaded.value = true;
}

async function onCreated(event: MealEventOut) {
  await router.push(`/events/${event.id}`);
}

// "Organise a meal" in the create menu opens this page with `?create=1`.
watch(
  () => route.query.create,
  (create) => {
    if (create) {
      dialog.value = true;
      router.replace({ query: { ...route.query, create: undefined } });
    }
  },
  { immediate: true },
);

onMounted(refresh);
</script>

<style scoped>
.event-name {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
