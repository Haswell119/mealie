<template>
  <v-container class="narrow-container">
    <BaseDialog
      v-model="dialog"
      :title="$t('personal.shopping.new-plan')"
      :icon="personalIcons.shopping"
      max-width="700"
      width="100%"
      can-submit
      :submit-text="$t('personal.shopping.form.create')"
      :submit-disabled="!canCreate || creating"
      :loading="creating"
      disable-submit-on-enter
      keep-open
      @submit="create"
    >
      <v-card-text>
        <ShoppingPlanForm v-model="form" />
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
        {{ $t('personal.shopping.delete-confirm', { name: deleting?.name }) }}
      </v-card-text>
    </BaseDialog>

    <BasePageTitle divider>
      <template #header>
        <v-icon
          size="80"
          color="primary"
          :icon="personalIcons.shopping"
        />
      </template>
      <template #title>
        {{ $t('personal.shopping.title') }}
      </template>
      {{ $t('personal.shopping.subtitle') }}
    </BasePageTitle>

    <div class="d-flex justify-end mb-4">
      <BaseButton
        create
        data-testid="plan-create"
        @click="openCreate()"
      />
    </div>

    <v-alert
      v-if="loaded && !plans.length"
      type="info"
      variant="tonal"
      data-testid="plan-empty"
    >
      {{ $t('personal.shopping.empty') }}
    </v-alert>

    <v-card
      v-for="plan in plans"
      :key="plan.id"
      class="my-2 left-border plan-card"
      data-testid="plan-card"
    >
      <v-card-title class="d-flex align-start">
        <NuxtLink
          :to="`/shopping-plans/${plan.id}`"
          class="plan-link flex-grow-1"
          data-testid="plan-link"
        >
          {{ plan.name }}
        </NuxtLink>
        <v-btn
          icon
          variant="text"
          size="small"
          class="plan-delete"
          :aria-label="$t('personal.common.delete')"
          data-testid="plan-delete"
          @click="askDelete(plan)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div class="d-flex flex-wrap ga-2 mb-2">
          <v-chip
            size="small"
            variant="tonal"
          >
            {{ $t(`personal.shopping.source.${plan.sourceType}`) }}
          </v-chip>
          <v-chip
            size="small"
            :color="plan.status === 'DONE' ? 'success' : 'primary'"
            variant="tonal"
            data-testid="plan-status"
          >
            {{ $t(`personal.shopping.status.${plan.status}`) }}
          </v-chip>
        </div>
        <span class="text-body-small text-medium-emphasis">
          {{ plan.computedAt
            ? $t('personal.shopping.computed-at', { date: $d(new Date(plan.computedAt), 'long') })
            : $t('personal.shopping.never-computed') }}
        </span>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import ShoppingPlanForm, {
  emptyShoppingPlanForm,
  shoppingPlanFormIsValid,
  shoppingPlanFormPayload,
} from "~/components/Domain/ShoppingPlan/ShoppingPlanForm.vue";
import type { ShoppingPlanFormModel } from "~/components/Domain/ShoppingPlan/ShoppingPlanForm.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type { ShoppingPlanOut } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();
const router = useRouter();

useSeoMeta({ title: i18n.t("personal.shopping.title") });

const plans = ref<ShoppingPlanOut[]>([]);
const loaded = ref(false);

const dialog = ref(false);
const creating = ref(false);
const form = ref<ShoppingPlanFormModel>(emptyShoppingPlanForm());
const canCreate = computed(() => shoppingPlanFormIsValid(form.value));

const deleteDialog = ref(false);
const deleting = ref<ShoppingPlanOut | null>(null);

async function refresh() {
  const { data } = await api.shoppingPlans.getAll(1, -1, { orderBy: "created_at", orderDirection: "desc" });
  plans.value = data?.items ?? [];
  loaded.value = true;
}

function openCreate(eventId: string | null = null) {
  form.value = emptyShoppingPlanForm();
  if (eventId) {
    form.value.sourceType = "EVENT";
    form.value.eventId = eventId;
  }
  dialog.value = true;
}

async function create() {
  if (!canCreate.value || creating.value) {
    return;
  }
  creating.value = true;
  const { data } = await api.shoppingPlans.createOne(shoppingPlanFormPayload(form.value));
  creating.value = false;
  if (data) {
    dialog.value = false;
    await router.push(`/shopping-plans/${data.id}`);
  }
}

function askDelete(plan: ShoppingPlanOut) {
  deleting.value = plan;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.shoppingPlans.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await refresh();
  }
}

onMounted(() => {
  refresh();
  const eventId = typeof route.query.event === "string" && route.query.event ? route.query.event : null;
  if (route.query.create || eventId) {
    openCreate(eventId);
  }
});
</script>

<style scoped>
.plan-card {
  position: relative;
}

.plan-link {
  color: inherit;
  text-decoration: none;
  white-space: normal;
  overflow-wrap: anywhere;
}

/* The whole card opens the plan, while the delete button stays a separate control above the link. */
.plan-link::after {
  content: "";
  position: absolute;
  inset: 0;
}

.plan-delete {
  position: relative;
  z-index: 1;
}
</style>
