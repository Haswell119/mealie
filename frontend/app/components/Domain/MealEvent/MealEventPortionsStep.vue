<template>
  <div>
    <v-alert
      variant="tonal"
      color="primary"
      :icon="personalIcons.people"
      class="mb-4"
      data-testid="portions-summary"
    >
      <div class="font-weight-medium">
        {{ $t('personal.events.guests.summary-persons', analysis?.totalPersons ?? 0) }}
        · {{ $t('personal.events.guests.summary-portions', { portions: text.quantity(analysis?.totalPortions ?? 0) }) }}
      </div>
      <div class="text-caption">
        {{ $t('personal.events.portions.help') }}
      </div>
    </v-alert>

    <v-alert
      v-if="!menu.length"
      type="info"
      variant="tonal"
      data-testid="portions-empty"
    >
      {{ $t('personal.events.portions.empty') }}
    </v-alert>

    <section
      v-for="item in menu"
      :key="item.menuItemId"
      class="mb-5"
      data-testid="portions-item"
    >
      <h3 class="text-h6 mb-2">
        {{ menuItemLabels[item.menuItemId] ?? '' }}
      </h3>
      <p
        v-if="!item.variants.length"
        class="text-body-2 text-medium-emphasis"
      >
        {{ $t('personal.events.portions.no-recipe') }}
      </p>
      <v-card
        v-for="variant in item.variants"
        :key="variant.variantId"
        variant="outlined"
        class="mb-2 pa-3"
        data-testid="portions-variant"
      >
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
          <NuxtLink
            v-if="variant.recipeSlug"
            :to="recipeLink(variant)"
            class="font-weight-medium recipe-link"
            data-testid="portions-recipe-link"
          >
            {{ variant.recipeName }}
          </NuxtLink>
          <span
            v-else
            class="font-weight-medium"
          >{{ variant.label || $t('personal.enums.finding.RECIPE_NOT_FOUND') }}</span>
          <v-chip
            v-if="variant.label && variant.recipeSlug"
            size="small"
            variant="tonal"
          >
            {{ variant.label }}
          </v-chip>
        </div>

        <v-alert
          v-if="variant.error === 'MISSING_SERVINGS'"
          type="error"
          variant="tonal"
          density="compact"
          data-testid="portions-missing-servings"
        >
          {{ $t('personal.events.portions.missing-servings') }}
          <NuxtLink
            :to="recipeLink(variant)"
            class="d-block mt-1"
            data-testid="portions-missing-servings-link"
          >
            {{ $t('personal.events.portions.open-recipe', { recipe: variant.recipeName }) }}
          </NuxtLink>
        </v-alert>
        <v-alert
          v-else-if="variant.error"
          type="error"
          variant="tonal"
          density="compact"
        >
          {{ $t(`personal.enums.finding.${variant.error}`) }}
        </v-alert>
        <p
          v-else-if="variant.portions <= 0"
          class="text-body-2 text-medium-emphasis mb-0"
          data-testid="portions-not-cooked"
        >
          {{ $t('personal.events.portions.not-cooked') }}
        </p>

        <v-row
          v-if="!variant.error && variant.portions > 0"
          density="compact"
        >
          <v-col
            v-for="metric in metrics(variant)"
            :key="metric.key"
            cols="6"
            sm="3"
          >
            <div class="text-caption text-medium-emphasis">
              {{ metric.label }}
            </div>
            <div
              class="text-h6"
              :data-testid="`portions-${metric.key}`"
            >
              {{ metric.value }}
            </div>
          </v-col>
        </v-row>
        <p
          v-if="variant.personNames.length"
          class="text-caption text-medium-emphasis mt-2 mb-0"
        >
          {{ $t('personal.events.menu.eaten-by', { names: variant.personNames.join(', ') }) }}
        </p>
      </v-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type { MealEventAnalysisOut, VariantAnalysisOut } from "~/lib/api/types/personal";

const props = defineProps<{
  analysis: MealEventAnalysisOut | null;
  /** The label of each dish of the menu, by its id. */
  menuItemLabels: Record<string, string>;
}>();

const i18n = useI18n();
const text = usePersonalText();
const auth = useMealieAuth();

const menu = computed(() => props.analysis?.menu ?? []);

function recipeLink(variant: VariantAnalysisOut): string {
  return `/g/${auth.user.value?.groupSlug ?? ""}/r/${variant.recipeSlug}`;
}

function metrics(variant: VariantAnalysisOut) {
  return [
    { key: "persons", label: i18n.t("personal.events.portions.persons"), value: String(variant.personIds.length) },
    { key: "portions", label: i18n.t("personal.events.portions.portions"), value: text.quantity(variant.portions) },
    { key: "servings", label: i18n.t("personal.events.portions.recipe-servings"), value: text.quantity(variant.recipeServings) },
    { key: "scale", label: i18n.t("personal.events.portions.scale"), value: `× ${text.quantity(variant.scale)}` },
  ];
}
</script>

<style scoped>
.recipe-link {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
