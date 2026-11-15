<template>
  <div>
    <BaseDialog
      v-model="dialog"
      :title="editing ? $t('personal.pantry.stock.edit') : $t('personal.pantry.stock.add')"
      :icon="personalIcons.pantry"
      max-width="600"
      width="100%"
      can-submit
      :submit-text="$t('personal.common.save')"
      :submit-icon="$globals.icons.save"
      :submit-disabled="!canSave || saving"
      disable-submit-on-enter
      keep-open
      @submit="save"
    >
      <v-card-text>
        <v-autocomplete
          v-model="form.foodId"
          :items="foods"
          item-title="name"
          item-value="id"
          :label="$t('personal.common.food')"
          :autofocus="!editing"
          data-testid="pantry-food"
        />
        <v-row density="compact">
          <v-col cols="5">
            <v-text-field
              v-model.number="form.quantity"
              type="number"
              min="0"
              step="any"
              inputmode="decimal"
              :label="$t('personal.common.quantity')"
              data-testid="pantry-quantity"
            />
          </v-col>
          <v-col cols="7">
            <v-select
              v-model="form.unitId"
              :items="units"
              item-title="name"
              item-value="id"
              :label="$t('personal.common.unit')"
              clearable
              data-testid="pantry-unit"
            />
          </v-col>
        </v-row>
        <v-switch
          v-model="form.confirmedUsable"
          color="primary"
          hide-details
          :label="$t('personal.pantry.stock.confirmed')"
          data-testid="pantry-confirmed"
        />
        <div class="text-body-small text-medium-emphasis mb-3">
          {{ $t('personal.pantry.stock.confirmed-help') }}
        </div>
        <v-text-field
          v-model="form.expiresOn"
          type="date"
          :label="$t('personal.pantry.stock.expires-on')"
          clearable
          data-testid="pantry-expires"
        />
        <v-text-field
          v-model="form.location"
          :label="$t('personal.pantry.stock.location')"
          :placeholder="$t('personal.pantry.stock.location-hint')"
          data-testid="pantry-location"
        />
        <v-textarea
          v-model="form.note"
          :label="$t('personal.pantry.stock.note')"
          rows="2"
          auto-grow
          data-testid="pantry-note"
        />
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
      <v-card-text>
        {{ $t('personal.pantry.stock.delete-confirm', { name: deleting?.food.name }) }}
      </v-card-text>
    </BaseDialog>

    <div class="text-body-medium text-medium-emphasis mb-3">
      {{ $t('personal.pantry.stock.help') }}
    </div>

    <div class="d-flex align-center flex-wrap ga-2 mb-3">
      <v-text-field
        v-model="search"
        :label="$t('personal.pantry.stock.search')"
        :prepend-inner-icon="$globals.icons.search"
        density="compact"
        hide-details
        clearable
        class="pantry-search"
        data-testid="pantry-search"
      />
      <BaseButton
        create
        data-testid="pantry-add"
        @click="openCreate"
      >
        {{ $t('personal.common.add') }}
      </BaseButton>
    </div>

    <v-alert
      v-if="loaded && !items.length"
      type="info"
      variant="tonal"
      data-testid="pantry-empty"
    >
      {{ $t('personal.pantry.stock.empty') }}
    </v-alert>
    <v-alert
      v-else-if="loaded && !visible.length"
      type="info"
      variant="tonal"
    >
      {{ $t('personal.pantry.stock.no-match') }}
    </v-alert>

    <v-card
      v-for="item in visible"
      :key="item.id"
      class="my-2"
      data-testid="pantry-item"
    >
      <v-card-text class="pa-3">
        <div class="d-flex align-start ga-1">
          <div class="flex-grow-1 pantry-text">
            <div
              class="text-title-medium font-weight-medium"
              data-testid="pantry-item-name"
            >
              {{ item.food.name }}
            </div>
            <div
              v-if="item.location || item.note"
              class="text-body-medium text-medium-emphasis"
            >
              {{ [item.location, item.note].filter(Boolean).join(' · ') }}
            </div>
          </div>
          <v-btn
            icon
            variant="text"
            size="small"
            :aria-label="$t('personal.common.edit')"
            data-testid="pantry-item-edit"
            @click="openEdit(item)"
          >
            <v-icon>{{ $globals.icons.edit }}</v-icon>
          </v-btn>
          <v-btn
            icon
            variant="text"
            size="small"
            :aria-label="$t('personal.common.delete')"
            data-testid="pantry-item-delete"
            @click="askDelete(item)"
          >
            <v-icon>{{ $globals.icons.delete }}</v-icon>
          </v-btn>
        </div>

        <div class="d-flex align-center flex-wrap ga-2 mt-2">
          <v-btn
            icon
            size="small"
            variant="tonal"
            :disabled="item.quantity <= 0"
            :aria-label="$t('personal.pantry.stock.decrease')"
            data-testid="pantry-item-minus"
            @click="adjust(item, -1)"
          >
            <v-icon :icon="mdiMinus" />
          </v-btn>
          <span
            class="text-title-large pantry-quantity"
            data-testid="pantry-item-quantity"
          >
            {{ text.quantity(item.quantity) }} {{ unitName(item) }}
          </span>
          <v-btn
            icon
            size="small"
            variant="tonal"
            :aria-label="$t('personal.pantry.stock.increase')"
            data-testid="pantry-item-plus"
            @click="adjust(item, 1)"
          >
            <v-icon :icon="mdiPlus" />
          </v-btn>
          <v-spacer />
          <v-chip
            v-if="item.expiresOn"
            size="small"
            label
            :color="expiryColor(item)"
            :variant="expiryColor(item) ? 'flat' : 'tonal'"
            data-testid="pantry-item-expiry"
            :data-expiry="expiryState(item)"
          >
            {{ expiryText(item) }}
          </v-chip>
        </div>

        <v-switch
          :model-value="item.confirmedUsable"
          color="primary"
          density="compact"
          hide-details
          :label="$t('personal.pantry.stock.confirmed')"
          data-testid="pantry-item-confirmed"
          @update:model-value="setConfirmed(item, !!$event)"
        />
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { mdiMinus, mdiPlus } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore, useUnitStore } from "~/composables/store";
import { alert } from "~/composables/use-toast";
import type { PantryItemCreate, PantryItemOut } from "~/lib/api/types/personal";

interface StockForm {
  foodId: string | null;
  quantity: number | string;
  unitId: string | null;
  confirmedUsable: boolean;
  expiresOn: string | null;
  location: string;
  note: string;
}

const SOON_DAYS = 7;

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const { store: foods } = useFoodStore();
const { store: units } = useUnitStore();

const items = ref<PantryItemOut[]>([]);
const loaded = ref(false);
const search = ref<string | null>("");

const dialog = ref(false);
const saving = ref(false);
const editing = ref<PantryItemOut | null>(null);
const deleteDialog = ref(false);
const deleting = ref<PantryItemOut | null>(null);

function emptyForm(): StockForm {
  return { foodId: null, quantity: 1, unitId: null, confirmedUsable: true, expiresOn: null, location: "", note: "" };
}
const form = ref<StockForm>(emptyForm());

const canSave = computed(
  () => !!form.value.foodId && typeof form.value.quantity === "number" && form.value.quantity >= 0,
);

function fold(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

const visible = computed(() => {
  const query = fold((search.value ?? "").trim());
  return items.value
    .filter(item => !query || fold(item.food.name).includes(query))
    .sort((a, b) => a.food.name.localeCompare(b.food.name, i18n.locale.value));
});

function unitName(item: PantryItemOut): string {
  if (!item.unit) {
    return "";
  }
  return item.unit.useAbbreviation && item.unit.abbreviation ? item.unit.abbreviation : item.unit.name;
}

function daysLeft(expiresOn: string): number {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((new Date(`${expiresOn}T00:00:00`).getTime() - today) / 86_400_000);
}

function expiryState(item: PantryItemOut): "expired" | "soon" | "ok" {
  const days = daysLeft(item.expiresOn!);
  if (days < 0) {
    return "expired";
  }
  return days <= SOON_DAYS ? "soon" : "ok";
}

function expiryColor(item: PantryItemOut): string | undefined {
  return { expired: "error", soon: "warning", ok: undefined }[expiryState(item)];
}

function expiryText(item: PantryItemOut): string {
  const date = new Intl.DateTimeFormat(i18n.locale.value, { dateStyle: "medium" }).format(
    new Date(`${item.expiresOn}T00:00:00`),
  );
  const key = { expired: "expired", soon: "expires-soon", ok: "expires" }[expiryState(item)];
  return i18n.t(`personal.pantry.stock.${key}`, { date });
}

async function refresh() {
  const { data } = await api.pantry.getAll(1, -1);
  items.value = data?.items ?? [];
  loaded.value = true;
}

function replace(updated: PantryItemOut) {
  items.value = items.value.map(item => (item.id === updated.id ? updated : item));
}

async function adjust(item: PantryItemOut, delta: number) {
  const { data } = await api.pantry.adjust(item.id, delta);
  if (data) {
    replace(data);
  }
}

async function setConfirmed(item: PantryItemOut, usable: boolean) {
  const { data } = await api.pantry.confirm(item.id, usable);
  if (data) {
    replace(data);
  }
  else {
    await refresh();
  }
}

function openCreate() {
  editing.value = null;
  form.value = emptyForm();
  dialog.value = true;
}

function openEdit(item: PantryItemOut) {
  editing.value = item;
  form.value = {
    foodId: item.foodId,
    quantity: item.quantity,
    unitId: item.unitId,
    confirmedUsable: item.confirmedUsable,
    expiresOn: item.expiresOn,
    location: item.location ?? "",
    note: item.note ?? "",
  };
  dialog.value = true;
}

async function save() {
  if (!canSave.value || !form.value.foodId) {
    return;
  }
  const payload: PantryItemCreate = {
    foodId: form.value.foodId,
    quantity: Number(form.value.quantity),
    unitId: form.value.unitId || null,
    confirmedUsable: form.value.confirmedUsable,
    expiresOn: form.value.expiresOn || null,
    location: form.value.location.trim() || null,
    note: form.value.note.trim() || null,
    productId: editing.value?.productId ?? null,
  };

  saving.value = true;
  const { data } = editing.value
    ? await api.pantry.updateOne(editing.value.id, payload)
    : await api.pantry.createOne(payload);
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    dialog.value = false;
    await refresh();
  }
}

function askDelete(item: PantryItemOut) {
  deleting.value = item;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.pantry.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await refresh();
  }
}

defineExpose({ refresh });

onMounted(refresh);
</script>

<style scoped>
.pantry-search {
  flex: 1 1 180px;
  min-width: 0;
}

.pantry-text {
  min-width: 0;
  overflow-wrap: anywhere;
}

.pantry-quantity {
  min-width: 72px;
  text-align: center;
}
</style>
