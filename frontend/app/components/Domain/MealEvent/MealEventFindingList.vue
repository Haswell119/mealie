<template>
  <ul class="finding-list">
    <li
      v-for="(finding, index) in sorted"
      :key="index"
      class="d-flex align-start ga-2 py-1"
      data-testid="event-finding"
      :data-status="finding.status"
    >
      <v-icon
        size="small"
        class="mt-1 flex-shrink-0"
        :color="finding.status === 'INCOMPATIBLE' ? 'error' : 'warning'"
        :icon="finding.status === 'INCOMPATIBLE' ? mdiCloseCircle : mdiAlertCircle"
      />
      <div class="finding-text">
        <div :class="finding.status === 'INCOMPATIBLE' ? 'font-weight-bold text-error' : undefined">
          {{ text.finding(finding) }}
        </div>
        <div class="text-caption text-medium-emphasis">
          {{ context(finding) }}
        </div>
        <NuxtLink
          v-if="verifyLinks && finding.foodId"
          :to="`/dietary?food=${finding.foodId}`"
          class="text-caption"
          data-testid="event-finding-verify"
        >
          {{ $t('personal.events.review.verify-food') }}
        </NuxtLink>
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { mdiAlertCircle, mdiCloseCircle } from "@mdi/js";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import type { FindingOut } from "~/lib/api/types/personal";

const props = withDefaults(
  defineProps<{
    findings: FindingOut[];
    /** The name of each restriction, by its key. */
    restrictionNames: Record<string, string>;
    /** Name the recipe of each finding: for lists that mix several recipes. */
    showRecipe?: boolean;
    /** Link each food to the page where the user verifies it. */
    verifyLinks?: boolean;
  }>(),
  { showRecipe: false, verifyLinks: false },
);

const i18n = useI18n();
const text = usePersonalText();

const sorted = computed(() =>
  [...props.findings].sort((a, b) => Number(b.status === "INCOMPATIBLE") - Number(a.status === "INCOMPATIBLE")),
);

/** What the finding is about: the ingredient, tool or dish, the restriction, and the recipe. */
function context(finding: FindingOut): string {
  // A dish without a title is named by the code of its course.
  const courseKey = `personal.enums.course.${finding.subject}`;
  const subject = finding.kind === "menu_item" && i18n.te(courseKey) ? i18n.t(courseKey) : finding.subject;
  const parts = [subject, props.restrictionNames[finding.restrictionKey] ?? finding.restrictionKey];
  if (props.showRecipe && finding.recipeName && finding.recipeName !== finding.subject) {
    parts.push(finding.recipeName);
  }
  return parts.filter(Boolean).join(" · ");
}
</script>

<style scoped>
.finding-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.finding-text {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
