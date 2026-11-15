<template>
  <v-chip
    :color="color"
    :size="size"
    :variant="active ? 'flat' : 'outlined'"
    label
    data-testid="inspiration-status-chip"
    :data-status="status"
  >
    <v-icon
      start
      :icon="icon"
    />
    {{ $t(`personal.inspirations.status.${status}`) }}
  </v-chip>
</template>

<script setup lang="ts">
import { mdiCheckCircle, mdiLightbulbOnOutline, mdiPencilOutline } from "@mdi/js";
import type { InspirationStatus } from "~/lib/api/types/personal";

const props = withDefaults(defineProps<{ status: InspirationStatus; size?: string; active?: boolean }>(), {
  size: "small",
  active: true,
});

const color = computed(() => ({ INSPIRATION: "info", DRAFT: "warning", VALIDATED: "success" })[props.status]);
const icon = computed(
  () => ({ INSPIRATION: mdiLightbulbOnOutline, DRAFT: mdiPencilOutline, VALIDATED: mdiCheckCircle })[props.status],
);
</script>
