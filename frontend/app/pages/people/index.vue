<template>
  <v-container class="narrow-container">
    <BaseDialog
      v-model="dialog"
      :title="editing ? $t('personal.people.edit') : $t('personal.people.new')"
      :icon="personalIcons.people"
      max-width="700"
      width="100%"
      can-submit
      :submit-disabled="!form.displayName.trim()"
      disable-submit-on-enter
      keep-open
      @submit="save"
    >
      <v-card-text>
        <v-text-field
          v-model="form.displayName"
          :label="$t('personal.people.display-name')"
          autofocus
          data-testid="person-name"
        />
        <v-select
          v-model="form.appetite"
          :items="appetiteItems"
          :label="$t('personal.people.appetite')"
        />
        <v-switch
          v-model="form.isMe"
          color="primary"
          hide-details
          :label="$t('personal.people.is-me')"
          data-testid="person-is-me"
        />
        <p class="text-caption text-medium-emphasis mb-3">
          {{ $t('personal.people.is-me-help') }}
        </p>

        <template v-if="!form.isMe">
          <v-switch
            v-model="form.consentGiven"
            color="primary"
            hide-details
            :label="$t('personal.people.consent')"
            data-testid="person-consent"
          />
          <p class="text-caption text-medium-emphasis mb-3">
            {{ $t('personal.people.consent-help') }}
          </p>
          <v-text-field
            v-if="form.consentGiven"
            v-model="form.consentNote"
            :label="$t('personal.people.consent-note')"
            density="compact"
          />
        </template>

        <template v-if="canHoldData">
          <v-divider class="my-3" />
          <h3 class="text-subtitle-1 mb-2">
            {{ $t('personal.people.restrictions') }}
          </h3>
          <v-card
            v-for="(restriction, index) in form.restrictions"
            :key="index"
            variant="outlined"
            class="pa-3 mb-3"
          >
            <div class="d-flex align-center">
              <v-select
                v-model="restriction.restrictionId"
                :items="restrictionItems"
                :label="$t('personal.people.restriction')"
                density="compact"
                hide-details
                class="mr-2"
                data-testid="person-restriction"
              />
              <v-btn
                icon
                size="small"
                variant="text"
                :aria-label="$t('personal.common.delete')"
                @click="form.restrictions.splice(index, 1)"
              >
                <v-icon>{{ $globals.icons.delete }}</v-icon>
              </v-btn>
            </div>
            <v-row
              dense
              class="mt-2"
            >
              <v-col
                cols="12"
                sm="6"
              >
                <v-select
                  v-model="restriction.severity"
                  :items="severityItems"
                  :label="$t('personal.people.severity')"
                  density="compact"
                  hide-details
                />
              </v-col>
              <v-col
                cols="12"
                sm="6"
              >
                <v-select
                  v-model="restriction.defaultScope"
                  :items="scopeItems"
                  :label="$t('personal.people.scope')"
                  density="compact"
                  hide-details
                  data-testid="person-restriction-scope"
                />
              </v-col>
            </v-row>
            <p class="text-caption text-medium-emphasis mt-2 mb-0">
              {{ $t(`personal.enums.scope-help.${restriction.defaultScope}`) }}
            </p>
            <v-checkbox
              v-model="restriction.appliesWhenCooking"
              :label="$t('personal.people.applies-when-cooking')"
              density="compact"
              hide-details
            />
          </v-card>
          <v-btn
            variant="tonal"
            size="small"
            :prepend-icon="$globals.icons.createAlt"
            data-testid="person-add-restriction"
            @click="addRestriction"
          >
            {{ $t('personal.people.add-restriction') }}
          </v-btn>

          <v-divider class="my-4" />
          <v-autocomplete
            v-model="likes"
            :items="foods"
            item-title="name"
            item-value="id"
            :label="$t('personal.people.likes')"
            multiple
            chips
            closable-chips
            density="compact"
          />
          <v-autocomplete
            v-model="dislikes"
            :items="foods"
            item-title="name"
            item-value="id"
            :label="$t('personal.people.dislikes')"
            multiple
            chips
            closable-chips
            density="compact"
          />
          <v-textarea
            v-model="form.notes"
            :label="$t('personal.common.notes')"
            rows="2"
            auto-grow
          />
        </template>
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
        {{ $t('personal.people.delete-confirm', { name: deleting?.displayName }) }}
      </v-card-text>
    </BaseDialog>

    <BasePageTitle divider>
      <template #header>
        <v-icon
          size="80"
          color="primary"
          :icon="personalIcons.people"
        />
      </template>
      <template #title>
        {{ $t('personal.people.title') }}
      </template>
      {{ $t('personal.people.subtitle') }}
    </BasePageTitle>

    <div class="d-flex justify-end mb-4">
      <BaseButton
        create
        data-testid="person-create"
        @click="openCreate"
      />
    </div>

    <v-alert
      v-if="loaded && !persons.length"
      type="info"
      variant="tonal"
    >
      {{ $t('personal.people.empty') }}
    </v-alert>

    <v-card
      v-for="person in persons"
      :key="person.id"
      class="my-2 left-border"
      data-testid="person-card"
    >
      <v-card-title class="d-flex align-center flex-wrap">
        <span class="mr-2">{{ person.displayName }}</span>
        <v-chip
          v-if="person.linkedUserId"
          size="small"
          color="primary"
          class="mr-2"
        >
          {{ $t('personal.people.me-badge') }}
        </v-chip>
        <v-chip
          v-if="person.appetite !== 'NORMAL'"
          size="small"
          variant="outlined"
        >
          {{ $t(`personal.enums.appetite.${person.appetite}`) }}
        </v-chip>
        <v-spacer />
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.edit')"
          @click="openEdit(person)"
        >
          <v-icon>{{ $globals.icons.edit }}</v-icon>
        </v-btn>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.delete')"
          @click="askDelete(person)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <div
          v-if="person.restrictions.length"
          class="d-flex flex-wrap ga-2"
        >
          <v-chip
            v-for="restriction in person.restrictions"
            :key="restriction.id"
            size="small"
            :color="restriction.defaultScope === 'INDIVIDUAL' ? undefined : 'warning'"
            variant="tonal"
          >
            {{ restriction.restriction.name }} · {{ $t(`personal.enums.scope.${restriction.defaultScope}`) }}
          </v-chip>
        </div>
        <span
          v-else
          class="text-medium-emphasis"
        >{{ $t('personal.people.no-restriction') }}</span>
        <div
          v-if="person.foodPreferences.length"
          class="text-caption mt-2"
        >
          <span v-if="preferenceNames(person, 'LIKE')">
            {{ $t('personal.people.likes') }} : {{ preferenceNames(person, 'LIKE') }}
          </span>
          <span v-if="preferenceNames(person, 'DISLIKE')">
            · {{ $t('personal.people.dislikes') }} : {{ preferenceNames(person, 'DISLIKE') }}
          </span>
        </div>
        <div
          v-if="!person.linkedUserId"
          class="text-caption text-medium-emphasis mt-2"
        >
          {{ person.consentGivenAt
            ? $t('personal.people.consent-given', { date: $d(new Date(person.consentGivenAt), 'short') })
            : $t('personal.people.consent-missing') }}
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { useFoodStore } from "~/composables/store";
import { alert } from "~/composables/use-toast";
import type {
  Appetite,
  DietaryRestrictionOut,
  FoodPreferenceKind,
  PersonCreate,
  PersonOut,
  PersonRestrictionCreate,
  RestrictionScope,
  RestrictionSeverity,
} from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const { store: foods } = useFoodStore();

useSeoMeta({ title: i18n.t("personal.people.title") });

type RestrictionForm = Required<Pick<PersonRestrictionCreate, "restrictionId" | "severity" | "defaultScope" | "appliesWhenCooking">>;
interface PersonForm {
  displayName: string;
  appetite: Appetite;
  notes: string;
  isMe: boolean;
  consentGiven: boolean;
  consentNote: string;
  restrictions: RestrictionForm[];
}

const persons = ref<PersonOut[]>([]);
const restrictions = ref<DietaryRestrictionOut[]>([]);
const loaded = ref(false);

const dialog = ref(false);
const deleteDialog = ref(false);
const editing = ref<PersonOut | null>(null);
const deleting = ref<PersonOut | null>(null);
const likes = ref<string[]>([]);
const dislikes = ref<string[]>([]);

function emptyForm(): PersonForm {
  return { displayName: "", appetite: "NORMAL", notes: "", isMe: false, consentGiven: false, consentNote: "", restrictions: [] };
}
const form = ref<PersonForm>(emptyForm());

const canHoldData = computed(() => form.value.isMe || form.value.consentGiven);

const appetiteItems = computed(() =>
  (["SMALL", "NORMAL", "LARGE"] as Appetite[]).map(value => ({ value, title: i18n.t(`personal.enums.appetite.${value}`) })),
);
const severityItems = computed(() =>
  (["STRICT", "MODERATE", "PREFERENCE"] as RestrictionSeverity[]).map(value => ({
    value,
    title: i18n.t(`personal.enums.severity.${value}`),
  })),
);
const scopeItems = computed(() =>
  (["INDIVIDUAL", "ENTIRE_MEAL", "ENTIRE_PREPARATION"] as RestrictionScope[]).map(value => ({
    value,
    title: i18n.t(`personal.enums.scope.${value}`),
  })),
);
const restrictionItems = computed(() => restrictions.value.map(r => ({ value: r.id, title: r.name })));

async function refresh() {
  const [personsResult, restrictionsResult] = await Promise.all([
    api.persons.getAll(1, -1, { orderBy: "display_name", orderDirection: "asc" }),
    api.dietary.getRestrictions(),
  ]);
  persons.value = personsResult.data?.items ?? [];
  restrictions.value = restrictionsResult.data ?? [];
  loaded.value = true;
}

function preferenceNames(person: PersonOut, kind: FoodPreferenceKind): string {
  return person.foodPreferences
    .filter(preference => preference.kind === kind)
    .map(preference => preference.food.name)
    .join(", ");
}

function openCreate() {
  editing.value = null;
  form.value = emptyForm();
  form.value.isMe = !persons.value.some(person => person.linkedUserId);
  likes.value = [];
  dislikes.value = [];
  dialog.value = true;
}

function openEdit(person: PersonOut) {
  editing.value = person;
  form.value = {
    displayName: person.displayName,
    appetite: person.appetite,
    notes: person.notes ?? "",
    isMe: !!person.linkedUserId,
    consentGiven: !!person.consentGivenAt,
    consentNote: person.consentNote ?? "",
    restrictions: person.restrictions.map(r => ({
      restrictionId: r.restrictionId,
      severity: r.severity,
      defaultScope: r.defaultScope,
      appliesWhenCooking: r.appliesWhenCooking,
    })),
  };
  likes.value = person.foodPreferences.filter(p => p.kind === "LIKE").map(p => p.foodId);
  dislikes.value = person.foodPreferences.filter(p => p.kind === "DISLIKE").map(p => p.foodId);
  dialog.value = true;
}

function addRestriction() {
  const used = new Set(form.value.restrictions.map(r => r.restrictionId));
  const next = restrictions.value.find(r => !used.has(r.id));
  if (!next) {
    return;
  }
  form.value.restrictions.push({
    restrictionId: next.id,
    severity: "STRICT",
    defaultScope: "INDIVIDUAL",
    appliesWhenCooking: form.value.isMe,
  });
}

async function save() {
  const holdsData = canHoldData.value;
  const payload: PersonCreate = {
    displayName: form.value.displayName.trim(),
    appetite: form.value.appetite,
    isMe: form.value.isMe,
    consentGiven: form.value.consentGiven,
    consentNote: form.value.consentNote || null,
    notes: holdsData ? form.value.notes || null : null,
    restrictions: holdsData ? form.value.restrictions : [],
    foodPreferences: holdsData
      ? [
          ...likes.value.map(foodId => ({ foodId, kind: "LIKE" as const })),
          ...dislikes.value.filter(foodId => !likes.value.includes(foodId)).map(foodId => ({ foodId, kind: "DISLIKE" as const })),
        ]
      : [],
  };

  const { data } = editing.value
    ? await api.persons.updateOne(editing.value.id, payload)
    : await api.persons.createOne(payload);
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    dialog.value = false;
    await refresh();
  }
}

function askDelete(person: PersonOut) {
  deleting.value = person;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.persons.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await refresh();
  }
}

onMounted(refresh);
</script>
