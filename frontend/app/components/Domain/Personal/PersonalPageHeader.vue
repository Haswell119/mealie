<template>
  <header class="pe-hero">
    <div
      v-if="icon"
      class="pe-hero__icon"
      aria-hidden="true"
    >
      <v-icon
        :icon="icon"
        size="28"
      />
    </div>
    <div class="pe-hero__text">
      <h1 class="pe-hero__title">
        {{ title }}
      </h1>
      <div
        v-if="subtitle || $slots.default"
        class="pe-hero__subtitle"
      >
        <slot>{{ subtitle }}</slot>
      </div>
    </div>
    <div
      v-if="$slots.actions"
      class="pe-hero__actions"
    >
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{ title: string; subtitle?: string; icon?: string }>();
</script>
