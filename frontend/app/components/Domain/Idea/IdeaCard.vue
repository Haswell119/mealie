<template>
  <v-card
    class="my-2 idea-card"
    :to="target"
    data-testid="idea-card"
    :data-kind="card.kind"
    :data-compliance="card.compliance ?? ''"
  >
    <div class="d-flex">
      <div
        v-if="hasImage"
        class="idea-card__thumb"
      >
        <v-img
          v-if="card.kind === 'RECIPE'"
          :src="recipeSmallImage(card.id, card.image)"
          :alt="card.title"
          cover
          height="100%"
          @error="imageFailed = true"
        />
        <InspirationImage
          v-else
          class="idea-card__inspiration-image"
          :inspiration-id="card.id"
          :version="card.image ?? ''"
          :alt="card.title"
          cover
        />
      </div>
      <div class="idea-card__body pa-3">
        <div class="d-flex align-start ga-2">
          <v-icon
            class="mt-1 text-medium-emphasis"
            size="small"
            :icon="card.kind === 'RECIPE' ? mdiSilverwareForkKnife : personalIcons.inspirations"
          />
          <span
            class="text-subtitle-1 font-weight-medium idea-card__wrap"
            data-testid="idea-card-title"
          >{{ card.title }}</span>
        </div>

        <div
          v-if="card.description"
          class="text-body-2 text-medium-emphasis mt-1 idea-card__description"
        >
          {{ card.description }}
        </div>

        <div
          class="d-flex flex-wrap ga-1 mt-2"
          data-testid="idea-card-tags"
        >
          <v-chip
            v-for="chip in chips"
            :key="chip.key"
            size="small"
            label
            :color="chip.color"
            :variant="chip.color ? 'tonal' : 'outlined'"
            :prepend-icon="chip.icon"
            :data-testid="`idea-tag-${chip.key}`"
          >
            {{ chip.text }}
          </v-chip>
        </div>

        <div
          v-if="missing"
          class="text-body-2 text-medium-emphasis mt-2"
          data-testid="idea-card-missing"
        >
          {{ missing }}
        </div>
      </div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import {
  mdiAlertCircleOutline,
  mdiCashMultiple,
  mdiCheckCircleOutline,
  mdiCloseCircleOutline,
  mdiFridgeOutline,
  mdiLeaf,
  mdiNewBox,
  mdiSale,
  mdiSilverwareForkKnife,
  mdiSproutOutline,
  mdiStarOutline,
  mdiTimerOutline,
} from "@mdi/js";
import InspirationImage from "~/components/Domain/Inspiration/InspirationImage.vue";
import { useStaticRoutes } from "~/composables/api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type { IdeaCard } from "~/lib/api/types/personal";

interface Chip {
  key: string;
  text: string;
  icon?: string;
  color?: string;
}

const MAX_MISSING = 4;

const props = withDefaults(defineProps<{ card: IdeaCard; restrictionNames?: Record<string, string> }>(), {
  restrictionNames: () => ({}),
});

const i18n = useI18n();
const auth = useMealieAuth();
const text = usePersonalText();
const { recipeSmallImage } = useStaticRoutes();

const imageFailed = ref(false);
watch(
  () => [props.card.id, props.card.image],
  () => {
    imageFailed.value = false;
  },
);
const hasImage = computed(() => !!props.card.image && !imageFailed.value);

/** A recipe opens as a recipe; an inspiration opens in the page of the inspirations. */
const target = computed(() => {
  if (props.card.kind === "RECIPE" && props.card.recipeSlug) {
    return `/g/${auth.user.value?.groupSlug || ""}/r/${props.card.recipeSlug}`;
  }
  return `/inspirations?open=${props.card.id}`;
});

function restrictions(value: string | null): string {
  return (value ?? "")
    .split(",")
    .map(key => key.trim())
    .filter(Boolean)
    .map(key => props.restrictionNames[key] ?? key)
    .join(", ");
}

function stores(value: string | null): string {
  return (value ?? "")
    .split(",")
    .map(store => store.trim())
    .filter(Boolean)
    .map(store => text.store(store))
    .join(", ");
}

/** 45 min, 1 h, 1 h 30: a long cooking time reads better in hours. */
function duration(minutes: number): string {
  if (minutes < 60) {
    return i18n.t("personal.ideas.minutes", { value: minutes });
  }
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest
    ? i18n.t("personal.ideas.hours-minutes", { hours, minutes: String(rest).padStart(2, "0") })
    : i18n.t("personal.ideas.hours", { hours });
}

const complianceLook: Record<string, { icon: string; color: string }> = {
  COMPATIBLE: { icon: mdiCheckCircleOutline, color: "success" },
  TO_CHECK: { icon: mdiAlertCircleOutline, color: "warning" },
  INCOMPATIBLE: { icon: mdiCloseCircleOutline, color: "error" },
};

/** The tags of the card as chips: what matters for a decision first, the labels of the user last. */
const chips = computed<Chip[]>(() => {
  const card = props.card;
  const tags = new Map(card.tags.map(tag => [tag.key, tag]));
  const list: Chip[] = [];

  for (const key of ["INCOMPATIBLE", "TO_CHECK", "COMPATIBLE"]) {
    const tag = tags.get(key);
    if (tag) {
      const names = restrictions(tag.value);
      list.push({
        key,
        text: names ? i18n.t(`personal.ideas.chip.${key}`, { value: names }) : i18n.t(`personal.ideas.tag.${key}`),
        ...complianceLook[key],
      });
    }
  }

  if (card.minutes !== null) {
    list.push({
      key: tags.has("QUICK") ? "QUICK" : "TIME",
      text: duration(card.minutes),
      icon: mdiTimerOutline,
      color: tags.has("QUICK") ? "primary" : undefined,
    });
  }

  if (tags.has("ALL_IN_STOCK")) {
    list.push({ key: "ALL_IN_STOCK", text: i18n.t("personal.ideas.tag.ALL_IN_STOCK"), icon: mdiFridgeOutline, color: "success" });
  }
  else if (card.stockTotal > 0 && card.stockHave > 0) {
    list.push({
      key: "IN_STOCK",
      text: i18n.t("personal.ideas.chip.IN_STOCK", { value: `${card.stockHave}/${card.stockTotal}` }),
      icon: mdiFridgeOutline,
      color: tags.has("IN_STOCK") ? "success" : undefined,
    });
  }

  const seasonal = tags.get("SEASONAL");
  if (seasonal) {
    list.push({
      key: "SEASONAL",
      text: i18n.t("personal.ideas.chip.SEASONAL", { value: seasonal.value ?? "" }),
      icon: mdiSproutOutline,
      color: "success",
    });
  }

  if (card.costPerServing !== null) {
    list.push({
      key: "COST",
      text: i18n.t("personal.ideas.per-serving", { price: text.money(card.costPerServing) }),
      icon: mdiCashMultiple,
    });
  }
  const promotion = tags.get("PROMOTION");
  if (promotion) {
    list.push({
      key: "PROMOTION",
      text: i18n.t("personal.ideas.chip.PROMOTION", { value: stores(promotion.value) }),
      icon: mdiSale,
      color: "secondary",
    });
  }

  for (const key of ["HINT_VEGAN", "HINT_VEGETARIAN"]) {
    if (tags.has(key)) {
      list.push({ key, text: i18n.t(`personal.ideas.tag.${key}`), icon: mdiLeaf });
      break;
    }
  }

  const rated = tags.get("TOP_RATED");
  if (rated) {
    list.push({ key: "TOP_RATED", text: i18n.t("personal.ideas.chip.TOP_RATED", { value: rated.value ?? "" }), icon: mdiStarOutline });
  }
  if (tags.has("NEW")) {
    list.push({ key: "NEW", text: i18n.t("personal.ideas.tag.NEW"), icon: mdiNewBox });
  }
  if (tags.has("NEVER_MADE")) {
    list.push({ key: "NEVER_MADE", text: i18n.t("personal.ideas.tag.NEVER_MADE") });
  }
  if (tags.has("INSPIRATION")) {
    list.push({ key: "INSPIRATION", text: i18n.t("personal.ideas.tag.INSPIRATION"), icon: personalIcons.inspirations });
  }

  for (const tag of card.tags) {
    if (tag.kind === "LABEL" && tag.value) {
      list.push({ key: tag.key, text: tag.value });
    }
  }
  return list;
});

const missing = computed(() => {
  const foods = props.card.missingFoods;
  if (!foods.length || !props.card.stockHave) {
    return "";
  }
  const shown = foods.slice(0, MAX_MISSING).join(", ");
  const rest = foods.length - MAX_MISSING;
  return rest > 0
    ? i18n.t("personal.ideas.missing-more", { foods: shown, count: rest }, rest)
    : i18n.t("personal.ideas.missing", { foods: shown });
});
</script>

<style scoped>
.idea-card__thumb {
  flex: 0 0 104px;
  width: 104px;
  min-height: 104px;
  overflow: hidden;
}

.idea-card__inspiration-image {
  height: 100%;
}

.idea-card__body {
  flex: 1 1 auto;
  min-width: 0;
}

.idea-card__wrap {
  overflow-wrap: anywhere;
  line-height: 1.4;
}

.idea-card__description {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  overflow-wrap: anywhere;
}
</style>
