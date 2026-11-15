<template>
  <div
    class="d-flex align-center flex-wrap ga-1"
    data-testid="inspiration-workflow"
  >
    <template
      v-for="(step, index) in steps"
      :key="step"
    >
      <InspirationStatusChip
        :status="step"
        :active="step === current"
      />
      <v-icon
        v-if="index < steps.length - 1"
        size="small"
        class="text-medium-emphasis"
        :icon="$globals.icons.chevronRight"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import InspirationStatusChip from "~/components/Domain/Inspiration/InspirationStatusChip.vue";
import type { InspirationStatus } from "~/lib/api/types/personal";

/** The three steps of an inspiration. Without `current`, every step is shown the same way. */
defineProps<{ current?: InspirationStatus | null }>();

const steps: InspirationStatus[] = ["INSPIRATION", "DRAFT", "VALIDATED"];
</script>
