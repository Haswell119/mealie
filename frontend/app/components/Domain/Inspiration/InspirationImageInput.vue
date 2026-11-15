<template>
  <span>
    <v-btn
      variant="tonal"
      size="small"
      :loading="loading"
      :prepend-icon="$globals.icons.upload"
      @click="input?.click()"
    >
      <slot>{{ $t('personal.inspirations.image.choose') }}</slot>
    </v-btn>
    <input
      ref="input"
      type="file"
      class="d-none"
      :accept="accept"
      data-testid="inspiration-image-input"
      @change="onChange"
    >
  </span>
</template>

<script setup lang="ts">
import { alert } from "~/composables/use-toast";

/** Picks one image that the server accepts: JPEG, PNG or WebP, 10 MB at most. */
defineProps<{ loading?: boolean }>();
const emit = defineEmits<{ (e: "select", file: File): void }>();

const allowedTypes = ["image/jpeg", "image/png", "image/webp"];
const accept = allowedTypes.join(",");
const maxBytes = 10 * 1024 * 1024;

const i18n = useI18n();
const input = ref<HTMLInputElement | null>(null);

function onChange() {
  const file = input.value?.files?.[0];
  if (input.value) {
    // Lets the user pick the same file again.
    input.value.value = "";
  }
  if (!file) {
    return;
  }
  if (!allowedTypes.includes(file.type)) {
    alert.error(i18n.t("personal.inspirations.image.wrong-type"));
    return;
  }
  if (file.size > maxBytes) {
    alert.error(i18n.t("personal.inspirations.image.too-large"));
    return;
  }
  emit("select", file);
}
</script>
