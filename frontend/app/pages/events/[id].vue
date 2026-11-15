<template>
  <v-container class="narrow-container">
    <v-alert
      v-if="notFound"
      type="error"
      variant="tonal"
      data-testid="event-not-found"
    >
      {{ $t('personal.events.not-found') }}
      <NuxtLink
        to="/events"
        class="d-block mt-2"
      >
        {{ $t('personal.events.back') }}
      </NuxtLink>
    </v-alert>

    <v-progress-linear
      v-else-if="!event"
      indeterminate
      color="primary"
    />

    <template v-else>
      <MealEventFormDialog
        v-model="editDialog"
        :event="event"
        :persons="persons"
        @saved="applyEvent($event)"
      />

      <BaseDialog
        v-model="deleteDialog"
        :title="$t('general.confirm')"
        :icon="$globals.icons.alertCircle"
        color="error"
        can-confirm
        @confirm="remove"
      >
        <v-card-text data-testid="event-delete-confirm">
          {{ $t('personal.events.delete-confirm', { name: event.name }) }}
        </v-card-text>
      </BaseDialog>

      <header
        class="mt-2 mb-3"
        data-testid="event-header"
      >
        <v-btn
          variant="text"
          size="small"
          to="/events"
          class="px-1 mb-1"
          :prepend-icon="mdiArrowLeft"
          data-testid="event-back"
        >
          {{ $t('personal.events.back') }}
        </v-btn>
        <div class="d-flex align-center flex-wrap ga-2">
          <h1
            class="text-h5 event-name ma-0"
            data-testid="event-title"
          >
            {{ event.name }}
          </h1>
          <MealEventStatusChip :status="event.status" />
          <v-btn
            icon
            size="small"
            variant="text"
            :aria-label="$t('personal.events.edit')"
            data-testid="event-edit-header"
            @click="editDialog = true"
          >
            <v-icon>{{ $globals.icons.edit }}</v-icon>
          </v-btn>
        </div>
        <div class="d-flex flex-wrap gc-4 gr-1 text-body-2 text-medium-emphasis mt-1">
          <span
            v-if="event.startsAt"
            data-testid="event-date"
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
          <span v-if="event.cookPersonId && personNames[event.cookPersonId]">
            <v-icon
              size="small"
              start
              :icon="mdiChefHat"
            />{{ $t('personal.events.cooked-by', { name: personNames[event.cookPersonId] }) }}
          </span>
        </div>
        <p
          v-if="event.notes"
          class="text-body-2 mt-2 mb-0 event-notes"
        >
          {{ event.notes }}
        </p>
      </header>

      <v-tabs
        v-model="step"
        show-arrows
        color="primary"
        density="comfortable"
        class="mb-4 event-tabs"
        data-testid="event-tabs"
      >
        <v-tab
          v-for="(entry, index) in steps"
          :key="entry.key"
          :value="entry.key"
          :data-testid="`event-tab-${entry.key}`"
        >
          {{ index + 1 }}. {{ entry.title }}
          <v-badge
            v-if="entry.badge"
            inline
            :color="entry.badgeColor"
            :content="entry.badge"
          />
        </v-tab>
      </v-tabs>

      <!-- Every step stays mounted, so that an unsaved choice survives a look at another step. -->
      <section
        v-show="step === 'guests'"
        data-testid="event-step-guests"
      >
        <MealEventGuestsStep
          :event="event"
          :persons="persons"
          :analysis="analysis"
          @updated="applyEvent($event)"
        />
      </section>
      <section
        v-show="step === 'constraints'"
        data-testid="event-step-constraints"
      >
        <MealEventConstraintsStep
          :event="event"
          :persons="persons"
          :analysis="analysis"
          :person-names="personNames"
          :menu-item-labels="menuItemLabels"
          @updated="applyEvent($event)"
        />
      </section>
      <section
        v-show="step === 'menu'"
        data-testid="event-step-menu"
      >
        <MealEventMenuStep
          :event="event"
          :analysis="analysis"
          :restriction-names="restrictionNames"
          @updated="applyEvent($event)"
        />
      </section>
      <section
        v-show="step === 'portions'"
        data-testid="event-step-portions"
      >
        <MealEventPortionsStep
          :analysis="analysis"
          :menu-item-labels="menuItemLabels"
        />
      </section>
      <section
        v-show="step === 'review'"
        data-testid="event-step-review"
      >
        <MealEventReviewStep
          :event="event"
          :analysis="analysis"
          :restriction-names="restrictionNames"
          @updated="applyEvent($event, true)"
          @edit="editDialog = true"
          @delete="deleteDialog = true"
        />
      </section>

      <v-divider class="mt-6 mb-3" />
      <div class="d-flex justify-space-between ga-2">
        <v-btn
          v-if="previousStep"
          variant="text"
          :prepend-icon="mdiChevronLeft"
          data-testid="event-step-previous"
          @click="goTo(previousStep.key)"
        >
          {{ previousStep.title }}
        </v-btn>
        <v-spacer />
        <v-btn
          v-if="nextStep"
          variant="tonal"
          color="primary"
          :append-icon="mdiChevronRight"
          data-testid="event-step-next"
          @click="goTo(nextStep.key)"
        >
          {{ nextStep.title }}
        </v-btn>
      </div>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { mdiArrowLeft, mdiCalendar, mdiChefHat, mdiChevronLeft, mdiChevronRight, mdiMapMarkerOutline } from "@mdi/js";
import MealEventConstraintsStep from "~/components/Domain/MealEvent/MealEventConstraintsStep.vue";
import MealEventFormDialog from "~/components/Domain/MealEvent/MealEventFormDialog.vue";
import MealEventGuestsStep from "~/components/Domain/MealEvent/MealEventGuestsStep.vue";
import MealEventMenuStep from "~/components/Domain/MealEvent/MealEventMenuStep.vue";
import MealEventPortionsStep from "~/components/Domain/MealEvent/MealEventPortionsStep.vue";
import MealEventReviewStep from "~/components/Domain/MealEvent/MealEventReviewStep.vue";
import MealEventStatusChip from "~/components/Domain/MealEvent/MealEventStatusChip.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { alert } from "~/composables/use-toast";
import type { MealEventAnalysisOut, MealEventOut, PersonOut } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const STEP_KEYS = ["guests", "constraints", "menu", "portions", "review"] as const;
type StepKey = (typeof STEP_KEYS)[number];

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();
const router = useRouter();

const eventId = computed(() => route.params.id as string);

const event = ref<MealEventOut | null>(null);
const analysis = ref<MealEventAnalysisOut | null>(null);
const persons = ref<PersonOut[]>([]);
const notFound = ref(false);
const editDialog = ref(false);
const deleteDialog = ref(false);

useSeoMeta({ title: () => event.value?.name ?? i18n.t("personal.events.title") });

function isStep(value: unknown): value is StepKey {
  return STEP_KEYS.includes(value as StepKey);
}

// The step lives in the URL, so that a reload or a shared link opens the same step.
const step = ref<StepKey>(isStep(route.query.step) ? route.query.step : "guests");
watch(step, (value) => {
  router.replace({ query: { ...route.query, step: value } });
});

const steps = computed(() =>
  STEP_KEYS.map((key) => {
    const blocking = key === "review" ? (analysis.value?.blocking.length ?? 0) : 0;
    const shared = key === "constraints" ? (analysis.value?.constraints.shared.length ?? 0) : 0;
    return {
      key,
      title: i18n.t(`personal.events.steps.${key}`),
      badge: blocking || shared || 0,
      badgeColor: blocking ? "error" : "warning",
    };
  }),
);
const stepIndex = computed(() => STEP_KEYS.indexOf(step.value));
const previousStep = computed(() => steps.value[stepIndex.value - 1]);
const nextStep = computed(() => steps.value[stepIndex.value + 1]);

function goTo(key: StepKey) {
  step.value = key;
  window.scrollTo({ top: 0 });
}

const personNames = computed(() => {
  const names: Record<string, string> = {};
  for (const guest of event.value?.guests ?? []) {
    names[guest.personId] = guest.person.displayName;
  }
  for (const person of persons.value) {
    names[person.id] = person.displayName;
  }
  return names;
});

/** The name of each restriction by its key, from the profiles of the persons and from the analysis. */
const restrictionNames = computed(() => {
  const names: Record<string, string> = {};
  for (const person of persons.value) {
    for (const restriction of person.restrictions) {
      names[restriction.restriction.key] = restriction.restriction.name;
    }
  }
  const sets = [analysis.value?.constraints, ...(analysis.value?.menu ?? []).map(item => item.constraints)];
  for (const set of sets) {
    const constraints = [...(set?.shared ?? []), ...(set?.individual ?? []).flatMap(person => person.constraints)];
    for (const constraint of constraints) {
      names[constraint.restrictionKey] = constraint.restrictionName;
    }
  }
  return names;
});

/** A dish is named by its course, and by its title when it has one. */
const menuItemLabels = computed(() => {
  const labels: Record<string, string> = {};
  for (const item of event.value?.menuItems ?? []) {
    const course = i18n.t(`personal.enums.course.${item.course}`);
    labels[item.id] = item.title ? `${course} · ${item.title}` : course;
  }
  return labels;
});

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(i18n.locale.value, { hour: "2-digit", minute: "2-digit" });
}

/**
 * Take the event that the server returned after a change, and check the menu again.
 *
 * The server sends a planned event back to draft when its guests or its menu change. The user hears about it,
 * unless they changed the status themselves.
 */
async function applyEvent(updated: MealEventOut, statusChange = false) {
  const reopened = !statusChange && event.value?.status === "PLANNED" && updated.status === "DRAFT";
  // The event and its analysis change together, so that no step shows the new menu with the old checks.
  const { data } = await api.mealEvents.getAnalysis(updated.id);
  event.value = updated;
  if (data) {
    analysis.value = data;
  }
  if (reopened) {
    alert.info(i18n.t("personal.events.reopened"));
  }
}

async function remove() {
  if (!event.value) {
    return;
  }
  const { data } = await api.mealEvents.deleteOne(event.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await router.push("/events");
  }
}

onMounted(async () => {
  const [eventResult, personsResult] = await Promise.all([
    api.mealEvents.getOne(eventId.value),
    api.persons.getAll(1, -1, { orderBy: "display_name", orderDirection: "asc" }),
  ]);
  persons.value = personsResult.data?.items ?? [];
  if (!eventResult.data) {
    notFound.value = true;
    return;
  }
  await applyEvent(eventResult.data, true);
});
</script>

<style scoped>
.event-name,
.event-notes {
  min-width: 0;
  overflow-wrap: anywhere;
}

.event-notes {
  white-space: pre-line;
}

/* The tabs keep their words as written: the names of the steps are not shouted. */
.event-tabs :deep(.v-tab) {
  text-transform: none;
  letter-spacing: normal;
}
</style>
