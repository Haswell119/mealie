<template>
  <v-container class="narrow-container">
    <BaseDialog
      v-model="createDialog"
      :title="$t('personal.inspirations.new')"
      :icon="personalIcons.inspirations"
      max-width="700"
      width="100%"
      :loading="creating"
      can-submit
      :submit-disabled="!createValid"
      disable-submit-on-enter
      keep-open
      @submit="create"
    >
      <v-card-text data-testid="inspiration-create-form">
        <InspirationFields
          v-model="createForm"
          v-model:valid="createValid"
          autofocus
        />
        <div
          v-if="createForm.kind === 'PHOTO'"
          class="d-flex align-center flex-wrap ga-2 mt-3"
        >
          <InspirationImageInput @select="createImage = $event">
            {{ $t('personal.inspirations.image.add') }}
          </InspirationImageInput>
          <v-chip
            v-if="createImage"
            size="small"
            closable
            class="inspiration-file-chip"
            @click:close="createImage = null"
          >
            <span class="text-truncate">{{ createImage.name }}</span>
          </v-chip>
          <span
            v-else
            class="text-caption text-medium-emphasis"
          >{{ $t('personal.inspirations.image.help') }}</span>
        </div>
      </v-card-text>
    </BaseDialog>

    <InspirationDetailDialog
      v-model="detailDialog"
      :inspiration-id="detailId"
      @changed="refresh"
      @image-changed="bumpImage"
    />

    <BasePageTitle divider>
      <template #header>
        <v-icon
          size="80"
          color="primary"
          :icon="personalIcons.inspirations"
        />
      </template>
      <template #title>
        {{ $t('personal.inspirations.title') }}
      </template>
      {{ $t('personal.inspirations.subtitle') }}
      <template #content>
        <InspirationWorkflow class="mx-auto mt-3 justify-center" />
      </template>
    </BasePageTitle>

    <div class="d-flex justify-end mb-4">
      <BaseButton
        create
        data-testid="inspiration-create"
        @click="openCreate"
      />
    </div>

    <v-chip-group
      v-model="statusFilter"
      mandatory
      column
      selected-class="text-primary"
      class="mb-2"
      data-testid="inspiration-status-filter"
    >
      <v-chip
        v-for="item in statusFilters"
        :key="item.value"
        :value="item.value"
        filter
        variant="outlined"
        :data-testid="`inspiration-filter-${item.value}`"
      >
        {{ item.title }} ({{ item.count }})
      </v-chip>
    </v-chip-group>
    <v-text-field
      v-model="search"
      :label="$t('personal.inspirations.search')"
      :prepend-inner-icon="$globals.icons.search"
      density="compact"
      clearable
      hide-details
      class="mb-4"
      data-testid="inspiration-search"
    />

    <v-alert
      v-if="loaded && !inspirations.length"
      type="info"
      variant="tonal"
      data-testid="inspiration-empty"
    >
      {{ $t('personal.inspirations.empty') }}
    </v-alert>
    <v-alert
      v-else-if="loaded && !visible.length"
      type="info"
      variant="tonal"
    >
      {{ $t('personal.inspirations.empty-filtered') }}
    </v-alert>

    <InspirationCard
      v-for="inspiration in visible"
      :key="inspiration.id"
      :inspiration="inspiration"
      :image-version="imageVersions[inspiration.id] ?? 0"
      @open="openDetail(inspiration.id)"
    />
  </v-container>
</template>

<script setup lang="ts">
import InspirationCard from "~/components/Domain/Inspiration/InspirationCard.vue";
import InspirationDetailDialog from "~/components/Domain/Inspiration/InspirationDetailDialog.vue";
import InspirationFields from "~/components/Domain/Inspiration/InspirationFields.vue";
import InspirationImageInput from "~/components/Domain/Inspiration/InspirationImageInput.vue";
import InspirationWorkflow from "~/components/Domain/Inspiration/InspirationWorkflow.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { alert } from "~/composables/use-toast";
import type { InspirationKind, InspirationOut, InspirationStatus } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();

useSeoMeta({ title: i18n.t("personal.inspirations.title") });

interface InspirationForm {
  title: string;
  kind: InspirationKind;
  url: string;
  text: string;
  tags: string[];
}
type StatusFilter = "ALL" | InspirationStatus;

const inspirations = ref<InspirationOut[]>([]);
const loaded = ref(false);
/** Grows each time an inspiration gets a new image, so that its card fetches the image again. */
const imageVersions = ref<Record<string, number>>({});

const statusFilter = ref<StatusFilter>("ALL");
const search = ref<string | null>("");

const createDialog = ref(false);
const creating = ref(false);
const createValid = ref(false);
const createImage = ref<File | null>(null);

function emptyForm(): InspirationForm {
  return { title: "", kind: "NOTE", url: "", text: "", tags: [] };
}
const createForm = ref<InspirationForm>(emptyForm());

const detailDialog = ref(false);
const detailId = ref<string | null>(null);

const statusFilters = computed(() =>
  (["ALL", "INSPIRATION", "DRAFT", "VALIDATED"] as StatusFilter[]).map(value => ({
    value,
    title: i18n.t(`personal.inspirations.filter.${value}`),
    count: value === "ALL" ? inspirations.value.length : inspirations.value.filter(item => item.status === value).length,
  })),
);

const visible = computed(() => {
  const term = (search.value ?? "").trim().toLocaleLowerCase();
  return inspirations.value.filter(
    item =>
      (statusFilter.value === "ALL" || item.status === statusFilter.value)
      && (!term || item.title.toLocaleLowerCase().includes(term)),
  );
});

async function refresh() {
  const { data } = await api.inspirations.getAll(1, -1, { orderBy: "created_at", orderDirection: "desc" });
  inspirations.value = data?.items ?? [];
  loaded.value = true;
}

function bumpImage(id: string) {
  imageVersions.value = { ...imageVersions.value, [id]: (imageVersions.value[id] ?? 0) + 1 };
}

function openCreate() {
  createForm.value = emptyForm();
  createImage.value = null;
  createDialog.value = true;
}

async function create() {
  if (creating.value || !createValid.value) {
    return;
  }
  creating.value = true;
  try {
    const { data } = await api.inspirations.createOne({
      title: createForm.value.title.trim(),
      kind: createForm.value.kind,
      url: createForm.value.url.trim() || null,
      text: createForm.value.text.trim() || null,
      tags: createForm.value.tags.map(tag => tag.trim()).filter(Boolean),
    });
    if (!data) {
      return;
    }
    if (createImage.value && createForm.value.kind === "PHOTO") {
      // The inspiration exists even when its image is refused: the user adds the image again from the card.
      await api.inspirations.setImage(data.id, createImage.value);
    }
    alert.success(i18n.t("personal.common.saved"));
    createDialog.value = false;
    await refresh();
  }
  finally {
    creating.value = false;
  }
}

function openDetail(id: string) {
  detailId.value = id;
  detailDialog.value = true;
}

onMounted(async () => {
  await refresh();
  // The assistant links here with `?open=<id>` once a draft is accepted.
  const open = route.query.open;
  if (typeof open === "string" && open) {
    openDetail(open);
  }
});
</script>

<style scoped>
.inspiration-file-chip {
  max-width: 220px;
}
</style>
