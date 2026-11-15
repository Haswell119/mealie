<template>
  <v-card
    class="my-2 left-border"
    data-testid="inspiration-card"
    :data-status="inspiration.status"
    @click="emit('open')"
  >
    <div class="d-flex">
      <InspirationImage
        v-if="inspiration.image"
        class="inspiration-card__thumb"
        :inspiration-id="inspiration.id"
        :version="`${inspiration.image}-${imageVersion}`"
        :alt="inspiration.title"
        cover
      />
      <div class="inspiration-card__body pa-3">
        <div class="d-flex align-start ga-2">
          <InspirationKindIcon
            :kind="inspiration.kind"
            class="mt-1 text-medium-emphasis"
          />
          <span
            class="text-subtitle-1 font-weight-medium inspiration-card__wrap"
            data-testid="inspiration-card-title"
          >{{ inspiration.title }}</span>
        </div>
        <div class="d-flex flex-wrap ga-1 mt-2">
          <InspirationStatusChip :status="inspiration.status" />
          <v-chip
            v-for="tag in inspiration.tags"
            :key="tag"
            size="small"
            variant="tonal"
          >
            {{ tag }}
          </v-chip>
        </div>
        <div
          v-if="inspiration.text"
          class="text-body-2 text-medium-emphasis mt-2 mb-0 inspiration-card__note"
        >
          {{ inspiration.text }}
        </div>
        <a
          v-if="link"
          :href="link"
          target="_blank"
          rel="noopener noreferrer"
          class="d-flex align-center text-body-2 mt-2 inspiration-card__link"
          data-testid="inspiration-card-link"
          @click.stop
        >
          <v-icon
            size="small"
            class="mr-1"
            :icon="$globals.icons.externalLink"
          />
          <span class="text-truncate">{{ linkLabel }}</span>
        </a>
      </div>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import InspirationImage from "~/components/Domain/Inspiration/InspirationImage.vue";
import InspirationKindIcon from "~/components/Domain/Inspiration/InspirationKindIcon.vue";
import InspirationStatusChip from "~/components/Domain/Inspiration/InspirationStatusChip.vue";
import type { InspirationOut } from "~/lib/api/types/personal";

const props = withDefaults(defineProps<{ inspiration: InspirationOut; imageVersion?: number }>(), { imageVersion: 0 });
const emit = defineEmits<{ (e: "open"): void }>();

// Only a web address becomes a link. Anything else stays out of `href`.
const link = computed(() => {
  const url = props.inspiration.url?.trim() ?? "";
  return /^https?:\/\//i.test(url) ? url : null;
});
const linkLabel = computed(() => (link.value ?? "").replace(/^https?:\/\/(www\.)?/i, ""));
</script>

<style scoped>
.inspiration-card__thumb {
  flex: 0 0 96px;
  width: 96px;
  min-height: 96px;
}

.inspiration-card__body {
  flex: 1 1 auto;
  min-width: 0;
}

.inspiration-card__wrap {
  overflow-wrap: anywhere;
  line-height: 1.4;
}

.inspiration-card__note {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  overflow-wrap: anywhere;
  white-space: pre-line;
}

.inspiration-card__link {
  min-width: 0;
  max-width: 100%;
}
</style>
