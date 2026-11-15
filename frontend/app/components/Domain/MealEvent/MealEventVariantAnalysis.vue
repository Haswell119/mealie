<template>
  <div
    data-testid="menu-variant-analysis"
    :data-status="result.status"
  >
    <div class="d-flex align-center flex-wrap ga-2">
      <PersonalStatusChip :status="result.status" />
      <span
        v-if="result.personNames.length"
        class="text-body-2"
        data-testid="menu-variant-eaters"
      >
        {{ $t('personal.events.menu.eaten-by', { names: result.personNames.join(', ') }) }}
      </span>
      <span
        v-else
        class="text-body-2 text-medium-emphasis"
      >
        {{ $t('personal.events.menu.eaten-by-nobody') }}
      </span>
    </div>

    <v-alert
      v-if="result.error"
      type="error"
      variant="tonal"
      density="compact"
      class="mt-2"
      data-testid="menu-variant-error"
    >
      {{ $t(`personal.enums.finding.${result.error}`) }}
    </v-alert>

    <template v-if="result.findings.length">
      <v-btn
        variant="text"
        size="small"
        class="mt-1 px-1"
        :color="result.status === 'INCOMPATIBLE' ? 'error' : undefined"
        :append-icon="open ? mdiChevronUp : mdiChevronDown"
        :aria-expanded="open"
        data-testid="menu-variant-findings-toggle"
        @click="open = !open"
      >
        {{ $t('personal.events.menu.findings', result.findings.length) }}
      </v-btn>
      <v-expand-transition>
        <MealEventFindingList
          v-show="open"
          :findings="result.findings"
          :restriction-names="restrictionNames"
          data-testid="menu-variant-findings"
        />
      </v-expand-transition>
    </template>
  </div>
</template>

<script setup lang="ts">
import { mdiChevronDown, mdiChevronUp } from "@mdi/js";
import MealEventFindingList from "~/components/Domain/MealEvent/MealEventFindingList.vue";
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import type { VariantAnalysisOut } from "~/lib/api/types/personal";

const props = defineProps<{
  result: VariantAnalysisOut;
  /** The name of each restriction, by its key. */
  restrictionNames: Record<string, string>;
}>();

// The reasons of an incompatible recipe are open from the start: the user must not have to look for them.
const open = ref(props.result.status === "INCOMPATIBLE");

watch(
  () => props.result.status,
  (status) => {
    if (status === "INCOMPATIBLE") {
      open.value = true;
    }
  },
);
</script>
