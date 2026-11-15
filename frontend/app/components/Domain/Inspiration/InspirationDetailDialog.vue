<template>
  <div>
    <BaseDialog
      v-model="dialog"
      :title="current?.title ?? $t('personal.common.loading')"
      :icon="personalIcons.inspirations"
      max-width="760"
      width="100%"
      :loading="!!busy"
      :can-submit="editable"
      :submit-text="$t('personal.common.save')"
      :submit-icon="$globals.icons.save"
      :submit-disabled="!formValid"
      :cancel-text="$t('personal.common.close')"
      disable-submit-on-enter
      keep-open
      @submit="save"
    >
      <v-card-text
        v-if="current"
        data-testid="inspiration-detail"
        :data-status="current.status"
      >
        <InspirationWorkflow
          :current="current.status"
          class="mb-4"
        />

        <!-- A validated inspiration is a recipe: nothing can change here any more. -->
        <template v-if="!editable">
          <v-alert
            type="success"
            variant="tonal"
            class="mb-4"
            data-testid="inspiration-validated"
          >
            <div class="mb-2">
              {{ $t('personal.inspirations.validated.text') }}
            </div>
            <v-btn
              v-if="recipeLink"
              :to="recipeLink"
              color="success"
              variant="flat"
              :prepend-icon="$globals.icons.primary"
              data-testid="inspiration-recipe-link"
            >
              {{ $t('personal.inspirations.validated.open-recipe') }}
            </v-btn>
            <span v-else>{{ $t('personal.inspirations.validated.recipe-missing') }}</span>
          </v-alert>

          <div class="d-flex align-center ga-2 mb-2">
            <InspirationKindIcon :kind="current.kind" />
            <span>{{ $t(`personal.inspirations.kind.${current.kind}`) }}</span>
          </div>
          <a
            v-if="link"
            :href="link"
            target="_blank"
            rel="noopener noreferrer"
            class="d-block mb-2 inspiration-detail__wrap"
          >{{ link }}</a>
          <div
            v-if="current.text"
            class="inspiration-detail__text mb-2"
          >
            {{ current.text }}
          </div>
          <div
            v-if="current.tags.length"
            class="d-flex flex-wrap ga-1 mb-2"
          >
            <v-chip
              v-for="tag in current.tags"
              :key="tag"
              size="small"
              variant="tonal"
            >
              {{ tag }}
            </v-chip>
          </div>
          <InspirationImage
            v-if="current.image"
            class="rounded mt-2"
            :inspiration-id="current.id"
            :version="imageVersion"
            :alt="current.title"
            max-height="320"
          />
        </template>

        <template v-else>
          <InspirationFields
            v-model="form"
            v-model:valid="formValid"
          />
          <a
            v-if="link"
            :href="link"
            target="_blank"
            rel="noopener noreferrer"
            class="d-inline-flex align-center text-body-2 mb-2 inspiration-detail__wrap"
          >
            <v-icon
              size="small"
              class="mr-1"
              :icon="$globals.icons.externalLink"
            />
            {{ $t('personal.inspirations.open-link') }}
          </a>

          <!-- Image -->
          <h3 class="text-subtitle-1 mt-4 mb-2">
            {{ $t('personal.inspirations.image.title') }}
          </h3>
          <InspirationImage
            v-if="current.image"
            class="rounded mb-2"
            :inspiration-id="current.id"
            :version="imageVersion"
            :alt="current.title"
            max-height="320"
          />
          <div class="d-flex align-center flex-wrap ga-2">
            <InspirationImageInput
              :loading="busy === 'image'"
              @select="uploadImage"
            >
              {{ current.image ? $t('personal.inspirations.image.replace') : $t('personal.inspirations.image.add') }}
            </InspirationImageInput>
            <span class="text-caption text-medium-emphasis">{{ $t('personal.inspirations.image.help') }}</span>
          </div>

          <v-divider class="my-4" />

          <!-- Draft -->
          <h3 class="text-subtitle-1 mb-1">
            {{ $t('personal.inspirations.draft.title') }}
          </h3>
          <template v-if="!draft">
            <div class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('personal.inspirations.draft.start-help') }}
            </div>
            <v-btn
              color="primary"
              :disabled="!formValid || !!busy"
              :loading="busy === 'draft'"
              :prepend-icon="$globals.icons.edit"
              data-testid="inspiration-start-draft"
              @click="startDraft"
            >
              {{ $t('personal.inspirations.draft.start') }}
            </v-btn>
          </template>
          <template v-else>
            <div class="text-body-2 text-medium-emphasis mb-3">
              {{ $t('personal.inspirations.draft.help') }}
            </div>
            <v-text-field
              v-model="draft.name"
              :label="$t('personal.inspirations.draft.name')"
              data-testid="inspiration-draft-name"
            />
            <v-textarea
              v-model="draft.description"
              :label="$t('personal.inspirations.draft.description')"
              rows="2"
              auto-grow
              data-testid="inspiration-draft-description"
            />
            <v-text-field
              v-model.number="draft.servings"
              :label="$t('personal.inspirations.draft.servings')"
              :hint="$t('personal.inspirations.draft.servings-hint')"
              persistent-hint
              type="number"
              inputmode="decimal"
              min="0"
              step="1"
              class="mb-2"
              data-testid="inspiration-draft-servings"
            />
            <v-textarea
              v-model="draft.ingredients"
              :label="$t('personal.inspirations.draft.ingredients')"
              :hint="$t('personal.inspirations.draft.ingredients-hint')"
              persistent-hint
              rows="5"
              auto-grow
              class="mb-2"
              data-testid="inspiration-draft-ingredients"
            />
            <v-textarea
              v-model="draft.instructions"
              :label="$t('personal.inspirations.draft.instructions')"
              :hint="$t('personal.inspirations.draft.instructions-hint')"
              persistent-hint
              rows="5"
              auto-grow
              class="mb-2"
              data-testid="inspiration-draft-instructions"
            />
            <v-textarea
              v-model="draft.notes"
              :label="$t('personal.inspirations.draft.notes')"
              rows="2"
              auto-grow
              data-testid="inspiration-draft-notes"
            />

            <v-alert
              type="warning"
              variant="tonal"
              class="mb-3"
              data-testid="inspiration-check-quantities"
            >
              {{ $t('personal.inspirations.draft.check-quantities') }}
            </v-alert>
            <div
              v-if="missing.length"
              class="text-body-2 text-medium-emphasis mb-2"
              data-testid="inspiration-draft-missing"
            >
              {{ $t('personal.inspirations.draft.missing') }} {{ missing.join(', ') }}.
            </div>
            <v-btn
              color="success"
              :disabled="!formValid || !!missing.length || !!busy"
              :loading="busy === 'validate'"
              :prepend-icon="$globals.icons.check"
              data-testid="inspiration-validate"
              @click="validate"
            >
              {{ $t('personal.inspirations.draft.validate') }}
            </v-btn>
          </template>

          <v-divider class="my-4" />

          <!-- Assistant -->
          <h3 class="text-subtitle-1 mb-1">
            {{ $t('personal.inspirations.structure.title') }}
          </h3>
          <div class="text-body-2 text-medium-emphasis mb-3">
            {{ $t('personal.inspirations.structure.help') }}
          </div>
          <v-btn
            variant="tonal"
            :disabled="!formValid || !!busy"
            :loading="busy === 'structure'"
            :prepend-icon="personalIcons.assistant"
            data-testid="inspiration-structure"
            @click="structure"
          >
            {{ $t('personal.inspirations.structure.action') }}
          </v-btn>
          <v-alert
            v-if="structured"
            type="info"
            variant="tonal"
            class="mt-3"
            data-testid="inspiration-structured"
          >
            <div class="mb-2">
              {{ $t('personal.inspirations.structure.done') }}
            </div>
            <v-btn
              to="/assistant"
              color="info"
              variant="flat"
              :prepend-icon="personalIcons.assistant"
              data-testid="inspiration-assistant-link"
            >
              {{ $t('personal.inspirations.structure.open-assistant') }}
            </v-btn>
          </v-alert>
        </template>

        <v-divider class="my-4" />
        <v-btn
          color="error"
          variant="text"
          :disabled="!!busy"
          :prepend-icon="$globals.icons.delete"
          data-testid="inspiration-delete"
          @click="deleteDialog = true"
        >
          {{ $t('personal.inspirations.delete') }}
        </v-btn>
      </v-card-text>
      <v-card-text
        v-else
        class="text-medium-emphasis"
      >
        {{ $t('personal.common.loading') }}
      </v-card-text>
    </BaseDialog>

    <BaseDialog
      v-model="deleteDialog"
      :title="$t('general.confirm')"
      :icon="$globals.icons.alertCircle"
      color="error"
      can-confirm
      @confirm="remove"
    >
      <v-card-text data-testid="inspiration-delete-confirm">
        {{ $t('personal.inspirations.delete-confirm', { title: current?.title }) }}
        <span v-if="current?.status === 'VALIDATED'">{{ $t('personal.inspirations.delete-keeps-recipe') }}</span>
      </v-card-text>
    </BaseDialog>
  </div>
</template>

<script setup lang="ts">
import InspirationFields from "~/components/Domain/Inspiration/InspirationFields.vue";
import InspirationImage from "~/components/Domain/Inspiration/InspirationImage.vue";
import InspirationImageInput from "~/components/Domain/Inspiration/InspirationImageInput.vue";
import InspirationKindIcon from "~/components/Domain/Inspiration/InspirationKindIcon.vue";
import InspirationWorkflow from "~/components/Domain/Inspiration/InspirationWorkflow.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type { InspirationDraft, InspirationKind, InspirationOut, InspirationUpdate } from "~/lib/api/types/personal";

/**
 * One inspiration, from the idea to the validated recipe.
 *
 * The dialog loads the inspiration itself: only a single inspiration carries the slug of its recipe.
 */
const props = defineProps<{ inspirationId: string | null }>();
const dialog = defineModel<boolean>({ required: true });
const emit = defineEmits<{
  /** The inspiration changed or went away: the list is out of date. */
  (e: "changed"): void;
  (e: "image-changed", id: string): void;
}>();

interface InspirationForm {
  title: string;
  kind: InspirationKind;
  url: string;
  text: string;
  tags: string[];
}
/** The draft as the user types it: one ingredient and one step per line. */
interface DraftForm {
  name: string;
  description: string;
  servings: number | string;
  ingredients: string;
  instructions: string;
  notes: string;
}
type Busy = "" | "load" | "save" | "draft" | "validate" | "structure" | "image" | "delete";

const i18n = useI18n();
const api = usePersonalApi();
const auth = useMealieAuth();

const current = ref<InspirationOut | null>(null);
const form = ref<InspirationForm>({ title: "", kind: "NOTE", url: "", text: "", tags: [] });
const formValid = ref(false);
const draft = ref<DraftForm | null>(null);
const busy = ref<Busy>("");
const structured = ref(false);
const imageVersion = ref(0);
const deleteDialog = ref(false);

const editable = computed(() => !!current.value && current.value.status !== "VALIDATED");

const link = computed(() => {
  const url = (editable.value ? form.value.url : current.value?.url)?.trim() ?? "";
  return /^https?:\/\/\S+$/i.test(url) ? url : null;
});

const recipeLink = computed(() => {
  const groupSlug = auth.user.value?.groupSlug;
  const recipeSlug = current.value?.recipeSlug;
  return groupSlug && recipeSlug ? `/g/${groupSlug}/r/${recipeSlug}` : null;
});

function lines(text: string): string[] {
  return text.split("\n").map(line => line.trim()).filter(Boolean);
}

function servings(value: number | string): number {
  const number = typeof value === "number" ? value : Number.parseFloat(value);
  return Number.isFinite(number) ? number : 0;
}

/** What the server asks for before it turns the draft into a recipe. */
const missing = computed(() => {
  if (!draft.value) {
    return [];
  }
  const names: string[] = [];
  if (!draft.value.name.trim()) {
    names.push(i18n.t("personal.inspirations.draft.missing-name"));
  }
  if (servings(draft.value.servings) <= 0) {
    names.push(i18n.t("personal.inspirations.draft.missing-servings"));
  }
  if (!lines(draft.value.ingredients).length) {
    names.push(i18n.t("personal.inspirations.draft.missing-ingredients"));
  }
  return names;
});

function toDraftForm(value: InspirationDraft): DraftForm {
  return {
    name: value.name ?? "",
    description: value.description ?? "",
    servings: value.recipeServings || "",
    ingredients: (value.ingredients ?? []).join("\n"),
    instructions: (value.instructions ?? []).join("\n"),
    notes: value.notes ?? "",
  };
}

function fromDraftForm(value: DraftForm): InspirationDraft {
  return {
    name: value.name.trim(),
    description: value.description.trim() || null,
    recipeServings: servings(value.servings),
    ingredients: lines(value.ingredients),
    instructions: lines(value.instructions),
    notes: value.notes.trim() || null,
  };
}

function show(inspiration: InspirationOut) {
  current.value = inspiration;
  form.value = {
    title: inspiration.title,
    kind: inspiration.kind,
    url: inspiration.url ?? "",
    text: inspiration.text ?? "",
    tags: [...inspiration.tags],
  };
  draft.value = inspiration.draft ? toDraftForm(inspiration.draft) : null;
}

async function load(id: string) {
  current.value = null;
  draft.value = null;
  structured.value = false;
  busy.value = "load";
  const { data } = await api.inspirations.getOne(id);
  busy.value = "";
  if (data && props.inspirationId === id) {
    show(data);
  }
  else if (!data) {
    dialog.value = false;
    emit("changed");
  }
}

watch(
  () => [dialog.value, props.inspirationId] as const,
  ([open, id]) => {
    if (open && id) {
      load(id);
    }
  },
  { immediate: true },
);

/** Send the fields and the draft to the server. The answer replaces what the dialog shows. */
async function persist(): Promise<boolean> {
  if (!current.value || !formValid.value) {
    return false;
  }
  const payload: InspirationUpdate = {
    title: form.value.title.trim(),
    kind: form.value.kind,
    url: form.value.url.trim() || null,
    text: form.value.text.trim() || null,
    tags: form.value.tags.map(tag => tag.trim()).filter(Boolean),
  };
  if (draft.value) {
    payload.draft = fromDraftForm(draft.value);
  }
  const { data } = await api.inspirations.updateOne(current.value.id, payload);
  if (!data) {
    return false;
  }
  show(data);
  emit("changed");
  return true;
}

async function run(action: Busy, work: () => Promise<void>) {
  if (busy.value) {
    return;
  }
  busy.value = action;
  try {
    await work();
  }
  finally {
    busy.value = "";
  }
}

function save() {
  return run("save", async () => {
    if (await persist()) {
      alert.success(i18n.t("personal.common.saved"));
    }
  });
}

function startDraft() {
  return run("draft", async () => {
    if (!(await persist()) || !current.value) {
      return;
    }
    const { data } = await api.inspirations.startDraft(current.value.id);
    if (data) {
      show(data);
      emit("changed");
    }
  });
}

function validate() {
  return run("validate", async () => {
    if (!(await persist()) || !current.value) {
      return;
    }
    const { data } = await api.inspirations.validate(current.value.id);
    if (data) {
      show(data);
      emit("changed");
      alert.success(i18n.t("personal.inspirations.validated.toast"));
    }
  });
}

function structure() {
  return run("structure", async () => {
    structured.value = false;
    if (!(await persist()) || !current.value) {
      return;
    }
    const { data } = await api.inspirations.structure(current.value.id);
    structured.value = !!data;
  });
}

function uploadImage(file: File) {
  return run("image", async () => {
    if (!current.value) {
      return;
    }
    const { data } = await api.inspirations.setImage(current.value.id, file);
    if (data && current.value) {
      // Only the image changes: what the user is typing stays as it is.
      current.value = { ...current.value, image: data.image };
      imageVersion.value++;
      emit("image-changed", data.id);
      emit("changed");
    }
  });
}

function remove() {
  return run("delete", async () => {
    if (!current.value) {
      return;
    }
    const { data } = await api.inspirations.deleteOne(current.value.id);
    if (data) {
      alert.success(i18n.t("personal.common.deleted"));
      dialog.value = false;
      emit("changed");
    }
  });
}
</script>

<style scoped>
.inspiration-detail__wrap {
  overflow-wrap: anywhere;
}

.inspiration-detail__text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
