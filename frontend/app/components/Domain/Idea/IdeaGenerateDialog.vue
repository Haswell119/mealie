<template>
  <BaseDialog
    v-model="open"
    :title="$t('personal.ideas.generate.title')"
    :icon="personalIcons.assistant"
    max-width="600"
    width="100%"
    can-submit
    :submit-text="$t('personal.ideas.generate.submit')"
    :submit-icon="personalIcons.assistant"
    :submit-disabled="busy"
    :loading="busy"
    disable-submit-on-enter
    keep-open
    @submit="generate"
  >
    <v-card-text data-testid="idea-generate-form">
      <div class="text-body-medium mb-2">
        {{ $t('personal.ideas.generate.help') }}
      </div>
      <v-alert
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        data-testid="idea-generate-sent"
      >
        {{ $t('personal.ideas.generate.sent') }}
      </v-alert>

      <div class="text-body-medium">
        {{ $t('personal.ideas.generate.count', { count }) }}
      </div>
      <v-slider
        v-model="count"
        :min="1"
        :max="8"
        :step="1"
        color="primary"
        hide-details
        class="mb-3"
        data-testid="idea-generate-count"
      />

      <v-text-field
        v-model="hint"
        :label="$t('personal.ideas.generate.hint')"
        :placeholder="$t('personal.ideas.generate.hint-placeholder')"
        maxlength="200"
        counter
        data-testid="idea-generate-hint"
      />

      <v-switch
        v-model="useStock"
        color="primary"
        hide-details
        :label="$t('personal.ideas.generate.use-stock')"
        data-testid="idea-generate-stock"
      />
      <div class="text-body-small text-medium-emphasis mb-2">
        {{ $t('personal.ideas.generate.use-stock-help') }}
      </div>

      <v-switch
        v-model="includeConstraints"
        color="primary"
        hide-details
        :label="$t('personal.ideas.generate.include-constraints')"
        data-testid="idea-generate-constraints"
      />
      <div class="text-body-small text-medium-emphasis">
        {{ $t('personal.ideas.generate.include-constraints-help') }}
      </div>

      <v-alert
        v-if="message"
        :type="failed ? 'warning' : 'info'"
        variant="tonal"
        density="compact"
        class="mt-4"
        data-testid="idea-generate-message"
      >
        {{ message }}
      </v-alert>
    </v-card-text>
  </BaseDialog>
</template>

<script setup lang="ts">
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";

const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ (e: "created", count: number): void }>();

const i18n = useI18n();
const api = usePersonalApi();

const count = ref(3);
const hint = ref("");
const useStock = ref(true);
/** Off each time the dialog opens: the user decides again each time what goes out. */
const includeConstraints = ref(false);
const busy = ref(false);
const failed = ref(false);
const message = ref("");

watch(open, (value) => {
  if (value) {
    includeConstraints.value = false;
    failed.value = false;
    message.value = "";
  }
});

async function generate() {
  if (busy.value) {
    return;
  }
  busy.value = true;
  failed.value = false;
  message.value = "";
  const { data } = await api.ideas.generate({
    count: count.value,
    hint: hint.value.trim() || null,
    useStock: useStock.value,
    includeConstraints: includeConstraints.value,
  });
  busy.value = false;

  if (!data || !data.available) {
    failed.value = true;
    message.value = i18n.t("personal.ideas.generate.unavailable");
    return;
  }
  if (!data.created.length) {
    message.value = i18n.t("personal.ideas.generate.none");
    return;
  }
  alert.success(i18n.t("personal.ideas.generate.done", { count: data.created.length }, data.created.length));
  emit("created", data.created.length);
  open.value = false;
}
</script>
