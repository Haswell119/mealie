<template>
  <BaseDialog
    v-model="open"
    :title="$t('personal.prices.match.title')"
    :icon="mdiStoreSearchOutline"
    max-width="760"
    width="100%"
    can-submit
    :submit-text="$t('personal.prices.match.keep', { count: chosen.length }, chosen.length)"
    :submit-icon="$globals.icons.save"
    :submit-disabled="!chosen.length || saving || loading"
    disable-submit-on-enter
    keep-open
    @submit="keep"
  >
    <v-card-text
      class="match-body"
      data-testid="store-match"
    >
      <p class="text-body-small text-medium-emphasis mb-2">
        {{ $t('personal.prices.match.help') }}
      </p>
      <v-alert
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3 text-body-small"
        data-testid="store-match-warning"
      >
        {{ $t('personal.prices.match.warning') }}
      </v-alert>

      <div
        v-if="loading"
        class="d-flex align-center ga-3 py-6"
        data-testid="store-match-loading"
      >
        <v-progress-circular
          indeterminate
          size="24"
          color="primary"
        />
        <span class="text-body-medium">{{ $t('personal.prices.match.searching') }}</span>
      </div>

      <v-alert
        v-else-if="result && !result.available"
        type="info"
        variant="tonal"
        data-testid="store-match-unavailable"
      >
        {{ $t('personal.prices.match.unavailable') }}
      </v-alert>

      <template v-else-if="result">
        <v-alert
          v-if="!searchedLines.length"
          type="info"
          variant="tonal"
          class="mb-3"
          data-testid="store-match-nothing"
        >
          {{ $t('personal.prices.match.nothing') }}
        </v-alert>

        <section
          v-for="line in searchedLines"
          :key="line.key"
          class="match-line"
          data-testid="store-match-line"
        >
          <div class="text-body-large font-weight-medium match-wrap">
            {{ line.display || line.foodName }}
          </div>
          <div class="d-flex flex-wrap align-center ga-2 text-body-small text-medium-emphasis">
            <span data-testid="store-match-query">{{ $t('personal.prices.match.searched-as', { query: line.query }) }}</span>
            <v-btn
              variant="text"
              size="x-small"
              color="primary"
              :disabled="busyLine === line.key"
              @click="toggleQuery(line)"
            >
              {{ $t('personal.prices.match.change-query') }}
            </v-btn>
          </div>
          <div
            v-if="editingKey === line.key"
            class="d-flex align-start ga-2 mt-2"
          >
            <v-text-field
              v-model="typedQuery"
              :label="$t('personal.prices.match.query-label')"
              :hint="$t('personal.prices.match.query-hint')"
              persistent-hint
              density="compact"
              maxlength="80"
              data-testid="store-match-query-input"
              @keydown.enter.prevent="searchLine(line)"
            />
            <v-btn
              color="primary"
              variant="tonal"
              :loading="busyLine === line.key"
              :disabled="typedQuery.trim().length < 2"
              data-testid="store-match-query-search"
              @click="searchLine(line)"
            >
              {{ $t('personal.prices.match.search-again') }}
            </v-btn>
          </div>

          <div
            v-for="store in line.stores"
            :key="store.store"
            class="match-store"
            :data-store="store.store"
            data-testid="store-match-store"
          >
            <div class="text-body-medium font-weight-medium">
              {{ text.store(store.store) }}
              <span
                v-if="store.hasStored && store.storedPrice !== null"
                class="text-body-small text-medium-emphasis font-weight-regular"
              >· {{ $t('personal.prices.match.stored', { price: text.money(store.storedPrice) }) }}</span>
            </div>
            <template v-if="store.searched">
              <div
                v-if="store.failed"
                class="text-body-small text-warning"
              >
                {{ $t('personal.prices.match.failed') }}
              </div>
              <div
                v-else-if="!store.candidates.length"
                class="text-body-small text-medium-emphasis"
              >
                {{ $t('personal.prices.match.none') }}
              </div>
              <v-radio-group
                v-else
                v-model="selection[choiceKey(line.key, store.store)]"
                density="compact"
                hide-details
                class="match-choices"
              >
                <v-radio
                  v-for="candidate in store.candidates"
                  :key="candidate.offer.externalId"
                  :value="candidate.offer.externalId"
                  data-testid="store-match-candidate"
                >
                  <template #label>
                    <div class="match-wrap">
                      <div class="text-body-medium">
                        {{ candidateName(candidate) }}
                        <v-chip
                          v-if="!candidate.confident"
                          size="x-small"
                          color="warning"
                          variant="tonal"
                          label
                          class="ml-1"
                        >
                          {{ $t('personal.prices.match.uncertain') }}
                        </v-chip>
                      </div>
                      <div class="text-body-small text-medium-emphasis">
                        {{ candidateDetail(candidate) }}
                      </div>
                    </div>
                  </template>
                </v-radio>
                <v-radio
                  :value="NONE"
                  :label="$t('personal.prices.match.skip')"
                />
              </v-radio-group>
            </template>
          </div>
        </section>

        <div
          v-for="line in skippedLines"
          :key="line.key"
          class="text-body-small text-medium-emphasis match-wrap"
          data-testid="store-match-skipped"
        >
          {{ line.display || line.foodName }} · {{ reason(line.reason) }}
        </div>

        <v-btn
          v-if="hasStored"
          variant="text"
          size="small"
          color="primary"
          class="mt-2"
          :prepend-icon="mdiRefresh"
          data-testid="store-match-refresh"
          @click="load(true)"
        >
          {{ $t('personal.prices.match.refresh') }}
        </v-btn>
      </template>
    </v-card-text>
  </BaseDialog>
</template>

<script setup lang="ts">
import { mdiRefresh, mdiStoreSearchOutline } from "@mdi/js";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { usePersonalText } from "~/composables/personal/use-personal-text";
import { alert } from "~/composables/use-toast";
import type { FoodPriceCreate, StoreMatchCandidate, StoreMatchLine, StoreMatchOut } from "~/lib/api/types/personal";

/** The choice "keep nothing" for a shop. No product of a shop has this id. */
const NONE = "";

const props = defineProps<{ planId: string }>();
const open = defineModel<boolean>({ default: false });
const emit = defineEmits<{ kept: [] }>();

const i18n = useI18n();
const api = usePersonalApi();
const text = usePersonalText();

const result = ref<StoreMatchOut | null>(null);
const loading = ref(false);
const saving = ref(false);
const selection = ref<Record<string, string>>({});
const editingKey = ref<string | null>(null);
const typedQuery = ref("");
const busyLine = ref<string | null>(null);
let request = 0;

function choiceKey(lineKey: string, store: string): string {
  return `${lineKey}|${store}`;
}

/** A product that fits well is chosen for the person. A doubtful one waits for the person to choose it. */
function preselect(lines: StoreMatchLine[]) {
  for (const line of lines) {
    for (const store of line.stores) {
      const first = store.candidates[0];
      selection.value[choiceKey(line.key, store.store)] = first && first.confident ? first.offer.externalId : NONE;
    }
  }
}

async function load(refresh = false) {
  const current = ++request;
  loading.value = true;
  editingKey.value = null;
  const { data } = await api.shoppingPlans.matchStores(props.planId, { refresh });
  if (current !== request) {
    return;
  }
  loading.value = false;
  result.value = data ?? { planId: props.planId, available: false, lines: [], searchedLines: 0 };
  selection.value = {};
  preselect(result.value.lines);
}

const searchedLines = computed(() =>
  (result.value?.lines ?? []).filter(line => !line.reason && line.stores.some(store => store.searched)),
);
const skippedLines = computed(() => (result.value?.lines ?? []).filter(line => !!line.reason));
const hasStored = computed(() => (result.value?.lines ?? []).some(line => line.stores.some(store => store.hasStored)));

function toggleQuery(line: StoreMatchLine) {
  editingKey.value = editingKey.value === line.key ? null : line.key;
  typedQuery.value = line.query;
}

/** Search one line again with the text that the person typed. */
async function searchLine(line: StoreMatchLine) {
  const query = typedQuery.value.trim();
  if (query.length < 2 || !result.value) {
    return;
  }
  busyLine.value = line.key;
  const { data } = await api.shoppingPlans.matchStores(props.planId, { keys: [line.key], queries: { [line.key]: query } });
  busyLine.value = null;
  const found = data?.lines.find(item => item.key === line.key);
  if (!data?.available || !found) {
    alert.error(i18n.t("personal.prices.match.unavailable"));
    return;
  }
  result.value.lines = result.value.lines.map(item => (item.key === line.key ? found : item));
  preselect([found]);
  editingKey.value = null;
}

function candidateName(candidate: StoreMatchCandidate): string {
  const { brand, name } = candidate.offer;
  return brand && !name.toLocaleLowerCase().includes(brand.toLocaleLowerCase()) ? `${brand} ${name}` : name;
}

function candidateDetail(candidate: StoreMatchCandidate): string {
  const { offer } = candidate;
  const parts: string[] = [];
  const price = text.money(offer.price, offer.currency);
  if (offer.size !== null && offer.sizeUnit) {
    const size = `${text.quantity(offer.size)} ${i18n.t(`personal.prices.units.${offer.sizeUnit}`)}`;
    parts.push(i18n.t("personal.prices.pack", { price, size }));
  }
  else {
    parts.push(i18n.t("personal.prices.pack-plain", { price }));
  }
  if (offer.regularPrice !== null) {
    parts.push(i18n.t("personal.prices.was", { price: text.money(offer.regularPrice, offer.currency) }));
  }
  if (candidate.cost !== null) {
    parts.push(i18n.t("personal.prices.match.line-cost", { cost: text.money(candidate.cost, offer.currency) }));
  }
  return parts.join(" · ");
}

function reason(code: string | null): string {
  const key = `personal.prices.match.reason.${code}`;
  return i18n.te(key) ? i18n.t(key) : (code ?? "");
}

/** Only a web address is stored as a link. */
function webLink(url: string | null | undefined): string | null {
  const value = url?.trim() ?? "";
  return /^https?:\/\//i.test(value) ? value : null;
}

/** The prices to keep: one for each shop of each line where the person chose a product. */
const chosen = computed<FoodPriceCreate[]>(() => {
  const prices: FoodPriceCreate[] = [];
  for (const line of searchedLines.value) {
    for (const store of line.stores) {
      const id = selection.value[choiceKey(line.key, store.store)];
      const candidate = id ? store.candidates.find(item => item.offer.externalId === id) : undefined;
      if (!candidate || !line.foodId) {
        continue;
      }
      const { offer } = candidate;
      prices.push({
        foodId: line.foodId,
        store: offer.store,
        label: offer.name,
        brand: offer.brand,
        price: offer.price,
        regularPrice: offer.regularPrice,
        size: offer.size,
        sizeUnit: offer.size !== null ? offer.sizeUnit : null,
        promotion: offer.promotion,
        promotionEndsOn: offer.promotionEndsOn,
        source: "swissgroceries",
        externalId: offer.externalId,
        productUrl: webLink(offer.productUrl),
        imageUrl: webLink(offer.imageUrl),
      });
    }
  }
  return prices;
});

async function keep() {
  if (!chosen.value.length) {
    return;
  }
  saving.value = true;
  const { data } = await api.prices.saveMany(chosen.value);
  saving.value = false;
  if (data) {
    alert.success(i18n.t("personal.prices.match.kept", { count: data.length }, data.length));
    emit("kept");
    open.value = false;
  }
}

watch(open, (value) => {
  if (value) {
    load();
  }
  else {
    request++;
  }
});
</script>

<style scoped>
.match-body {
  max-height: min(70vh, 720px);
  overflow-y: auto;
}

.match-line {
  padding: 12px 0;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.match-store {
  margin-top: 10px;
}

.match-choices :deep(.v-label) {
  opacity: 1;
  align-items: flex-start;
}

.match-choices :deep(.v-radio) {
  align-items: flex-start;
  padding: 2px 0;
}

.match-wrap {
  min-width: 0;
  overflow-wrap: anywhere;
}
</style>
