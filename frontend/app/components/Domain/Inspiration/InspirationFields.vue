<template>
  <div>
    <v-text-field
      v-model="form.title"
      :label="$t('personal.inspirations.field.title')"
      :autofocus="autofocus"
      maxlength="200"
      data-testid="inspiration-title"
    />
    <v-select
      v-model="form.kind"
      :items="kindItems"
      :label="$t('personal.inspirations.field.kind')"
      data-testid="inspiration-kind"
    >
      <template #selection="{ item }">
        <InspirationKindIcon
          :kind="item.value"
          size="small"
          class="mr-2"
        />
        {{ item.title }}
      </template>
      <template #item="{ props: itemProps, item }">
        <v-list-item
          v-bind="itemProps"
          :data-testid="`inspiration-kind-${item.value}`"
        >
          <template #prepend>
            <InspirationKindIcon :kind="item.value" />
          </template>
        </v-list-item>
      </template>
    </v-select>
    <v-text-field
      v-if="showUrl"
      v-model="form.url"
      :label="$t('personal.inspirations.field.url')"
      :error-messages="urlValid ? [] : [$t('personal.inspirations.field.url-invalid')]"
      placeholder="https://"
      type="url"
      inputmode="url"
      autocapitalize="off"
      data-testid="inspiration-url"
    />
    <v-textarea
      v-model="form.text"
      :label="$t('personal.inspirations.field.text')"
      rows="3"
      auto-grow
      data-testid="inspiration-text"
    />
    <v-combobox
      v-model="form.tags"
      :label="$t('personal.inspirations.field.tags')"
      :hint="$t('personal.inspirations.field.tags-hint')"
      persistent-hint
      multiple
      chips
      closable-chips
      data-testid="inspiration-tags"
    />
  </div>
</template>

<script setup lang="ts">
import InspirationKindIcon from "~/components/Domain/Inspiration/InspirationKindIcon.vue";
import type { InspirationKind } from "~/lib/api/types/personal";

/** The fields that every inspiration has, in the dialog that creates one and in the one that edits one. */
interface InspirationForm {
  title: string;
  kind: InspirationKind;
  url: string;
  text: string;
  tags: string[];
}

defineProps<{ autofocus?: boolean }>();
const form = defineModel<InspirationForm>({ required: true });
/** True when the form can be sent: it has a title, and its link, if any, starts with http:// or https://. */
const valid = defineModel<boolean>("valid", { default: false });

const i18n = useI18n();

const kinds: InspirationKind[] = ["LINK", "PHOTO", "NOTE", "VIDEO", "IDEA"];
const kindItems = computed(() => kinds.map(value => ({ value, title: i18n.t(`personal.inspirations.kind.${value}`) })));

// A link belongs to the kinds LINK and VIDEO. A link that another kind already has stays visible, so that nothing is hidden.
const showUrl = computed(() => form.value.kind === "LINK" || form.value.kind === "VIDEO" || !!form.value.url);
const urlValid = computed(() => !form.value.url.trim() || /^https?:\/\/\S+$/i.test(form.value.url.trim()));

watchEffect(() => {
  valid.value = !!form.value.title.trim() && urlValid.value;
});
</script>
