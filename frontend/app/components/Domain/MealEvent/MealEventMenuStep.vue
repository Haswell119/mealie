<template>
  <div>
    <p class="text-body-2 text-medium-emphasis mb-4">
      {{ $t('personal.events.menu.help') }}
    </p>

    <v-alert
      v-if="!items.length"
      type="info"
      variant="tonal"
      class="mb-4"
      data-testid="menu-empty"
    >
      {{ $t('personal.events.menu.empty') }}
    </v-alert>

    <v-card
      v-for="(item, itemIndex) in items"
      :key="item.key"
      class="mb-4 left-border"
      data-testid="menu-item"
    >
      <v-card-text class="pa-3">
        <div class="d-flex align-center mb-2">
          <span class="text-subtitle-1 font-weight-medium flex-grow-1">
            {{ $t('personal.events.menu.item-number', { number: itemIndex + 1 }) }}
          </span>
          <v-btn
            icon
            size="small"
            variant="text"
            :disabled="itemIndex === 0"
            :aria-label="$t('personal.events.menu.move-up')"
            data-testid="menu-item-up"
            @click="moveItem(itemIndex, -1)"
          >
            <v-icon :icon="mdiArrowUp" />
          </v-btn>
          <v-btn
            icon
            size="small"
            variant="text"
            :disabled="itemIndex === items.length - 1"
            :aria-label="$t('personal.events.menu.move-down')"
            data-testid="menu-item-down"
            @click="moveItem(itemIndex, 1)"
          >
            <v-icon :icon="mdiArrowDown" />
          </v-btn>
          <v-btn
            icon
            size="small"
            variant="text"
            :aria-label="$t('personal.events.menu.remove-item')"
            data-testid="menu-item-remove"
            @click="items.splice(itemIndex, 1)"
          >
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>

        <v-row density="compact">
          <v-col
            cols="12"
            sm="5"
          >
            <v-select
              v-model="item.course"
              :items="courseItems"
              :label="$t('personal.events.menu.course')"
              density="compact"
              hide-details
              data-testid="menu-item-course"
            />
          </v-col>
          <v-col
            cols="12"
            sm="7"
          >
            <v-text-field
              v-model="item.title"
              :label="`${$t('personal.events.menu.item-title')} (${$t('personal.common.optional')})`"
              density="compact"
              hide-details
              data-testid="menu-item-title"
            />
          </v-col>
        </v-row>

        <div
          v-if="sharedConstraints(item).length"
          class="d-flex flex-wrap align-center ga-1 mt-3"
          data-testid="menu-item-constraints"
        >
          <span class="text-caption text-medium-emphasis mr-1">{{ $t('personal.events.menu.item-constraints') }}</span>
          <v-chip
            v-for="constraint in sharedConstraints(item)"
            :key="constraint.restrictionKey"
            size="small"
            color="warning"
            variant="tonal"
          >
            {{ constraint.restrictionName }} · {{ $t(`personal.enums.scope.${constraint.scope}`) }}
          </v-chip>
        </div>

        <v-alert
          v-if="unassignedNames(item).length"
          type="error"
          variant="tonal"
          density="compact"
          class="mt-3"
          data-testid="menu-item-unassigned"
        >
          {{ $t('personal.events.menu.unassigned', { names: unassignedNames(item).join(', ') }, unassignedNames(item).length) }}
        </v-alert>

        <v-card
          v-for="(variant, variantIndex) in item.variants"
          :key="variant.key"
          variant="outlined"
          class="mt-3 pa-3"
          data-testid="menu-variant"
        >
          <v-autocomplete
            v-model="variant.recipeId"
            :items="recipeItems"
            item-title="name"
            item-value="id"
            :label="$t('personal.common.recipe')"
            :loading="!recipesLoaded"
            :no-data-text="$t('personal.events.menu.no-recipe')"
            density="compact"
            hide-details
            auto-select-first
            data-testid="menu-variant-recipe"
          />
          <div class="d-flex align-center mt-2">
            <v-text-field
              v-model="variant.label"
              :label="`${$t('personal.events.menu.variant-label')} (${$t('personal.common.optional')})`"
              :placeholder="$t('personal.events.menu.variant-label-placeholder')"
              density="compact"
              hide-details
              data-testid="menu-variant-label"
            />
            <v-btn
              icon
              size="small"
              variant="text"
              class="ml-1"
              :aria-label="$t('personal.events.menu.remove-variant')"
              data-testid="menu-variant-remove"
              @click="item.variants.splice(variantIndex, 1)"
            >
              <v-icon>{{ $globals.icons.delete }}</v-icon>
            </v-btn>
          </div>

          <MealEventVariantAnalysis
            v-if="variantAnalysis(item, variant)"
            :result="variantAnalysis(item, variant)!"
            :restriction-names="restrictionNames"
            class="mt-3"
          />
        </v-card>

        <v-btn
          variant="tonal"
          size="small"
          class="mt-3"
          :prepend-icon="$globals.icons.createAlt"
          data-testid="menu-variant-add"
          @click="item.variants.push(newVariant())"
        >
          {{ item.variants.length ? $t('personal.events.menu.add-variant') : $t('personal.events.menu.add-recipe') }}
        </v-btn>
        <p
          v-if="item.variants.length === 1"
          class="text-caption text-medium-emphasis mt-1 mb-0"
        >
          {{ $t('personal.events.menu.variant-help') }}
        </p>

        <v-expansion-panels
          v-if="savedItem(item)?.variants.length && attendingGuests.length"
          flat
          class="mt-3 assignments"
          data-testid="menu-assignments"
        >
          <v-expansion-panel>
            <v-expansion-panel-title class="px-3">
              {{ $t('personal.events.menu.assignments-title') }}
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <p class="text-caption text-medium-emphasis">
                {{ $t('personal.events.menu.assignments-help') }}
              </p>
              <v-select
                v-for="guest in attendingGuests"
                :key="guest.personId"
                :model-value="assignmentOf(item, guest.personId)"
                :items="assignmentItems(item)"
                :label="guest.person.displayName"
                :hint="assignmentHint(item, guest.personId)"
                :disabled="assigning"
                persistent-hint
                density="compact"
                class="mb-2"
                data-testid="menu-assignment"
                :data-person="guest.person.displayName"
                @update:model-value="setAssignment(item, guest.personId, $event)"
              />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
    </v-card>

    <v-btn
      variant="tonal"
      color="primary"
      block
      :prepend-icon="$globals.icons.createAlt"
      data-testid="menu-item-add"
      @click="addItem"
    >
      {{ $t('personal.events.menu.add-item') }}
    </v-btn>

    <v-alert
      v-if="dirty"
      type="warning"
      variant="tonal"
      density="compact"
      class="mt-4"
      data-testid="menu-unsaved"
    >
      {{ valid ? $t('personal.events.menu.unsaved') : $t('personal.events.menu.missing-recipe') }}
    </v-alert>

    <div class="d-flex justify-end mt-4">
      <BaseButton
        save
        :disabled="!dirty || !valid"
        :loading="saving"
        data-testid="menu-save"
        @click="save"
      >
        {{ $t('personal.events.menu.save') }}
      </BaseButton>
    </div>
  </div>
</template>

<script setup lang="ts">
import { mdiArrowDown, mdiArrowUp } from "@mdi/js";
import MealEventVariantAnalysis from "~/components/Domain/MealEvent/MealEventVariantAnalysis.vue";
import { useUserApi } from "~/composables/api";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { alert } from "~/composables/use-toast";
import type {
  AppliedConstraintOut,
  MealCourse,
  MealEventAnalysisOut,
  MealEventMenuItemCreate,
  MealEventMenuItemOut,
  MealEventOut,
  MenuItemAnalysisOut,
  VariantAnalysisOut,
} from "~/lib/api/types/personal";

const props = defineProps<{
  event: MealEventOut;
  analysis: MealEventAnalysisOut | null;
  /** The name of each restriction, by its key. */
  restrictionNames: Record<string, string>;
}>();

const emit = defineEmits<{ (e: "updated", event: MealEventOut): void }>();

interface VariantDraft {
  key: string;
  id: string | null;
  recipeId: string | null;
  label: string;
  portionsOverride: number | null;
}
interface ItemDraft {
  key: string;
  id: string | null;
  course: MealCourse;
  title: string;
  variants: VariantDraft[];
}
interface RecipeItem {
  id: string;
  name: string;
}

const COURSES: MealCourse[] = ["APERITIF", "STARTER", "MAIN", "SIDE", "DESSERT", "OTHER"];
/** The value of "let the application choose" in the select of a dish for a guest. */
const AUTOMATIC = "automatic";

const i18n = useI18n();
const api = usePersonalApi();
const userApi = useUserApi();

const items = ref<ItemDraft[]>([]);
const recipes = ref<RecipeItem[]>([]);
const recipesLoaded = ref(false);
const saving = ref(false);
const assigning = ref(false);

let nextKey = 0;
function newKey(): string {
  nextKey += 1;
  return `new-${nextKey}`;
}

function newVariant(): VariantDraft {
  return { key: newKey(), id: null, recipeId: null, label: "", portionsOverride: null };
}

function savedItems(): ItemDraft[] {
  return [...props.event.menuItems]
    .sort((a, b) => a.position - b.position)
    .map(item => ({
      key: item.id,
      id: item.id,
      course: item.course,
      title: item.title ?? "",
      variants: [...item.variants]
        .sort((a, b) => a.position - b.position)
        .map(variant => ({
          key: variant.id,
          id: variant.id,
          recipeId: variant.recipeId,
          label: variant.label ?? "",
          portionsOverride: variant.portionsOverride,
        })),
    }));
}

/** What the server receives. The ids of the saved dishes and variants go along, so that the server keeps them. */
function payloadOf(list: ItemDraft[]): MealEventMenuItemCreate[] {
  return list.map(item => ({
    id: item.id,
    course: item.course,
    title: item.title.trim() || null,
    variants: item.variants.map(variant => ({
      id: variant.id,
      recipeId: variant.recipeId ?? "",
      label: variant.label.trim() || null,
      portionsOverride: variant.portionsOverride,
    })),
  }));
}

const savedPayload = computed(() => JSON.stringify(payloadOf(savedItems())));
const dirty = computed(() => JSON.stringify(payloadOf(items.value)) !== savedPayload.value);
const valid = computed(() => items.value.every(item => item.variants.every(variant => !!variant.recipeId)));

// The draft follows the saved menu. A change elsewhere in the event leaves unsaved edits alone.
watch(
  savedPayload,
  () => {
    items.value = savedItems();
  },
  { immediate: true },
);

const courseItems = computed(() =>
  COURSES.map(value => ({ value, title: i18n.t(`personal.enums.course.${value}`) })),
);

/** The recipes of the household, plus the ones of the menu that the list does not hold. */
const recipeItems = computed<RecipeItem[]>(() => {
  const known = new Set(recipes.value.map(recipe => recipe.id));
  const extra: RecipeItem[] = [];
  for (const item of props.analysis?.menu ?? []) {
    for (const variant of item.variants) {
      if (!known.has(variant.recipeId) && variant.recipeName) {
        known.add(variant.recipeId);
        extra.push({ id: variant.recipeId, name: variant.recipeName });
      }
    }
  }
  return [...recipes.value, ...extra];
});

const attendingGuests = computed(() => props.event.guests.filter(guest => guest.attending));

function savedItem(item: ItemDraft): MealEventMenuItemOut | undefined {
  return props.event.menuItems.find(saved => saved.id === item.id);
}

function itemAnalysis(item: ItemDraft): MenuItemAnalysisOut | undefined {
  return props.analysis?.menu.find(result => result.menuItemId === item.id);
}

/** The analysis of a variant, as long as the draft still holds the recipe that the server checked. */
function variantAnalysis(item: ItemDraft, variant: VariantDraft): VariantAnalysisOut | undefined {
  const result = itemAnalysis(item)?.variants.find(candidate => candidate.variantId === variant.id);
  return result && result.recipeId === variant.recipeId ? result : undefined;
}

function sharedConstraints(item: ItemDraft): AppliedConstraintOut[] {
  return itemAnalysis(item)?.constraints.shared ?? [];
}

function unassignedNames(item: ItemDraft): string[] {
  return itemAnalysis(item)?.unassignedPersonNames ?? [];
}

function variantName(item: ItemDraft, variantId: string): string {
  const saved = savedItem(item)?.variants.find(variant => variant.id === variantId);
  const result = itemAnalysis(item)?.variants.find(variant => variant.variantId === variantId);
  const recipeName = result?.recipeName || recipeItems.value.find(recipe => recipe.id === saved?.recipeId)?.name || "";
  return saved?.label ? `${saved.label} (${recipeName})` : recipeName;
}

function assignmentItems(item: ItemDraft) {
  return [
    { value: AUTOMATIC, title: i18n.t("personal.events.menu.assignment-automatic") },
    ...(savedItem(item)?.variants ?? []).map(variant => ({ value: variant.id, title: variantName(item, variant.id) })),
  ];
}

function assignmentOf(item: ItemDraft, personId: string): string {
  const assignment = props.event.assignments.find(
    candidate => candidate.menuItemId === item.id && candidate.personId === personId,
  );
  return assignment?.variantId ?? AUTOMATIC;
}

/** The dish that the person gets, whether chosen by hand or by the application. */
function assignmentHint(item: ItemDraft, personId: string): string {
  const result = itemAnalysis(item);
  if (!result) {
    return "";
  }
  const variant = result.variants.find(candidate => candidate.personIds.includes(personId));
  if (!variant) {
    return i18n.t("personal.events.menu.assignment-none");
  }
  return i18n.t("personal.events.menu.assignment-result", { recipe: variantName(item, variant.variantId) });
}

function addItem() {
  const used = new Set(items.value.map(item => item.course));
  const course = (["MAIN", "STARTER", "DESSERT", "APERITIF", "SIDE"] as MealCourse[]).find(c => !used.has(c)) ?? "OTHER";
  items.value.push({ key: newKey(), id: null, course, title: "", variants: [newVariant()] });
}

function moveItem(index: number, offset: number) {
  const target = index + offset;
  const [moved] = items.value.splice(index, 1);
  if (moved) {
    items.value.splice(target, 0, moved);
  }
}

async function save() {
  if (saving.value || !valid.value) {
    return;
  }
  saving.value = true;
  const { data } = await api.mealEvents.setMenu(props.event.id, payloadOf(items.value));
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    emit("updated", data);
  }
}

async function setAssignment(item: ItemDraft, personId: string, value: string) {
  if (!item.id || assigning.value) {
    return;
  }
  assigning.value = true;
  const { data } = await api.mealEvents.setAssignment(props.event.id, {
    menuItemId: item.id,
    personId,
    variantId: value === AUTOMATIC ? null : value,
  });
  assigning.value = false;
  if (data) {
    emit("updated", data);
  }
}

onMounted(async () => {
  const { data } = await userApi.recipes.getAll(1, -1, { orderBy: "name", orderDirection: "asc" });
  recipes.value = (data?.items ?? []).map(recipe => ({ id: recipe.id, name: recipe.name }));
  recipesLoaded.value = true;
});
</script>

<style scoped>
.assignments {
  border: thin solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}
</style>
