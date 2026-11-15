<template>
  <v-container class="narrow-container pe-page">
    <PersonalPageHeader
      :icon="personalIcons.dietary"
      :title="$t('personal.dietary.title')"
      :subtitle="$t('personal.dietary.subtitle')"
    />

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

    <h3 class="text-title-large mt-6 mb-2">
      {{ $t('personal.dietary.check-recipe-title') }}
    </h3>
    <p class="text-body-medium text-medium-emphasis">
      {{ $t('personal.dietary.check-recipe-help') }}
    </p>
    <v-autocomplete
      v-model="recipeId"
      :items="recipes"
      item-title="name"
      item-value="id"
      :label="$t('personal.dietary.pick-recipe')"
      clearable
      density="compact"
      data-testid="dietary-recipe"
    />
    <v-card
      v-if="recipeCheck"
      class="mb-6"
      data-testid="dietary-recipe-result"
    >
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <span>{{ recipeCheck.recipeName }}</span>
        <PersonalStatusChip
          v-if="recipeCheck.restrictionKeys.length"
          :status="recipeCheck.status"
        />
      </v-card-title>
      <v-card-text>
        <v-alert
          v-if="!recipeCheck.restrictionKeys.length"
          type="info"
          variant="tonal"
          density="compact"
        >
          {{ $t('personal.dietary.no-own-restrictions') }}
        </v-alert>
        <v-alert
          v-else-if="!recipeCheck.findings.length"
          type="success"
          variant="tonal"
          density="compact"
        >
          {{ $t('personal.dietary.all-verified') }}
        </v-alert>
        <v-list
          v-else
          density="compact"
          lines="two"
        >
          <v-list-item
            v-for="(finding, index) in sortedFindings"
            :key="index"
            :disabled="!finding.foodId"
            @click="finding.foodId ? (foodId = finding.foodId) : undefined"
          >
            <template #prepend>
              <PersonalStatusChip
                :status="finding.status"
                class="mr-2"
              />
            </template>
            <v-list-item-title>{{ finding.subject }}</v-list-item-title>
            <v-list-item-subtitle>
              {{ restrictionName(finding.restrictionKey) }} · {{ text.finding(finding) }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>

    <h3 class="text-title-large mt-6 mb-2">
      {{ $t('personal.dietary.restrictions-title') }}
    </h3>
    <div class="d-flex flex-wrap ga-2 mb-3">
      <v-chip
        v-for="restriction in restrictions"
        :key="restriction.id"
        size="small"
        :closable="!restriction.isSystem"
        :variant="restriction.isSystem ? 'tonal' : 'outlined'"
        data-testid="dietary-restriction"
        @click:close="deleteRestriction(restriction.id)"
      >
        {{ restriction.name }} · {{ $t(`personal.enums.kind.${restriction.kind}`) }}
      </v-chip>
    </div>
    <v-row
      density="compact"
      align="center"
    >
      <v-col
        cols="12"
        sm="6"
      >
        <v-text-field
          v-model="restrictionForm.name"
          :label="$t('personal.dietary.new-restriction')"
          density="compact"
          hide-details
          data-testid="dietary-restriction-name"
        />
      </v-col>
      <v-col
        cols="8"
        sm="4"
      >
        <v-select
          v-model="restrictionForm.kind"
          :items="kindItems"
          :label="$t('personal.dietary.restriction-kind')"
          density="compact"
          hide-details
        />
      </v-col>
      <v-col
        cols="4"
        sm="2"
      >
        <v-btn
          block
          color="primary"
          :disabled="!restrictionForm.name.trim()"
          data-testid="dietary-restriction-add"
          @click="createRestriction"
        >
          {{ $t('personal.common.add') }}
        </v-btn>
      </v-col>
    </v-row>

    <h3 class="text-title-large mt-6 mb-2">
      {{ $t('personal.dietary.tools-title') }}
    </h3>
    <p class="text-body-medium text-medium-emphasis">
      {{ $t('personal.dietary.tools-help') }}
    </p>
    <v-row
      density="compact"
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
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import { useUserApi } from "~/composables/api";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore, useToolStore } from "~/composables/store";
import type {
  DietaryRestrictionOut,
  FoodComplianceOut,
  FoodRestrictionEffective,
  RecipeComplianceOut,
  RestrictionKind,
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

const userApi = useUserApi();
const recipes = ref<{ id?: string | null; name?: string | null }[]>([]);
const recipeId = ref<string | null>(null);
const recipeCheck = ref<RecipeComplianceOut | null>(null);

const sortedFindings = computed(() => {
  const order = { INCOMPATIBLE: 0, UNVERIFIED: 1, VERIFIED: 2 };
  return [...(recipeCheck.value?.findings ?? [])].sort((a, b) => order[a.status] - order[b.status]);
});

function restrictionName(key: string): string {
  return restrictions.value.find(restriction => restriction.key === key)?.name ?? key;
}

async function loadRecipeCheck() {
  if (!recipeId.value) {
    recipeCheck.value = null;
    return;
  }
  const { data } = await api.dietary.getRecipe(recipeId.value);
  recipeCheck.value = data;
}

watch(recipeId, loadRecipeCheck);

const restrictionForm = ref<{ name: string; kind: RestrictionKind }>({ name: "", kind: "PREFERENCE" });
const kindItems = computed(() =>
  (["MEDICAL", "ALLERGY", "INTOLERANCE", "ETHICAL", "PREFERENCE"] as RestrictionKind[]).map(value => ({
    value,
    title: i18n.t(`personal.enums.kind.${value}`),
  })),
);

async function loadRestrictions() {
  const { data } = await api.dietary.getRestrictions();
  restrictions.value = data ?? [];
}

async function createRestriction() {
  const name = restrictionForm.value.name.trim();
  // The key is a stable identifier without accents or spaces, built from the name.
  const key = name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  if (!key) {
    return;
  }
  const { data } = await api.dietary.createRestriction({ key, name, kind: restrictionForm.value.kind });
  if (data) {
    restrictionForm.value = { name: "", kind: "PREFERENCE" };
    await Promise.all([loadRestrictions(), loadFood()]);
  }
}

async function deleteRestriction(id: string) {
  await api.dietary.deleteRestriction(id);
  await Promise.all([loadRestrictions(), loadFood()]);
}

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
  await Promise.all([loadFood(), loadRecipeCheck()]);
}

async function clearStatus(restriction: FoodRestrictionEffective) {
  if (!foodId.value) {
    return;
  }
  await api.dietary.clearFoodStatus(foodId.value, restriction.restrictionId);
  await Promise.all([loadFood(), loadRecipeCheck()]);
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
  await loadRestrictions();
  await Promise.all([loadFood(), loadTools()]);
  const { data } = await userApi.recipes.getAll(1, -1, { orderBy: "name", orderDirection: "asc" });
  recipes.value = data?.items ?? [];
});
</script>
