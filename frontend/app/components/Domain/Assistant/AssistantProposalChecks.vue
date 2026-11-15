<template>
  <div
    v-if="checks.length"
    class="d-flex flex-wrap ga-2 mt-1"
    data-testid="assistant-proposal-checks"
  >
    <span
      v-for="item in checks"
      :key="item.restriction"
      class="d-inline-flex align-center ga-1"
    >
      <span class="text-caption">{{ restrictionNames?.[item.restriction] ?? item.restriction }}</span>
      <PersonalStatusChip
        :status="item.status"
        size="x-small"
      />
    </span>
  </div>
</template>

<script setup lang="ts">
import PersonalStatusChip from "~/components/Domain/Personal/PersonalStatusChip.vue";
import type { VerificationStatus } from "~/lib/api/types/personal";

/** The verification status of one line of a proposal, for each dietary restriction that applies. */
defineProps<{
  checks: { restriction: string; status: VerificationStatus }[];
  /** Names of the dietary restrictions by key, e.g. `gluten` → `Sans gluten`. */
  restrictionNames?: Record<string, string>;
}>();
</script>
