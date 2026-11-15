<template>
  <v-img
    v-if="src"
    :src="src"
    :alt="alt"
    data-testid="inspiration-image"
  />
  <div
    v-else
    class="d-flex align-center justify-center inspiration-image__placeholder"
  >
    <v-progress-circular
      v-if="loading"
      indeterminate
      size="20"
      width="2"
    />
    <v-icon
      v-else
      class="text-medium-emphasis"
      :icon="$globals.icons.fileImage"
    />
  </div>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";

/**
 * The image of an inspiration.
 *
 * The route of the image needs the session of the user, so the image is fetched as a blob and shown
 * through an object URL. The URL is released when the image changes and when the component goes away.
 */
const props = withDefaults(defineProps<{ inspirationId: string; version?: string | number; alt?: string }>(), {
  version: 0,
  alt: "",
});

const api = usePersonalApi();
const src = ref<string | null>(null);
const loading = ref(false);
let request = 0;

function release() {
  if (src.value) {
    URL.revokeObjectURL(src.value);
    src.value = null;
  }
}

async function load() {
  const current = ++request;
  loading.value = true;
  const { data } = await api.inspirations.getImage(props.inspirationId);
  if (current !== request) {
    return;
  }
  release();
  src.value = data ? URL.createObjectURL(data) : null;
  loading.value = false;
}

watch(() => [props.inspirationId, props.version], load, { immediate: true });

onBeforeUnmount(() => {
  request++;
  release();
});
</script>

<style scoped>
.inspiration-image__placeholder {
  min-height: 48px;
  background: rgba(var(--v-theme-on-surface), 0.06);
}
</style>
