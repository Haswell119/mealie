<template>
  <div>
    <BaseDialog
      v-model="dialog"
      :title="editing ? $t('personal.pantry.packagings.edit') : $t('personal.pantry.packagings.add')"
      :icon="mdiPackageVariantClosed"
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
          data-testid="packaging-food"
        />
        <v-row density="compact">
          <v-col cols="5">
            <v-text-field
              v-model.number="form.quantity"
              type="number"
              min="0"
              step="any"
              inputmode="decimal"
              :label="$t('personal.pantry.packagings.quantity')"
              :error-messages="quantityInvalid ? [$t('personal.pantry.packagings.quantity-invalid')] : []"
              data-testid="packaging-quantity"
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
              data-testid="packaging-unit"
            />
          </v-col>
        </v-row>
        <v-text-field
          v-model="form.label"
          :label="$t('personal.pantry.packagings.label')"
          :placeholder="$t('personal.pantry.packagings.label-hint')"
          data-testid="packaging-label"
        />
        <v-select
          v-model="form.store"
          :items="storeItems"
          :label="$t('personal.pantry.packagings.store')"
          data-testid="packaging-store"
        />
        <v-switch
          v-model="form.isDefault"
          color="primary"
          hide-details
          :label="$t('personal.pantry.packagings.default')"
          data-testid="packaging-default"
        />
        <div class="text-body-small text-medium-emphasis mb-0">
          {{ $t('personal.pantry.packagings.default-help') }}
        </div>
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
        {{ $t('personal.pantry.packagings.delete-confirm', { name: deleting?.food.name }) }}
      </v-card-text>
    </BaseDialog>

    <div class="text-body-medium text-medium-emphasis mb-3">
      {{ $t('personal.pantry.packagings.help') }}
    </div>

    <div class="d-flex justify-end mb-3">
      <BaseButton
        create
        data-testid="packaging-add"
        @click="openCreate"
      >
        {{ $t('personal.common.add') }}
      </BaseButton>
    </div>

    <v-alert
      v-if="loaded && !items.length"
      type="info"
      variant="tonal"
      data-testid="packaging-empty"
    >
      {{ $t('personal.pantry.packagings.empty') }}
    </v-alert>

    <v-card
      v-for="item in sorted"
      :key="item.id"
      class="my-2"
      data-testid="packaging-item"
    >
      <v-card-text class="pa-3 d-flex align-start ga-1">
        <div class="flex-grow-1 packaging-text">
          <div class="d-flex align-center flex-wrap ga-2">
            <span
              class="text-title-medium font-weight-medium"
              data-testid="packaging-item-name"
            >{{ item.food.name }}</span>
            <v-chip
              v-if="item.isDefault"
              size="small"
              color="primary"
              variant="tonal"
              label
              data-testid="packaging-item-default"
            >
              {{ $t('personal.pantry.packagings.default') }}
            </v-chip>
            <v-chip
              v-if="item.store"
              size="small"
              variant="outlined"
              label
            >
              {{ storeName(item.store) }}
            </v-chip>
          </div>
          <div
            class="text-body-large"
            data-testid="packaging-item-quantity"
          >
            {{ text.quantity(item.quantity) }} {{ unitName(item) }}
          </div>
          <div
            v-if="item.label"
            class="text-body-medium text-medium-emphasis"
          >
            {{ item.label }}
          </div>
        </div>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.edit')"
          data-testid="packaging-item-edit"
          @click="openEdit(item)"
        >
          <v-icon>{{ $globals.icons.edit }}</v-icon>
        </v-btn>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.delete')"
          data-testid="packaging-item-delete"
          @click="askDelete(item)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { mdiPackageVariantClosed } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore, useUnitStore } from "~/composables/store";
import { alert } from "~/composables/use-toast";
import type { FoodPackagingCreate, FoodPackagingOut, RetailStore } from "~/lib/api/types/personal";

interface PackagingForm {
  foodId: string | null;
  quantity: number | string;
  unitId: string | null;
  label: string;
  store: string;
  isDefault: boolean;
}

const NO_STORE = "";
const stores: RetailStore[] = ["coop", "migros", "aldi", "lidl"];

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const { store: foods } = useFoodStore();
const { store: units } = useUnitStore();

const items = ref<FoodPackagingOut[]>([]);
const loaded = ref(false);

const dialog = ref(false);
const saving = ref(false);
const editing = ref<FoodPackagingOut | null>(null);
const deleteDialog = ref(false);
const deleting = ref<FoodPackagingOut | null>(null);

function emptyForm(): PackagingForm {
  return { foodId: null, quantity: "", unitId: null, label: "", store: NO_STORE, isDefault: true };
}
const form = ref<PackagingForm>(emptyForm());

const quantityValid = computed(() => typeof form.value.quantity === "number" && form.value.quantity > 0);
const quantityInvalid = computed(() => form.value.quantity !== "" && !quantityValid.value);
const canSave = computed(() => !!form.value.foodId && quantityValid.value);

const storeItems = computed(() => [
  { value: NO_STORE, title: i18n.t("personal.pantry.packagings.no-store") },
  ...stores.map(value => ({ value: value as string, title: i18n.t(`personal.pantry.stores.${value}`) })),
]);

const sorted = computed(() =>
  [...items.value].sort(
    (a, b) => a.food.name.localeCompare(b.food.name, i18n.locale.value) || Number(b.isDefault) - Number(a.isDefault),
  ),
);

function storeName(store: string): string {
  return (stores as string[]).includes(store) ? i18n.t(`personal.pantry.stores.${store}`) : store;
}

function unitName(item: FoodPackagingOut): string {
  if (!item.unit) {
    return "";
  }
  return item.unit.useAbbreviation && item.unit.abbreviation ? item.unit.abbreviation : item.unit.name;
}

async function refresh() {
  const { data } = await api.packagings.getAll(1, -1);
  items.value = data?.items ?? [];
  loaded.value = true;
}

function openCreate() {
  editing.value = null;
  form.value = emptyForm();
  dialog.value = true;
}

function openEdit(item: FoodPackagingOut) {
  editing.value = item;
  form.value = {
    foodId: item.foodId,
    quantity: item.quantity,
    unitId: item.unitId,
    label: item.label ?? "",
    store: item.store ?? NO_STORE,
    isDefault: item.isDefault,
  };
  dialog.value = true;
}

async function save() {
  if (!canSave.value || !form.value.foodId) {
    return;
  }
  const payload: FoodPackagingCreate = {
    foodId: form.value.foodId,
    quantity: Number(form.value.quantity),
    unitId: form.value.unitId || null,
    label: form.value.label.trim() || null,
    store: form.value.store || null,
    isDefault: form.value.isDefault,
    productId: editing.value?.productId ?? null,
  };

  saving.value = true;
  const { data } = editing.value
    ? await api.packagings.updateOne(editing.value.id, payload)
    : await api.packagings.createOne(payload);
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.common.saved"));
    dialog.value = false;
    await refresh();
  }
}

function askDelete(item: FoodPackagingOut) {
  deleting.value = item;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.packagings.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await refresh();
  }
}

defineExpose({ refresh });

onMounted(refresh);
</script>

<style scoped>
.packaging-text {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
