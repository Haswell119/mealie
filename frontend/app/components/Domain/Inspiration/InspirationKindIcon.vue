<template>
  <v-icon
    :icon="icon"
    :size="size"
    :aria-label="$t(`personal.inspirations.kind.${kind}`)"
  />
</template>

<script setup lang="ts">
import { mdiImageOutline, mdiLightbulbOutline, mdiLinkVariant, mdiNoteTextOutline, mdiVideoOutline } from "@mdi/js";
import type { InspirationKind } from "~/lib/api/types/personal";

const props = withDefaults(defineProps<{ kind: InspirationKind; size?: string | number }>(), { size: "default" });

const icons: Record<InspirationKind, string> = {
  LINK: mdiLinkVariant,
  PHOTO: mdiImageOutline,
  NOTE: mdiNoteTextOutline,
  VIDEO: mdiVideoOutline,
  IDEA: mdiLightbulbOutline,
};

const icon = computed(() => icons[props.kind] ?? mdiLightbulbOutline);
</script>
