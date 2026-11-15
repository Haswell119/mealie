<template>
  <v-container class="md-container pe-page">
    <PersonalPageHeader
      :icon="personalIcons.hub"
      :title="greeting"
      :subtitle="`${today} · ${$t('personal.hub.subtitle')}`"
    />

    <!-- The three things a person does most often -->
    <v-row density="compact">
      <v-col
        v-for="action in quickActions"
        :key="action.key"
        cols="12"
        sm="4"
      >
        <NuxtLink
          :to="action.to"
          class="pe-tile pe-tile--action"
          :class="{ 'pe-tile--primary': action.primary }"
          :data-testid="`hub-action-${action.key}`"
        >
          <span class="pe-tile__icon">
            <v-icon :icon="action.icon" />
          </span>
          <span class="pe-tile__body">
            <span class="pe-tile__title">{{ action.title }}</span>
            <span class="pe-tile__hint">{{ action.subtitle }}</span>
          </span>
        </NuxtLink>
      </v-col>
    </v-row>

    <!-- What needs attention -->
    <template v-if="loaded">
      <h2 class="pe-section-title">
        {{ $t('personal.hub.todo-title') }}
      </h2>
      <v-card v-if="todos.length">
        <v-list lines="two">
          <v-list-item
            v-for="todo in todos"
            :key="todo.key"
            :value="todo.key"
            :to="todo.to"
            :title="todo.title"
            :subtitle="todo.hint"
            :data-testid="`hub-todo-${todo.key}`"
          >
            <template #prepend>
              <v-icon
                :icon="todo.icon"
                :color="todo.color"
                class="mr-2"
              />
            </template>
            <template #append>
              <v-icon :icon="mdiChevronRight" />
            </template>
          </v-list-item>
        </v-list>
      </v-card>
      <v-card
        v-else
        variant="outlined"
      >
        <v-card-text
          class="d-flex align-center ga-3"
          data-testid="hub-todo-empty"
        >
          <v-icon
            :icon="mdiCheckCircleOutline"
            color="success"
          />
          {{ $t('personal.hub.todo-nothing') }}
        </v-card-text>
      </v-card>
    </template>

    <v-row class="mt-0">
      <!-- Upcoming events -->
      <v-col
        cols="12"
        md="6"
      >
        <h2 class="pe-section-title">
          <v-icon
            :icon="personalIcons.events"
            size="20"
          />
          {{ $t('personal.hub.events-title') }}
        </h2>
        <v-card>
          <v-list
            v-if="events.length"
            lines="two"
          >
            <v-list-item
              v-for="event in events"
              :key="event.id"
              :to="`/events/${event.id}`"
              :title="event.name"
              :subtitle="eventSubtitle(event)"
              data-testid="hub-event"
            >
              <template #append>
                <v-icon :icon="mdiChevronRight" />
              </template>
            </v-list-item>
          </v-list>
          <v-card-text
            v-else
            class="text-medium-emphasis"
          >
            {{ $t('personal.hub.events-empty') }}
          </v-card-text>
          <v-card-actions class="px-4 pb-4">
            <v-btn
              variant="tonal"
              color="primary"
              to="/events?create=1"
            >
              {{ $t('personal.hub.events-cta') }}
            </v-btn>
            <v-btn
              v-if="events.length"
              variant="text"
              to="/events"
            >
              {{ $t('personal.hub.events-all') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>

      <!-- Shopping in progress -->
      <v-col
        cols="12"
        md="6"
      >
        <h2 class="pe-section-title">
          <v-icon
            :icon="personalIcons.shopping"
            size="20"
          />
          {{ $t('personal.hub.shopping-title') }}
        </h2>
        <v-card>
          <v-list
            v-if="plans.length"
            lines="one"
          >
            <v-list-item
              v-for="plan in plans"
              :key="plan.id"
              :to="`/shopping-plans/${plan.id}`"
              :title="plan.name"
              data-testid="hub-plan"
            >
              <template #append>
                <v-icon :icon="mdiChevronRight" />
              </template>
            </v-list-item>
          </v-list>
          <v-card-text
            v-else
            class="text-medium-emphasis"
          >
            {{ $t('personal.hub.shopping-empty') }}
          </v-card-text>
          <v-card-actions class="px-4 pb-4 flex-wrap">
            <v-btn
              variant="tonal"
              color="primary"
              to="/shopping-plans?create=1"
            >
              {{ $t('personal.hub.shopping-cta') }}
            </v-btn>
            <v-btn
              variant="text"
              to="/shopping-lists"
            >
              {{ $t('personal.hub.shopping-lists') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <!-- Every section, one tap away -->
    <h2 class="pe-section-title">
      {{ $t('personal.hub.explore-title') }}
    </h2>
    <v-row density="compact">
      <v-col
        v-for="link in explore"
        :key="link.to"
        cols="6"
        sm="4"
        md="3"
      >
        <NuxtLink
          :to="link.to"
          class="pe-tile"
        >
          <span class="pe-tile__icon">
            <v-icon :icon="link.icon" />
          </span>
          <span class="pe-tile__title">{{ link.title }}</span>
          <span class="pe-tile__hint">{{ link.hint }}</span>
        </NuxtLink>
      </v-col>
    </v-row>

    <!-- Appearance -->
    <h2 class="pe-section-title">
      {{ $t('personal.hub.look-title') }}
    </h2>
    <v-card>
      <v-card-text>
        <v-switch
          :model-value="look.glass.value"
          color="primary"
          hide-details
          :label="$t('personal.hub.look-glass')"
          data-testid="hub-glass-switch"
          @update:model-value="look.setGlass(!!$event)"
        />
        <div class="text-body-small text-medium-emphasis mt-1">
          {{ $t('personal.hub.look-glass-hint') }}
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import {
  mdiAccountPlusOutline,
  mdiAlertCircleOutline,
  mdiCalendarMultiselect,
  mdiCheckCircleOutline,
  mdiChevronRight,
  mdiClockAlertOutline,
  mdiSilverwareForkKnife,
} from "@mdi/js";
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalLook } from "~/composables/personal/use-personal-look";
import { personalIcons, usePersonalQuickActions } from "~/composables/personal/use-personal-nav";
import type { MealEventSummary, ShoppingPlanOut } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

interface Todo {
  key: string;
  icon: string;
  color: string;
  title: string;
  hint: string;
  to: string;
}

const i18n = useI18n();
const api = usePersonalApi();
const auth = useMealieAuth();
const look = usePersonalLook();
const quickActions = usePersonalQuickActions();

useSeoMeta({ title: i18n.t("personal.hub.title") });

const DAY = 24 * 60 * 60 * 1000;

const loaded = ref(false);
const events = ref<MealEventSummary[]>([]);
const plans = ref<ShoppingPlanOut[]>([]);
const hasOwnProfile = ref(true);
const pendingProposals = ref(0);
const expired = ref(0);
const expiring = ref(0);

const groupSlug = computed(() => auth.user.value?.groupSlug || "");
const greeting = computed(() => {
  const name = auth.user.value?.fullName?.split(" ")[0];
  return name ? i18n.t("personal.hub.greeting", { name }) : i18n.t("personal.hub.greeting-plain");
});
const today = computed(() => {
  const text = new Intl.DateTimeFormat(i18n.locale.value, { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  return text.charAt(0).toUpperCase() + text.slice(1);
});

const todos = computed<Todo[]>(() => {
  const list: Todo[] = [];
  if (!hasOwnProfile.value) {
    list.push({
      key: "profile",
      icon: mdiAccountPlusOutline,
      color: "primary",
      title: i18n.t("personal.hub.todo-profile"),
      hint: i18n.t("personal.hub.todo-profile-hint"),
      to: "/people",
    });
  }
  if (expired.value) {
    list.push({
      key: "expired",
      icon: mdiAlertCircleOutline,
      color: "error",
      title: i18n.t("personal.hub.todo-expired", { count: expired.value }, expired.value),
      hint: i18n.t("personal.hub.todo-expired-hint"),
      to: "/pantry",
    });
  }
  if (expiring.value) {
    list.push({
      key: "expiring",
      icon: mdiClockAlertOutline,
      color: "warning",
      title: i18n.t("personal.hub.todo-expiring", { count: expiring.value }, expiring.value),
      hint: i18n.t("personal.hub.todo-expiring-hint"),
      to: "/pantry",
    });
  }
  if (pendingProposals.value) {
    list.push({
      key: "proposals",
      icon: personalIcons.assistant,
      color: "primary",
      title: i18n.t("personal.hub.todo-proposals", { count: pendingProposals.value }, pendingProposals.value),
      hint: i18n.t("personal.hub.todo-proposals-hint"),
      to: "/assistant",
    });
  }
  return list;
});

const explore = computed(() => [
  {
    to: `/g/${groupSlug.value}`,
    icon: mdiSilverwareForkKnife,
    title: i18n.t("personal.hub.explore-recipes"),
    hint: i18n.t("personal.hub.explore-recipes-hint"),
  },
  {
    to: "/household/mealplan/planner/view",
    icon: mdiCalendarMultiselect,
    title: i18n.t("personal.hub.explore-planner"),
    hint: i18n.t("personal.hub.explore-planner-hint"),
  },
  {
    to: "/inspirations",
    icon: personalIcons.inspirations,
    title: i18n.t("personal.nav.inspirations"),
    hint: i18n.t("personal.hub.explore-inspirations-hint"),
  },
  {
    to: "/people",
    icon: personalIcons.people,
    title: i18n.t("personal.nav.people"),
    hint: i18n.t("personal.hub.explore-people-hint"),
  },
  {
    to: "/pantry",
    icon: personalIcons.pantry,
    title: i18n.t("personal.nav.pantry"),
    hint: i18n.t("personal.hub.explore-pantry-hint"),
  },
  {
    to: "/dietary",
    icon: personalIcons.dietary,
    title: i18n.t("personal.nav.dietary"),
    hint: i18n.t("personal.hub.explore-dietary-hint"),
  },
  {
    to: "/assistant",
    icon: personalIcons.assistant,
    title: i18n.t("personal.nav.assistant"),
    hint: i18n.t("personal.hub.explore-assistant-hint"),
  },
]);

function eventSubtitle(event: MealEventSummary): string {
  const count = event.guests.filter(guest => guest.attending).length;
  const guests = i18n.t("personal.hub.events-guests", { count }, count);
  if (!event.startsAt) {
    return `${i18n.t("personal.hub.events-undated")} · ${guests}`;
  }
  const date = new Intl.DateTimeFormat(i18n.locale.value, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(event.startsAt));
  return `${date} · ${guests}`;
}

async function load() {
  // Each block is independent: one request that fails must not empty the page.
  const [personsResult, eventsResult, plansResult, pantryResult, proposalsResult] = await Promise.all([
    api.persons.getAll(1, -1),
    api.mealEvents.getAll(1, -1),
    api.shoppingPlans.getAll(1, -1),
    api.pantry.getAll(1, -1),
    api.assistant.getProposals(),
  ]);

  hasOwnProfile.value = (personsResult.data?.items ?? []).some(person => person.linkedUserId);

  const startOfToday = new Date().setHours(0, 0, 0, 0);
  events.value = (eventsResult.data?.items ?? [])
    .filter(event => event.status !== "DONE" && (!event.startsAt || new Date(event.startsAt).getTime() >= startOfToday))
    .sort((a, b) => (a.startsAt ?? "9999").localeCompare(b.startsAt ?? "9999"))
    .slice(0, 3);

  plans.value = (plansResult.data?.items ?? []).filter(plan => plan.status === "OPEN").slice(0, 3);

  let expiredCount = 0;
  let expiringCount = 0;
  for (const item of pantryResult.data?.items ?? []) {
    if (!item.expiresOn || item.quantity <= 0) {
      continue;
    }
    const days = (new Date(`${item.expiresOn}T00:00:00`).getTime() - startOfToday) / DAY;
    if (days < 0) {
      expiredCount += 1;
    }
    else if (days <= 7) {
      expiringCount += 1;
    }
  }
  expired.value = expiredCount;
  expiring.value = expiringCount;

  pendingProposals.value = (proposalsResult.data?.items ?? []).filter(proposal => proposal.status === "PENDING").length;
  loaded.value = true;
}

onMounted(load);
</script>
