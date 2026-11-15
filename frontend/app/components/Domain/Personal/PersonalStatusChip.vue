<template>
  <v-chip
    :color="color"
    :size="size"
    variant="flat"
    label
    data-testid="personal-status-chip"
  >
    <v-icon
      start
      :icon="icon"
    />
    {{ $t(`personal.enums.status.${status}`) }}
  </v-chip>
</template>

<script setup lang="ts">
import { mdiAlertCircle, mdiCheckCircle, mdiCloseCircle } from "@mdi/js";
import type { VerificationStatus } from "~/lib/api/types/personal";

const props = withDefaults(defineProps<{ status: VerificationStatus; size?: string }>(), { size: "small" });

const color = computed(() => ({ VERIFIED: "success", UNVERIFIED: "warning", INCOMPATIBLE: "error" })[props.status]);
const icon = computed(
  () => ({ VERIFIED: mdiCheckCircle, UNVERIFIED: mdiAlertCircle, INCOMPATIBLE: mdiCloseCircle })[props.status],
);
</script>
