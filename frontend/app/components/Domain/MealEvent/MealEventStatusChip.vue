<template>
  <v-chip
    :color="color"
    :variant="status === 'DRAFT' ? 'tonal' : 'flat'"
    size="small"
    label
    data-testid="event-status-chip"
    :data-status="status"
  >
    {{ $t(`personal.events.status.${status}`) }}
  </v-chip>
</template>

<script setup lang="ts">
import type { MealEventStatus } from "~/lib/api/types/personal";

const props = defineProps<{ status: MealEventStatus }>();

const color = computed(() => ({ DRAFT: undefined, PLANNED: "success", DONE: "info" })[props.status]);
</script>
