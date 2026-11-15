<template>
  <v-container class="narrow-container">
    <BasePageTitle divider>
      <template #header>
        <v-icon
          size="80"
          color="primary"
          :icon="personalIcons.dietary"
        />
      </template>
      <template #title>
        {{ $t('personal.dietary.title') }}
      </template>
      {{ $t('personal.dietary.subtitle') }}
    </BasePageTitle>

    <v-autocomplete
      v-model="foodId"
      :items="foods"
      item-title="name"
      item-value="id"
      :label="$t('personal.dietary.pick-food')"
      :prepend-inner-icon="$globals.icons.search"
      clearable
      data-testid="dietary-food"
    />

    <v-card
      v-if="compliance"
      class="mb-6"
    >
      <v-card-title>{{ compliance.foodName }}</v-card-title>
      <v-list
        lines="two"
        density="compact"
      >
        <v-list-item
          v-for="status in compliance.statuses"
          :key="status.restrictionId"
          data-testid="dietary-status-row"
        >
          <v-list-item-title class="d-flex align-center flex-wrap ga-2">
            <span class="font-weight-medium">{{ status.restrictionName }}</span>
            <PersonalStatusChip :status="status.status" />
          </v-list-item-title>
          <v-list-item-subtitle>
            {{ text.foodStatus(status) }}
            <span v-if="status.source"> · {{ $t(`personal.enums.source.${status.source}`) }}</span>
          </v-list-item-subtitle>
          <template #append>
            <div class="d-flex flex-column flex-sm-row ga-1">
              <v-btn
                size="small"
                color="success"
                variant="tonal"
                :disabled="status.status === 'VERIFIED'"
                :data-testid="`dietary-verify-${status.restrictionKey}`"
                @click="askStatus(status, 'VERIFIED')"
              >
                {{ $t('personal.dietary.mark-verified') }}
              </v-btn>
              <v-btn
                size="small"
                color="error"
                variant="tonal"
                :disabled="status.stored && status.status === 'INCOMPATIBLE'"
                @click="askStatus(status, 'INCOMPATIBLE')"
              >
                {{ $t('personal.dietary.mark-incompatible') }}
              </v-btn>
              <v-btn
                v-if="status.stored"
                size="small"
                variant="text"
                @click="clearStatus(status)"
              >
                {{ $t('personal.dietary.reset') }}
              </v-btn>
            </div>
          </template>
        </v-list-item>
      </v-list>
    </v-card>

    <BaseDialog
      v-model="statusDialog"
      :title="pending ? `${pending.restriction.restrictionName} · ${$t(`personal.enums.status.${pending.status}`)}` : ''"
      :icon="personalIcons.dietary"
      can-confirm
      @confirm="applyStatus"
    >
      <v-card-text>
        <v-text-field
          v-model="reason"
          :label="$t('personal.dietary.reason')"
          autofocus
        />
      </v-card-text>
    </BaseDialog>

    <h3 class="text-h6 mt-6 mb-2">
      {{ $t('personal.dietary.tools-title') }}
    </h3>
    <p class="text-body-2 text-medium-emphasis">
      {{ $t('personal.dietary.tools-help') }}
    </p>
    <v-row
      dense
      align="center"
    >
      <v-col
        cols="12"
        sm="4"
      >
        <v-autocomplete
          v-model="toolForm.toolId"
          :items="tools"
          item-title="name"
          item-value="id"
          :label="$t('personal.dietary.tool')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col
        cols="12"
        sm="3"
      >
        <v-select
          v-model="toolForm.restrictionId"
          :items="restrictions"
          item-title="name"
          item-value="id"
          :label="$t('personal.people.restriction')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col
        cols="12"
        sm="3"
      >
        <v-text-field
          v-model="toolForm.reason"
          :label="$t('personal.common.reason')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col
        cols="12"
        sm="2"
      >
        <v-btn
          block
          color="primary"
          :disabled="!toolForm.toolId || !toolForm.restrictionId"
          @click="flagTool"
        >
          {{ $t('personal.common.add') }}
        </v-btn>
      </v-col>
    </v-row>
    <v-list density="compact">
      <v-list-item
        v-for="flag in toolFlags"
        :key="flag.id"
        :title="`${toolName(flag.toolId)} · ${flag.restriction.name}`"
        :subtitle="flag.reason ?? ''"
      >
        <template #append>
          <v-btn
            icon
            size="small"
            variant="text"
            :aria-label="$t('personal.common.delete')"
            @click="unflagTool(flag.id)"
          >
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </template>
      </v-list-item>
      <v-list-item
        v-if="!toolFlags.length"
        :title="$t('personal.dietary.no-tools')"
      />
    </v-list>
  </v-container>
</template>

<script setup lang="ts">
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore, useToolStore } from "~/composables/store";
import type {
  DietaryRestrictionOut,
  FoodComplianceOut,
  FoodRestrictionEffective,
  ToolRestrictionStatusOut,
  VerificationStatus,
} from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const route = useRoute();
const { store: foods } = useFoodStore();
const { store: tools } = useToolStore();

useSeoMeta({ title: i18n.t("personal.dietary.title") });

const foodId = ref<string | null>((route.query.food as string) || null);
const compliance = ref<FoodComplianceOut | null>(null);
const restrictions = ref<DietaryRestrictionOut[]>([]);
const toolFlags = ref<ToolRestrictionStatusOut[]>([]);

const statusDialog = ref(false);
const pending = ref<{ restriction: FoodRestrictionEffective; status: VerificationStatus } | null>(null);
const reason = ref("");
const toolForm = ref<{ toolId: string | null; restrictionId: string | null; reason: string }>({
  toolId: null,
  restrictionId: null,
  reason: "",
});

async function loadFood() {
  if (!foodId.value) {
    compliance.value = null;
    return;
  }
  const { data } = await api.dietary.getFood(foodId.value);
  compliance.value = data;
}

watch(foodId, loadFood);

function askStatus(restriction: FoodRestrictionEffective, status: VerificationStatus) {
  pending.value = { restriction, status };
  reason.value = "";
  statusDialog.value = true;
}

async function applyStatus() {
  if (!pending.value || !foodId.value) {
    return;
  }
  await api.dietary.setFoodStatus(foodId.value, pending.value.restriction.restrictionId, {
    status: pending.value.status,
    reason: reason.value || null,
  });
  await loadFood();
}

async function clearStatus(restriction: FoodRestrictionEffective) {
  if (!foodId.value) {
    return;
  }
  await api.dietary.clearFoodStatus(foodId.value, restriction.restrictionId);
  await loadFood();
}

function toolName(toolId: string): string {
  return tools.value.find(tool => tool.id === toolId)?.name ?? "";
}

async function loadTools() {
  const { data } = await api.dietary.getToolFlags();
  toolFlags.value = data ?? [];
}

async function flagTool() {
  if (!toolForm.value.toolId || !toolForm.value.restrictionId) {
    return;
  }
  await api.dietary.flagTool({
    toolId: toolForm.value.toolId,
    restrictionId: toolForm.value.restrictionId,
    reason: toolForm.value.reason || null,
  });
  toolForm.value = { toolId: null, restrictionId: null, reason: "" };
  await loadTools();
}

async function unflagTool(id: string) {
  await api.dietary.unflagTool(id);
  await loadTools();
}

onMounted(async () => {
  const { data } = await api.dietary.getRestrictions();
  restrictions.value = data ?? [];
  await Promise.all([loadFood(), loadTools()]);
});
</script>
