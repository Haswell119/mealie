<template>
  <div>
    <BaseDialog
      v-model="dialog"
      :title="dialogTitle"
      :icon="mdiCashMultiple"
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
      <v-card-text data-testid="price-form">
        <div
          v-if="keeping"
          class="text-title-medium font-weight-medium mb-3 price-text"
        >
          {{ keeping.name }}
        </div>
        <v-autocomplete
          v-model="form.foodId"
          :items="foods"
          item-title="name"
          item-value="id"
          :label="$t('personal.common.food')"
          :autofocus="!editing"
          data-testid="price-food"
        />
        <v-combobox
          v-model="form.store"
          :items="storeNames"
          :label="$t('personal.prices.store')"
          :hint="$t('personal.prices.store-hint')"
          :readonly="!!keeping"
          persistent-hint
          maxlength="60"
          class="mb-2"
          data-testid="price-store"
        />
        <v-row density="compact">
          <v-col
            cols="12"
            sm="4"
          >
            <v-text-field
              v-model.number="form.price"
              type="number"
              min="0"
              step="0.05"
              inputmode="decimal"
              :label="$t('personal.prices.price')"
              :error-messages="priceInvalid ? [$t('personal.prices.price-invalid')] : []"
              data-testid="price-amount"
            />
          </v-col>
          <v-col
            cols="7"
            sm="4"
          >
            <v-text-field
              v-model.number="form.size"
              type="number"
              min="0"
              step="any"
              inputmode="decimal"
              :label="$t('personal.prices.size')"
              :error-messages="sizeIncomplete ? [$t('personal.prices.size-incomplete')] : []"
              data-testid="price-size"
            />
          </v-col>
          <v-col
            cols="5"
            sm="4"
          >
            <v-select
              v-model="form.sizeUnit"
              :items="unitItems"
              :label="$t('personal.prices.size-unit')"
              clearable
              data-testid="price-size-unit"
            />
          </v-col>
        </v-row>
        <div class="text-body-small text-medium-emphasis mb-2">
          {{ $t('personal.prices.size-help') }}
        </div>
        <v-switch
          v-model="form.byWeight"
          color="primary"
          hide-details
          :label="$t('personal.prices.by-weight')"
          data-testid="price-by-weight"
        />
        <div class="text-body-small text-medium-emphasis mb-3">
          {{ $t('personal.prices.by-weight-help') }}
        </div>
        <v-text-field
          v-model="form.label"
          :label="$t('personal.prices.label')"
          :placeholder="$t('personal.prices.label-hint')"
          data-testid="price-label"
        />
        <v-row density="compact">
          <v-col
            cols="12"
            sm="4"
          >
            <v-text-field
              v-model="form.promotion"
              :label="$t('personal.prices.promotion')"
              :placeholder="$t('personal.prices.promotion-hint')"
              data-testid="price-promotion"
            />
          </v-col>
          <v-col
            cols="6"
            sm="4"
          >
            <v-text-field
              v-model.number="form.regularPrice"
              type="number"
              min="0"
              step="0.05"
              inputmode="decimal"
              :label="$t('personal.prices.regular-price')"
              :error-messages="regularInvalid ? [$t('personal.prices.regular-invalid')] : []"
              data-testid="price-regular"
            />
          </v-col>
          <v-col
            cols="6"
            sm="4"
          >
            <v-text-field
              v-model="form.promotionEndsOn"
              type="date"
              :label="$t('personal.prices.promotion-ends')"
              clearable
              data-testid="price-promotion-ends"
            />
          </v-col>
        </v-row>
        <div class="text-body-small text-medium-emphasis">
          {{ $t('personal.prices.regular-price-hint') }}
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
        {{ $t('personal.prices.delete-confirm', { name: deleting?.food.name, store: deleting ? text.store(deleting.store) : '' }) }}
      </v-card-text>
    </BaseDialog>

    <div class="text-body-medium text-medium-emphasis mb-3">
      {{ $t('personal.prices.help') }}
    </div>

    <div class="d-flex flex-wrap align-center ga-2 mb-3">
      <v-text-field
        v-if="items.length > 5"
        v-model="filter"
        :label="$t('personal.prices.filter')"
        :prepend-inner-icon="$globals.icons.search"
        density="compact"
        clearable
        hide-details
        class="price-filter"
        data-testid="price-filter"
      />
      <v-spacer />
      <BaseButton
        create
        data-testid="price-add"
        @click="openCreate"
      >
        {{ $t('personal.common.add') }}
      </BaseButton>
    </div>

    <v-alert
      v-if="loaded && !items.length"
      type="info"
      variant="tonal"
      data-testid="price-empty"
    >
      {{ $t('personal.prices.empty') }}
    </v-alert>
    <div
      v-else-if="loaded && !visible.length"
      class="text-body-medium text-medium-emphasis"
    >
      {{ $t('personal.prices.no-match') }}
    </div>

    <v-card
      v-for="item in visible"
      :key="item.id"
      class="my-2"
      data-testid="price-item"
    >
      <v-card-text class="pa-3 d-flex align-start ga-1">
        <div class="flex-grow-1 price-text">
          <div class="d-flex align-center flex-wrap ga-2">
            <span
              class="text-title-medium font-weight-medium"
              data-testid="price-item-name"
            >{{ item.food.name }}</span>
            <v-chip
              size="small"
              variant="outlined"
              label
              data-testid="price-item-store"
            >
              {{ text.store(item.store) }}
            </v-chip>
            <v-chip
              v-if="promotionState(item) === 'active'"
              size="small"
              color="secondary"
              variant="tonal"
              label
              data-testid="price-item-promotion"
            >
              {{ item.promotion || $t('personal.prices.promotion') }}
            </v-chip>
          </div>
          <div
            class="text-body-large"
            data-testid="price-item-amount"
          >
            {{ packText(item) }}
            <span
              v-if="item.regularPrice && promotionState(item) !== 'over'"
              class="text-body-small text-medium-emphasis"
            >{{ $t('personal.prices.was', { price: text.money(item.regularPrice, item.currency) }) }}</span>
          </div>
          <div
            v-if="details(item)"
            class="text-body-medium text-medium-emphasis"
          >
            {{ details(item) }}
          </div>
          <div
            v-if="promotionState(item) === 'over'"
            class="text-body-small text-warning"
          >
            {{ $t('personal.prices.promotion-over') }}
          </div>
          <a
            v-if="webLink(item.productUrl)"
            :href="webLink(item.productUrl)!"
            target="_blank"
            rel="noopener noreferrer"
            class="text-body-small"
          >{{ $t('personal.prices.open-product') }}</a>
        </div>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.edit')"
          data-testid="price-item-edit"
          @click="openEdit(item)"
        >
          <v-icon>{{ $globals.icons.edit }}</v-icon>
        </v-btn>
        <v-btn
          icon
          variant="text"
          size="small"
          :aria-label="$t('personal.common.delete')"
          data-testid="price-item-delete"
          @click="askDelete(item)"
        >
          <v-icon>{{ $globals.icons.delete }}</v-icon>
        </v-btn>
      </v-card-text>
    </v-card>

    <h3 class="text-title-large mt-6 mb-2">
      {{ $t('personal.prices.source.title') }}
    </h3>
    <div
      v-if="status && !status.enabled"
      class="text-body-medium text-medium-emphasis"
      data-testid="price-source-disabled"
    >
      {{ $t('personal.prices.source.disabled') }}
    </div>
    <template v-else-if="status">
      <div class="text-body-medium text-medium-emphasis mb-3">
        {{ $t('personal.prices.source.help') }}
      </div>
      <v-form @submit.prevent="runSearch">
        <v-row
          density="compact"
          align="start"
        >
          <v-col
            cols="12"
            sm="5"
          >
            <v-text-field
              v-model="query"
              :label="$t('personal.prices.source.query')"
              :prepend-inner-icon="$globals.icons.search"
              :hint="$t('personal.pantry.products.min-chars')"
              density="compact"
              clearable
              data-testid="offer-query"
            />
          </v-col>
          <v-col
            cols="7"
            sm="4"
          >
            <v-select
              v-model="searchStore"
              :items="searchStoreItems"
              :label="$t('personal.prices.store')"
              density="compact"
              hide-details
              data-testid="offer-store"
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
              data-testid="offer-search"
            >
              {{ $t('personal.common.search') }}
            </v-btn>
          </v-col>
        </v-row>
      </v-form>

      <v-alert
        v-if="offers && !offers.available"
        type="info"
        variant="tonal"
        class="mb-3"
        data-testid="offer-unavailable"
      >
        {{ $t('personal.prices.source.unavailable') }}
      </v-alert>
      <template v-else-if="offers">
        <div
          v-if="offers.failedStores.length"
          class="text-body-small text-warning mb-1"
          data-testid="offer-failed-stores"
        >
          {{ $t('personal.prices.source.failed-stores', { stores: offers.failedStores.map(text.store).join(', ') }) }}
        </div>
        <div
          v-if="!offers.offers.length"
          class="text-body-medium text-medium-emphasis"
          data-testid="offer-no-results"
        >
          {{ $t('personal.prices.source.no-results', { query: offers.query }) }}
        </div>
        <div
          v-else
          class="text-body-small text-medium-emphasis mb-1"
        >
          {{ $t('personal.prices.source.results', { count: offers.offers.length }) }}
        </div>

        <v-card
          v-for="offer in offers.offers"
          :key="`${offer.store}-${offer.externalId}`"
          class="my-2"
          data-testid="offer-card"
        >
          <v-card-text class="pa-3 d-flex align-start ga-3">
            <img
              v-if="webLink(offer.imageUrl)"
              :src="webLink(offer.imageUrl)!"
              :alt="offer.name"
              class="offer-image"
              loading="lazy"
              referrerpolicy="no-referrer"
            >
            <div class="flex-grow-1 price-text">
              <div class="d-flex align-center flex-wrap ga-2">
                <span class="text-title-medium font-weight-medium">{{ offer.name }}</span>
                <v-chip
                  size="small"
                  variant="outlined"
                  label
                >
                  {{ text.store(offer.store) }}
                </v-chip>
                <v-chip
                  v-if="offer.promotion || (offer.regularPrice && offer.regularPrice > offer.price)"
                  size="small"
                  color="secondary"
                  variant="tonal"
                  label
                >
                  {{ offer.promotion || $t('personal.prices.promotion') }}
                </v-chip>
              </div>
              <div class="text-body-large">
                {{ offerText(offer) }}
                <span
                  v-if="offer.regularPrice && offer.regularPrice > offer.price"
                  class="text-body-small text-medium-emphasis"
                >{{ $t('personal.prices.was', { price: text.money(offer.regularPrice, offer.currency) }) }}</span>
              </div>
              <div
                v-if="offerDetails(offer)"
                class="text-body-medium text-medium-emphasis"
              >
                {{ offerDetails(offer) }}
              </div>
            </div>
          </v-card-text>
          <v-card-actions class="pt-0">
            <v-btn
              color="primary"
              variant="tonal"
              :prepend-icon="mdiCashMultiple"
              data-testid="offer-keep"
              @click="openKeep(offer)"
            >
              {{ $t('personal.prices.source.keep') }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </template>

      <div
        v-if="hasTracked"
        class="mt-4"
      >
        <v-btn
          variant="outlined"
          :prepend-icon="mdiRefresh"
          :loading="refreshing"
          data-testid="price-refresh"
          @click="refreshPrices"
        >
          {{ $t('personal.prices.source.refresh') }}
        </v-btn>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { mdiCashMultiple, mdiRefresh } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { useFoodStore } from "~/composables/store";
import { alert } from "~/composables/use-toast";
import type {
  FoodPriceCreate,
  FoodPriceOut,
  PriceOffer,
  PriceOfferSearchOut,
  PriceSizeUnit,
  PriceSourceStatus,
  RetailStore,
} from "~/lib/api/types/personal";

interface PriceForm {
  foodId: string | null;
  store: string | null;
  price: number | string;
  regularPrice: number | string;
  size: number | string;
  sizeUnit: PriceSizeUnit | null;
  byWeight: boolean;
  label: string;
  promotion: string;
  promotionEndsOn: string | null;
}

const ALL_STORES = "";
const stores: RetailStore[] = ["coop", "migros", "aldi", "lidl"];
const sizeUnits: PriceSizeUnit[] = ["g", "kg", "ml", "l", "piece"];

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();
const { store: foods } = useFoodStore();

const items = ref<FoodPriceOut[]>([]);
const loaded = ref(false);
const filter = ref<string | null>("");
const status = ref<PriceSourceStatus | null>(null);

const dialog = ref(false);
const saving = ref(false);
const editing = ref<FoodPriceOut | null>(null);
/** The offer of a shop that the user keeps as the price of a food. */
const keeping = ref<PriceOffer | null>(null);
const deleteDialog = ref(false);
const deleting = ref<FoodPriceOut | null>(null);

const query = ref<string | null>("");
const searchStore = ref<string>(ALL_STORES);
const searching = ref(false);
const offers = ref<PriceOfferSearchOut | null>(null);
const refreshing = ref(false);

function emptyForm(): PriceForm {
  return {
    foodId: null,
    store: null,
    price: "",
    regularPrice: "",
    size: "",
    sizeUnit: null,
    byWeight: false,
    label: "",
    promotion: "",
    promotionEndsOn: null,
  };
}
const form = ref<PriceForm>(emptyForm());

const storeNames = computed(() => stores.map(store => text.store(store)));
const unitItems = computed(() => sizeUnits.map(value => ({ value, title: i18n.t(`personal.prices.units.${value}`) })));
const searchStoreItems = computed(() => [
  { value: ALL_STORES, title: i18n.t("personal.pantry.stores.all") },
  ...stores.map(value => ({ value: value as string, title: text.store(value) })),
]);

const dialogTitle = computed(() => {
  if (keeping.value) {
    return i18n.t("personal.prices.source.keep-title");
  }
  return editing.value ? i18n.t("personal.prices.edit") : i18n.t("personal.prices.add");
});

function positive(value: number | string): boolean {
  return typeof value === "number" && value > 0;
}

const storeText = computed(() => (form.value.store ?? "").trim());
const priceInvalid = computed(() => form.value.price !== "" && !positive(form.value.price));
const hasSize = computed(() => form.value.size !== "" && form.value.size !== null);
const sizeIncomplete = computed(
  () => (hasSize.value && (!positive(form.value.size) || !form.value.sizeUnit)) || (!hasSize.value && !!form.value.sizeUnit),
);
const hasRegular = computed(() => form.value.regularPrice !== "" && form.value.regularPrice !== null);
const regularInvalid = computed(
  () =>
    hasRegular.value
    && (!positive(form.value.regularPrice) || (positive(form.value.price) && Number(form.value.regularPrice) < Number(form.value.price))),
);
const canSave = computed(
  () => !!form.value.foodId && !!storeText.value && positive(form.value.price) && !sizeIncomplete.value && !regularInvalid.value,
);

const visible = computed(() => {
  const term = (filter.value ?? "").trim().toLocaleLowerCase();
  return [...items.value]
    .filter(item => !term || item.food.name.toLocaleLowerCase().includes(term))
    .sort((a, b) => a.food.name.localeCompare(b.food.name, i18n.locale.value) || a.store.localeCompare(b.store));
});

const hasTracked = computed(() => items.value.some(item => item.source !== "manual" && item.externalId));
const canSearch = computed(() => (query.value ?? "").trim().length >= 2 && !searching.value);

/** Only a web address becomes a link or an image. Anything else stays out of `href` and `src`. */
function webLink(url: string | null | undefined): string | null {
  const value = url?.trim() ?? "";
  return /^https?:\/\//i.test(value) ? value : null;
}

function day(value: string): string {
  return i18n.d(new Date(`${value}T00:00:00`), "short");
}

function sizeText(size: number | null, unit: PriceSizeUnit | null): string {
  return size !== null && unit ? `${text.quantity(size)} ${i18n.t(`personal.prices.units.${unit}`)}` : "";
}

function packText(item: FoodPriceOut): string {
  const price = text.money(item.price, item.currency);
  const size = sizeText(item.size, item.sizeUnit);
  if (!size) {
    return i18n.t("personal.prices.pack-plain", { price });
  }
  return item.byWeight ? i18n.t("personal.prices.rate", { price, unit: size }) : i18n.t("personal.prices.pack", { price, size });
}

function promotionState(item: FoodPriceOut): "none" | "active" | "over" {
  if (!item.promotion && !item.regularPrice) {
    return "none";
  }
  if (item.promotionEndsOn) {
    const today = new Date().setHours(0, 0, 0, 0);
    if (new Date(`${item.promotionEndsOn}T00:00:00`).getTime() < today) {
      return "over";
    }
  }
  return "active";
}

function details(item: FoodPriceOut): string {
  const parts = [item.brand, item.label];
  if (item.promotionEndsOn && promotionState(item) === "active") {
    parts.push(i18n.t("personal.prices.promotion-until", { date: day(item.promotionEndsOn) }));
  }
  if (item.source !== "manual") {
    parts.push(
      item.fetchedAt
        ? i18n.t("personal.prices.fetched", { date: i18n.d(new Date(item.fetchedAt), "short") })
        : i18n.t("personal.prices.source-auto"),
    );
  }
  return parts.filter(Boolean).join(" · ");
}

function offerText(offer: PriceOffer): string {
  const price = text.money(offer.price, offer.currency);
  const size = sizeText(offer.size, offer.sizeUnit);
  return size ? i18n.t("personal.prices.pack", { price, size }) : i18n.t("personal.prices.pack-plain", { price });
}

function offerDetails(offer: PriceOffer): string {
  const parts = [offer.brand];
  if (offer.unitPrice !== null && offer.unitPricePer) {
    parts.push(i18n.t("personal.prices.rate", { price: text.money(offer.unitPrice, offer.currency), unit: offer.unitPricePer }));
  }
  if (offer.promotionEndsOn) {
    parts.push(i18n.t("personal.prices.promotion-until", { date: day(offer.promotionEndsOn) }));
  }
  return parts.filter(Boolean).join(" · ");
}

async function refresh() {
  const { data } = await api.prices.getAll(1, -1);
  items.value = data?.items ?? [];
  loaded.value = true;
}

async function loadStatus() {
  const { data } = await api.prices.getStatus();
  status.value = data ?? { enabled: false, name: null, stores: [] };
}

function openCreate() {
  editing.value = null;
  keeping.value = null;
  form.value = emptyForm();
  dialog.value = true;
}

function openEdit(item: FoodPriceOut) {
  editing.value = item;
  keeping.value = null;
  form.value = {
    foodId: item.foodId,
    store: text.store(item.store),
    price: item.price,
    regularPrice: item.regularPrice ?? "",
    size: item.size ?? "",
    sizeUnit: item.sizeUnit,
    byWeight: item.byWeight,
    label: item.label ?? "",
    promotion: item.promotion ?? "",
    promotionEndsOn: item.promotionEndsOn,
  };
  dialog.value = true;
}

function openKeep(offer: PriceOffer) {
  editing.value = null;
  keeping.value = offer;
  form.value = {
    foodId: null,
    store: text.store(offer.store),
    price: offer.price,
    regularPrice: offer.regularPrice && offer.regularPrice > offer.price ? offer.regularPrice : "",
    size: offer.size ?? "",
    sizeUnit: offer.sizeUnit,
    byWeight: false,
    label: offer.name,
    promotion: offer.promotion ?? "",
    promotionEndsOn: offer.promotionEndsOn,
  };
  dialog.value = true;
}

async function save() {
  if (!canSave.value || !form.value.foodId) {
    return;
  }
  const offer = keeping.value;
  const current = editing.value;
  const payload: FoodPriceCreate = {
    foodId: form.value.foodId,
    // A price kept from a shop keeps the key of the shop; a typed name is cleaned by the server.
    store: offer ? offer.store : storeText.value,
    price: Number(form.value.price),
    regularPrice: hasRegular.value ? Number(form.value.regularPrice) : null,
    size: hasSize.value ? Number(form.value.size) : null,
    sizeUnit: hasSize.value ? form.value.sizeUnit : null,
    byWeight: form.value.byWeight,
    label: form.value.label.trim() || null,
    promotion: form.value.promotion.trim() || null,
    promotionEndsOn: form.value.promotionEndsOn || null,
    brand: offer ? offer.brand : (current?.brand ?? null),
    source: offer ? "swissgroceries" : (current?.source ?? "manual"),
    externalId: offer ? offer.externalId : (current?.externalId ?? null),
    productUrl: offer ? webLink(offer.productUrl) : (current?.productUrl ?? null),
    imageUrl: offer ? webLink(offer.imageUrl) : (current?.imageUrl ?? null),
  };

  saving.value = true;
  const { data } = current ? await api.prices.updateOne(current.id, payload) : await api.prices.createOne(payload);
  saving.value = false;
  if (data) {
    alert.success(offer ? i18n.t("personal.prices.source.kept", { food: data.food.name }) : i18n.t("personal.common.saved"));
    dialog.value = false;
    await refresh();
  }
}

function askDelete(item: FoodPriceOut) {
  deleting.value = item;
  deleteDialog.value = true;
}

async function remove() {
  if (!deleting.value) {
    return;
  }
  const { data } = await api.prices.deleteOne(deleting.value.id);
  if (data) {
    alert.success(i18n.t("personal.common.deleted"));
    await refresh();
  }
}

async function runSearch() {
  if (!canSearch.value) {
    return;
  }
  searching.value = true;
  const { data } = await api.prices.searchOffers((query.value ?? "").trim(), (searchStore.value || null) as RetailStore | null);
  searching.value = false;
  offers.value = data ?? null;
}

async function refreshPrices() {
  refreshing.value = true;
  const { data } = await api.prices.refresh();
  refreshing.value = false;
  if (!data) {
    return;
  }
  if (!data.available) {
    alert.info(i18n.t("personal.prices.source.unavailable"));
  }
  else if (!data.updated && !data.unchanged && !data.failed) {
    alert.info(i18n.t("personal.prices.source.refresh-none"));
  }
  else {
    alert.success(i18n.t("personal.prices.source.refreshed", { updated: data.updated, unchanged: data.unchanged, failed: data.failed }));
  }
  await refresh();
}

onMounted(() => {
  refresh();
  loadStatus();
});
</script>

<style scoped>
.price-text {
  min-width: 0;
  overflow-wrap: anywhere;
}

.price-filter {
  flex: 1 1 220px;
  max-width: 360px;
}

.offer-image {
  flex: 0 0 64px;
  width: 64px;
  height: 64px;
  object-fit: contain;
  border-radius: 8px;
  background: #fff;
}
</style>
