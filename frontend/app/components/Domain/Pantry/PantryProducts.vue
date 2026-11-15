<template>
  <div>
    <BaseDialog
      v-model="linkDialog"
      :title="$t('personal.pantry.products.link-title')"
      :icon="mdiLinkVariant"
      max-width="600"
      width="100%"
      can-submit
      :submit-text="$t('personal.pantry.products.link')"
      :submit-icon="mdiLinkVariant"
      :submit-disabled="!linkFoodId || linking"
      :loading="linking"
      disable-submit-on-enter
      keep-open
      @submit="importProduct"
    >
      <v-card-text>
        <div
          v-if="linkProduct"
          class="text-title-medium font-weight-medium mb-3"
        >
          {{ productTitle(linkProduct) }}
        </div>
        <v-autocomplete
          v-model="linkFoodId"
          :items="foods"
          item-title="name"
          item-value="id"
          :label="$t('personal.common.food')"
          autofocus
          data-testid="product-link-food"
        />
        <v-checkbox
          v-model="createPackaging"
          :label="$t('personal.pantry.products.create-packaging')"
          density="compact"
          hide-details
          data-testid="product-link-packaging"
        />
        <div class="text-body-small text-medium-emphasis mb-3">
          {{ $t('personal.pantry.products.create-packaging-help') }}
        </div>
        <v-alert
          type="warning"
          variant="tonal"
          density="compact"
        >
          {{ $t('personal.pantry.products.hint-warning') }}
        </v-alert>
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
        {{ $t('personal.pantry.products.delete-confirm', { name: deleting?.name }) }}
      </v-card-text>
    </BaseDialog>

    <div class="text-body-medium text-medium-emphasis mb-1">
      {{ $t('personal.pantry.products.help') }}
    </div>
    <div
      class="text-body-small text-medium-emphasis"
      data-testid="product-source"
    >
      {{ $t('personal.pantry.products.source') }}
      <a
        href="https://world.openfoodfacts.org"
        target="_blank"
        rel="noopener noreferrer"
      >{{ $t('personal.pantry.products.source-link') }}</a>.
      {{ $t('personal.pantry.products.privacy') }}
    </div>

    <v-form @submit.prevent="runSearch">
      <v-row
        density="compact"
        align="start"
      >
        <v-col
          cols="12"
          sm="6"
        >
          <v-text-field
            v-model="query"
            :label="$t('personal.pantry.products.query')"
            :prepend-inner-icon="$globals.icons.search"
            :hint="$t('personal.pantry.products.min-chars')"
            density="compact"
            clearable
            data-testid="product-query"
          />
        </v-col>
        <v-col
          cols="7"
          sm="3"
        >
          <v-select
            v-model="store"
            :items="storeItems"
            :label="$t('personal.pantry.products.store')"
            density="compact"
            hide-details
            data-testid="product-store"
          />
        </v-col>
        <v-col
          cols="5"
          sm="3"
        >
          <v-btn
            type="submit"
            color="primary"
            block
            height="40"
            :disabled="!canSearch"
            :loading="searching"
            data-testid="product-search"
          >
            {{ $t('personal.pantry.products.search') }}
          </v-btn>
        </v-col>
      </v-row>
    </v-form>

    <v-progress-linear
      :active="searching"
      indeterminate
      color="primary"
      class="mb-2"
      data-testid="product-loader"
    />

    <div
      v-if="imported"
      ref="importResult"
      class="mb-3 product-import-result"
      data-testid="product-import-result"
    >
      <v-alert
        type="success"
        variant="tonal"
        density="compact"
        closable
        class="mb-2"
        @click:close="imported = null"
      >
        <div class="font-weight-medium">
          {{ $t('personal.pantry.products.linked', { product: imported.out.product.name, food: imported.foodName }) }}
        </div>
        <div
          v-if="imported.out.packaging"
          data-testid="product-import-packaging"
        >
          {{ $t('personal.pantry.products.packaging-created', { label: packagingText(imported.out.packaging) }) }}
        </div>
      </v-alert>
      <v-alert
        type="warning"
        variant="tonal"
        density="compact"
        data-testid="product-import-hints"
      >
        <template v-if="imported.out.hints.length">
          <div class="font-weight-medium">
            {{ $t('personal.pantry.products.hints-title') }}
          </div>
          <ul class="product-hints mb-2">
            <li
              v-for="hint in imported.out.hints"
              :key="hint"
              data-testid="product-import-hint"
            >
              {{ hintText(hint) }}
            </li>
          </ul>
        </template>
        <div class="font-weight-medium">
          {{ $t('personal.pantry.products.hint-warning') }}
        </div>
        <v-btn
          variant="outlined"
          size="small"
          class="mt-2"
          :to="`/dietary?food=${imported.foodId}`"
          :prepend-icon="personalIcons.dietary"
          data-testid="product-check-food"
        >
          {{ $t('personal.pantry.products.check-food') }}
        </v-btn>
      </v-alert>
    </div>

    <v-alert
      v-if="result && !result.available"
      type="info"
      variant="tonal"
      class="mb-3"
      data-testid="product-unavailable"
    >
      {{ $t('personal.pantry.products.unavailable') }}
    </v-alert>
    <template v-else-if="result">
      <div
        v-if="!result.products.length"
        class="text-body-medium text-medium-emphasis"
        data-testid="product-no-results"
      >
        {{ $t('personal.pantry.products.no-results', { query: result.query }) }}
      </div>
      <div
        v-else
        class="text-body-small text-medium-emphasis mb-1"
      >
        {{ $t('personal.pantry.products.results', { count: result.products.length }) }}
      </div>

      <v-card
        v-for="product in result.products"
        :key="product.barcode"
        class="my-2"
        data-testid="product-card"
      >
        <v-card-text class="pa-3 d-flex align-start ga-3">
          <img
            v-if="product.imageUrl"
            :src="product.imageUrl"
            :alt="product.name"
            class="product-image"
            loading="lazy"
            referrerpolicy="no-referrer"
          >
          <div class="flex-grow-1 product-text">
            <div
              class="text-title-medium font-weight-medium"
              data-testid="product-name"
            >
              {{ product.name }}
            </div>
            <div
              v-if="product.brand || product.quantityText"
              class="text-body-medium text-medium-emphasis"
            >
              {{ [product.brand, product.quantityText].filter(Boolean).join(' · ') }}
            </div>
            <div
              v-if="product.stores?.length || product.labels?.length"
              class="d-flex flex-wrap ga-1 mt-2"
            >
              <v-chip
                v-for="shop in product.stores"
                :key="`store-${shop}`"
                size="x-small"
                color="primary"
                variant="outlined"
                label
              >
                {{ storeName(shop) }}
              </v-chip>
              <v-chip
                v-for="label in shownLabels(product)"
                :key="`label-${label}`"
                size="x-small"
                variant="tonal"
                label
                data-testid="product-label"
              >
                {{ labelText(label) }}
              </v-chip>
              <v-chip
                v-if="hiddenLabels(product)"
                size="x-small"
                variant="text"
              >
                +{{ hiddenLabels(product) }}
              </v-chip>
            </div>
          </div>
        </v-card-text>
        <v-card-actions class="pt-0">
          <v-btn
            color="primary"
            variant="tonal"
            :prepend-icon="mdiLinkVariant"
            data-testid="product-link"
            @click="openLink(product)"
          >
            {{ $t('personal.pantry.products.link') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </template>

    <h3 class="text-title-large mt-6 mb-2">
      {{ $t('personal.pantry.products.imported-title') }}
    </h3>
    <div
      v-if="savedLoaded && !saved.length"
      class="text-body-medium text-medium-emphasis"
      data-testid="product-saved-empty"
    >
      {{ $t('personal.pantry.products.imported-empty') }}
    </div>
    <v-card
      v-for="product in saved"
      :key="product.id"
      class="my-2"
      data-testid="product-saved"
    >
      <v-card-text class="pa-3 d-flex align-start ga-2">
        <div class="flex-grow-1 product-text">
          <div class="text-title-medium font-weight-medium">
            {{ product.name }}
          </div>
          <div class="text-body-medium text-medium-emphasis">
            {{ [product.brand, product.quantityText, $t('personal.pantry.products.barcode', { barcode: product.barcode })]
              .filter(Boolean).join(' · ') }}
          </div>
          <div class="text-body-medium">
            <NuxtLink
              v-if="product.foodId"
              :to="`/dietary?food=${product.foodId}`"
            >
              {{ $t('personal.pantry.products.imported-food', { name: foodName(product.foodId) }) }}
            </NuxtLink>
            <span
              v-else
              class="text-medium-emphasis"
            >{{ $t('personal.pantry.products.no-food') }}</span>
          </div>
        </div>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.delete')"
          data-testid="product-saved-delete"
          @click="askDelete(product)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { mdiLinkVariant } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore } from "~/composables/store";
import { alert } from "~/composables/use-toast";
import type {
  FoodPackagingOut,
  ProductBase,
  ProductImportOut,
  ProductOut,
  ProductSearchOut,
  RetailStore,
} from "~/lib/api/types/personal";

const ALL_STORES = "";
const MAX_LABELS = 6;
const stores: RetailStore[] = ["coop", "migros", "aldi", "lidl"];

const emit = defineEmits<{ (e: "imported"): void }>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const { store: foods } = useFoodStore();

const query = ref<string | null>("");
const store = ref<string>(ALL_STORES);
const searching = ref(false);
const result = ref<ProductSearchOut | null>(null);
let searchRun = 0;

const saved = ref<ProductOut[]>([]);
const savedLoaded = ref(false);
const restrictionNames = ref<Record<string, string>>({});

const linkDialog = ref(false);
const linking = ref(false);
const linkProduct = ref<ProductBase | null>(null);
const linkFoodId = ref<string | null>(null);
const createPackaging = ref(true);
const imported = ref<{ out: ProductImportOut; foodId: string; foodName: string } | null>(null);
const importResult = ref<HTMLElement | null>(null);

const deleteDialog = ref(false);
const deleting = ref<ProductOut | null>(null);

const canSearch = computed(() => (query.value ?? "").trim().length >= 2);

const storeItems = computed(() => [
  { value: ALL_STORES, title: i18n.t("personal.pantry.stores.all") },
  ...stores.map(value => ({ value: value as string, title: i18n.t(`personal.pantry.stores.${value}`) })),
]);

function storeName(shop: string): string {
  return (stores as string[]).includes(shop) ? i18n.t(`personal.pantry.stores.${shop}`) : shop.replace(/-/g, " ");
}

function labelText(label: string): string {
  return label.replace(/-/g, " ");
}

function shownLabels(product: ProductBase): string[] {
  return (product.labels ?? []).slice(0, MAX_LABELS);
}

function hiddenLabels(product: ProductBase): number {
  return Math.max((product.labels ?? []).length - MAX_LABELS, 0);
}

function productTitle(product: ProductBase): string {
  return [product.name, product.brand, product.quantityText].filter(Boolean).join(" · ");
}

function foodName(foodId: string): string {
  return foods.value.find(food => food.id === foodId)?.name ?? "…";
}

function packagingText(packaging: FoodPackagingOut): string {
  const unit = packaging.unit?.useAbbreviation && packaging.unit.abbreviation ? packaging.unit.abbreviation : packaging.unit?.name;
  return [text.quantity(packaging.quantity), unit].filter(Boolean).join(" ");
}

/** A hint is `KIND` or `KIND:restriction key`. */
function hintText(hint: string): string {
  const [kind, restrictionKey] = hint.split(":");
  const key = `personal.pantry.products.hint.${kind}`;
  if (!i18n.te(key)) {
    return hint;
  }
  const name = restrictionKey ? (restrictionNames.value[restrictionKey] ?? restrictionKey) : "";
  return i18n.t(key, { key: name.toLocaleLowerCase(i18n.locale.value) });
}

async function runSearch() {
  if (!canSearch.value || searching.value) {
    return;
  }
  const run = ++searchRun;
  searching.value = true;
  const { data } = await api.products.search((query.value ?? "").trim(), (store.value || null) as RetailStore | null);
  if (run !== searchRun) {
    return;
  }
  searching.value = false;
  result.value = data;
}

async function loadSaved() {
  const { data } = await api.products.getAll();
  saved.value = data?.items ?? [];
  savedLoaded.value = true;
}

async function loadRestrictions() {
  const { data } = await api.dietary.getRestrictions();
  restrictionNames.value = Object.fromEntries((data ?? []).map(restriction => [restriction.key, restriction.name]));
}

function openLink(product: ProductBase) {
  linkProduct.value = product;
  linkFoodId.value = null;
  createPackaging.value = true;
  linkDialog.value = true;
}

async function importProduct() {
  if (!linkProduct.value || !linkFoodId.value || linking.value) {
    return;
  }
  const foodId = linkFoodId.value;
  linking.value = true;
  const { data } = await api.products.importProduct({
    barcode: linkProduct.value.barcode,
    foodId,
    createPackaging: createPackaging.value,
  });
  linking.value = false;
  if (!data) {
    return;
  }

  imported.value = { out: data, foodId, foodName: foodName(foodId) };
  linkDialog.value = false;
  emit("imported");
  await loadSaved();
  await nextTick();
  importResult.value?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function askDelete(product: ProductOut) {
  deleting.value = product;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.products.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await loadSaved();
  }
}

onMounted(() => {
  loadSaved();
  loadRestrictions();
});
</script>

<style scoped>
.product-image {
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  object-fit: contain;
  border-radius: 4px;
  background: #fff;
}

/* The fixed application bar must not cover the result when the page scrolls to it. */
.product-import-result {
  scroll-margin-top: 72px;
}

.product-text {
  min-width: 0;
  overflow-wrap: anywhere;
}

.product-hints {
  padding-left: 20px;
  margin: 0;
}
</style>
