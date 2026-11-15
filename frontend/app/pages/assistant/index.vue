<template>
  <v-container class="narrow-container pe-page">
    <PersonalPageHeader
      :icon="personalIcons.assistant"
      :title="$t('personal.assistant.title')"
      :subtitle="$t('personal.assistant.subtitle')"
    />

    <!-- Status -->
    <v-alert
      v-if="status?.enabled"
      type="success"
      variant="tonal"
      density="compact"
      class="mb-3"
      data-testid="assistant-status-enabled"
    >
      {{ $t('personal.assistant.status-enabled', {
        provider: status.providerName || $t('personal.assistant.unknown-provider'),
        model: status.model || $t('personal.assistant.unknown-model'),
      }) }}
    </v-alert>
    <v-alert
      v-else-if="statusLoaded"
      type="info"
      variant="tonal"
      class="mb-3"
      data-testid="assistant-status-disabled"
    >
      <div class="font-weight-medium mb-1">
        {{ $t('personal.assistant.disabled.title') }}
      </div>
      <div class="mb-3">
        {{ $t('personal.assistant.disabled.text') }}
      </div>
      <v-btn
        to="/group"
        color="info"
        variant="flat"
        size="small"
        :prepend-icon="$globals.icons.cog"
        data-testid="assistant-settings-link"
      >
        {{ $t('personal.assistant.disabled.settings') }}
      </v-btn>
    </v-alert>

    <!-- Privacy -->
    <v-card
      variant="outlined"
      class="mb-6"
      data-testid="assistant-privacy"
    >
      <v-card-text class="d-flex ga-3 py-3">
        <v-icon
          color="primary"
          :icon="personalIcons.dietary"
        />
        <div>
          <div class="font-weight-medium mb-1">
            {{ $t('personal.assistant.privacy.title') }}
          </div>
          <ul class="assistant-privacy__list text-body-2">
            <li>{{ $t('personal.assistant.privacy.guests') }}</li>
            <li>{{ $t('personal.assistant.privacy.quantities') }}</li>
            <li>{{ $t('personal.assistant.privacy.approval') }}</li>
          </ul>
        </div>
      </v-card-text>
    </v-card>

    <!-- Conversation -->
    <div class="d-flex align-center mb-2">
      <h3 class="text-h6">
        {{ $t('personal.assistant.chat.title') }}
      </h3>
      <v-spacer />
      <v-btn
        v-if="entries.length"
        variant="text"
        size="small"
        :disabled="sending"
        :prepend-icon="$globals.icons.refresh"
        data-testid="assistant-reset"
        @click="reset"
      >
        {{ $t('personal.assistant.chat.reset') }}
      </v-btn>
    </div>

    <div
      class="assistant-chat"
      aria-live="polite"
      data-testid="assistant-chat"
    >
      <div
        v-if="!entries.length"
        data-testid="assistant-suggestions"
      >
        <div class="text-body-2 text-medium-emphasis mb-2">
          {{ $t('personal.assistant.chat.empty') }}
        </div>
        <div class="d-flex flex-wrap ga-2">
          <v-chip
            v-for="key in suggestionKeys"
            :key="key"
            variant="tonal"
            color="primary"
            class="assistant-chat__suggestion"
            :disabled="sending"
            data-testid="assistant-suggestion"
            @click="send($t(`personal.assistant.suggestions.${key}`))"
          >
            {{ $t(`personal.assistant.suggestions.${key}`) }}
          </v-chip>
        </div>
      </div>

      <div
        v-for="entry in entries"
        :key="entry.id"
        class="assistant-message"
        :class="`assistant-message--${entry.role}`"
        :data-testid="`assistant-message-${entry.role}`"
      >
        <div
          v-if="entry.role === 'user'"
          class="assistant-bubble assistant-bubble--user"
        >
          {{ entry.content }}
        </div>
        <template v-else>
          <v-icon
            class="mt-2 text-medium-emphasis"
            :icon="personalIcons.assistant"
          />
          <div class="assistant-message__body">
            <div
              v-if="entry.content"
              class="assistant-bubble assistant-bubble--assistant"
              data-testid="assistant-reply"
            >
              {{ entry.content }}
            </div>
            <v-alert
              v-if="entry.notice"
              :type="entry.notice === 'NOT_CONFIGURED' ? 'info' : 'warning'"
              variant="tonal"
              density="compact"
              :class="entry.content ? 'mt-2' : undefined"
              data-testid="assistant-notice"
              :data-notice="entry.notice"
            >
              <div class="mb-0">
                {{ $t(`personal.assistant.notice.${entry.notice}`) }}
              </div>
              <v-btn
                v-if="entry.notice === 'NOT_CONFIGURED'"
                to="/group"
                variant="text"
                size="small"
                class="px-0 mt-1"
              >
                {{ $t('personal.assistant.disabled.settings') }}
              </v-btn>
            </v-alert>
            <div
              v-if="entry.tools.length"
              class="d-flex flex-wrap align-center ga-1 mt-2"
              data-testid="assistant-tools"
            >
              <span class="text-caption text-medium-emphasis mr-1">{{ $t('personal.assistant.chat.tools-used') }}</span>
              <v-chip
                v-for="tool in entry.tools"
                :key="tool.name"
                size="x-small"
                variant="outlined"
                data-testid="assistant-tool"
              >
                {{ toolLabel(tool) }}
              </v-chip>
            </div>
            <AssistantProposalCard
              v-for="proposal in entry.proposals"
              :key="proposal.id"
              class="mt-2"
              :proposal="proposal"
              :restriction-names="restrictionNames"
              @updated="onProposalUpdated"
              @deleted="onProposalDeleted"
            />
          </div>
        </template>
      </div>

      <div
        v-if="sending"
        class="assistant-message assistant-message--assistant"
        data-testid="assistant-loading"
      >
        <v-icon
          class="mt-2 text-medium-emphasis"
          :icon="personalIcons.assistant"
        />
        <div class="assistant-bubble assistant-bubble--assistant d-flex align-center ga-2">
          <v-progress-circular
            indeterminate
            size="16"
            width="2"
          />
          <span class="text-medium-emphasis">{{ $t('personal.assistant.chat.thinking') }}</span>
        </div>
      </div>
      <div ref="end" />
    </div>

    <!-- Composer -->
    <v-select
      v-model="eventId"
      :items="eventItems"
      :label="$t('personal.assistant.chat.event')"
      :no-data-text="$t('personal.assistant.chat.no-event')"
      :prepend-inner-icon="personalIcons.events"
      density="compact"
      clearable
      hide-details
      class="mt-4 mb-2"
      data-testid="assistant-event"
    />
    <div class="d-flex align-end ga-2">
      <v-textarea
        v-model="input"
        :label="$t('personal.assistant.chat.input')"
        :hint="$t('personal.assistant.chat.input-hint')"
        rows="1"
        max-rows="6"
        maxlength="4000"
        auto-grow
        persistent-hint
        data-testid="assistant-input"
        @keydown.enter="onEnter"
      />
      <v-btn
        icon
        color="primary"
        class="mb-6"
        :disabled="!input.trim() || sending"
        :aria-label="$t('personal.assistant.chat.send')"
        data-testid="assistant-send"
        @click="send()"
      >
        <v-icon :icon="mdiSend" />
      </v-btn>
    </div>

    <!-- Proposals -->
    <v-divider class="my-6" />
    <div class="d-flex align-center flex-wrap ga-2 mb-1">
      <h3 class="text-h6">
        {{ $t('personal.assistant.proposals.title') }}
      </h3>
      <v-chip
        v-if="pendingCount"
        size="small"
        color="info"
        variant="flat"
        data-testid="assistant-pending-count"
      >
        {{ $t('personal.assistant.proposals.pending', pendingCount) }}
      </v-chip>
    </div>
    <div class="text-body-2 text-medium-emphasis mb-3">
      {{ $t('personal.assistant.proposals.help') }}
    </div>
    <v-alert
      v-if="proposalsLoaded && !sortedProposals.length"
      type="info"
      variant="tonal"
      density="compact"
      data-testid="assistant-proposals-empty"
    >
      {{ $t('personal.assistant.proposals.empty') }}
    </v-alert>
    <div data-testid="assistant-proposals">
      <AssistantProposalCard
        v-for="proposal in sortedProposals"
        :key="proposal.id"
        class="mb-3"
        :proposal="proposal"
        :restriction-names="restrictionNames"
        deletable
        @updated="onProposalUpdated"
        @deleted="onProposalDeleted"
      />
    </div>
  </v-container>
</template>

<script setup lang="ts">
import PersonalPageHeader from "~/components/Domain/Personal/PersonalPageHeader.vue";
import { mdiSend } from "@mdi/js";
import AssistantProposalCard from "~/components/Domain/Assistant/AssistantProposalCard.vue";
import { usePersonalApi } from "~/composables/personal/use-personal-api";
import { personalIcons } from "~/composables/personal/use-personal-nav";
import type { AiProposalOut, AssistantStatus, MealEventSummary } from "~/lib/api/types/personal";

definePageMeta({
  middleware: ["auth"],
});

const i18n = useI18n();
const api = usePersonalApi();
const route = useRoute();

useSeoMeta({ title: i18n.t("personal.assistant.title") });

/** Why the assistant gave no usable answer. */
type Notice = "NOT_CONFIGURED" | "PROVIDER_ERROR" | "TOO_MANY_STEPS" | "EMPTY" | "REQUEST_FAILED";
interface ChatEntry {
  id: number;
  role: "user" | "assistant";
  content: string;
  tools: { name: string; count: number }[];
  proposals: AiProposalOut[];
  notice: Notice | null;
  /** Sent back to the assistant as history. A question without an answer is left out. */
  remembered: boolean;
}

const maxHistory = 12;
const suggestionKeys = ["stock", "menu", "adapt", "shopping"];

const status = ref<AssistantStatus | null>(null);
const statusLoaded = ref(false);
const events = ref<MealEventSummary[]>([]);
const restrictionNames = ref<Record<string, string>>({});

// The conversation lives in the page only: it goes away with the page.
const entries = ref<ChatEntry[]>([]);
const input = ref("");
const sending = ref(false);
const eventId = ref<string | null>(typeof route.query.event === "string" ? route.query.event : null);
const end = ref<HTMLElement | null>(null);
let nextId = 1;

const proposals = ref<AiProposalOut[]>([]);
const proposalsLoaded = ref(false);

const eventItems = computed(() =>
  events.value.map(event => ({
    value: event.id,
    title: event.startsAt ? `${event.name} · ${i18n.d(new Date(event.startsAt), "short")}` : event.name,
  })),
);

const sortedProposals = computed(() => {
  // The server sorts by date. Here the proposals that wait for a decision come first.
  const pending = proposals.value.filter(proposal => proposal.status === "PENDING");
  const decided = proposals.value.filter(proposal => proposal.status !== "PENDING");
  return [...pending, ...decided];
});
const pendingCount = computed(() => proposals.value.filter(proposal => proposal.status === "PENDING").length);

/** The name of a function in plain words. A function that this page does not know keeps its technical name. */
function toolLabel(tool: { name: string; count: number }): string {
  const key = `personal.assistant.tools.${tool.name}`;
  const label = i18n.te(key) ? i18n.t(key) : tool.name;
  return tool.count > 1 ? `${label} ×${tool.count}` : label;
}

function countTools(names: string[]): ChatEntry["tools"] {
  const counts = new Map<string, number>();
  for (const name of names) {
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  return [...counts].map(([name, count]) => ({ name, count }));
}

function add(entry: Omit<ChatEntry, "id">): ChatEntry {
  entries.value.push({ id: nextId++, ...entry });
  return entries.value[entries.value.length - 1]!;
}

async function scrollToEnd() {
  await nextTick();
  end.value?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

async function refreshProposals() {
  const { data } = await api.assistant.getProposals();
  if (data) {
    proposals.value = data.items;
  }
  proposalsLoaded.value = true;
}

async function send(prompt?: string) {
  const message = (prompt ?? input.value).trim();
  if (!message || sending.value) {
    return;
  }

  const history = entries.value
    .filter(entry => entry.remembered)
    .slice(-maxHistory)
    .map(entry => ({ role: entry.role, content: entry.content }));

  const question = add({ role: "user", content: message, tools: [], proposals: [], notice: null, remembered: false });
  if (!prompt) {
    input.value = "";
  }
  sending.value = true;
  scrollToEnd();

  const { data } = await api.assistant.chat({ message, history, eventId: eventId.value || null });
  sending.value = false;

  if (!data) {
    add({ role: "assistant", content: "", tools: [], proposals: [], notice: "REQUEST_FAILED", remembered: false });
  }
  else {
    const reply = data.reply.trim();
    let notice: Notice | null = null;
    if (!data.available) {
      notice = data.error === "NOT_CONFIGURED" ? "NOT_CONFIGURED" : "PROVIDER_ERROR";
    }
    else if (data.error === "TOO_MANY_STEPS") {
      notice = "TOO_MANY_STEPS";
    }
    else if (!reply && !data.proposals.length) {
      notice = "EMPTY";
    }

    const answered = data.available && !!reply;
    question.remembered = answered;
    add({
      role: "assistant",
      content: reply,
      tools: countTools(data.toolCalls.map(call => call.name)),
      proposals: data.proposals,
      notice,
      remembered: answered,
    });
  }

  scrollToEnd();
  await refreshProposals();
}

function onEnter(event: KeyboardEvent) {
  // Shift+Enter makes a new line. Enter while an input method composes a character belongs to that method.
  if (event.shiftKey || event.isComposing) {
    return;
  }
  event.preventDefault();
  send();
}

function reset() {
  entries.value = [];
}

function onProposalUpdated(updated: AiProposalOut) {
  const replace = (list: AiProposalOut[]) => list.map(proposal => (proposal.id === updated.id ? updated : proposal));
  proposals.value = replace(proposals.value);
  for (const entry of entries.value) {
    entry.proposals = replace(entry.proposals);
  }
  refreshProposals();
}

function onProposalDeleted(id: string) {
  proposals.value = proposals.value.filter(proposal => proposal.id !== id);
  for (const entry of entries.value) {
    entry.proposals = entry.proposals.filter(proposal => proposal.id !== id);
  }
  refreshProposals();
}

onMounted(async () => {
  const [statusResult, eventsResult, restrictionsResult] = await Promise.all([
    api.assistant.getStatus(),
    api.mealEvents.getAll(1, -1),
    api.dietary.getRestrictions(),
    refreshProposals(),
  ]);
  status.value = statusResult.data;
  statusLoaded.value = true;
  events.value = eventsResult.data?.items ?? [];
  restrictionNames.value = Object.fromEntries((restrictionsResult.data ?? []).map(item => [item.key, item.name]));
});
</script>

<style scoped>
.assistant-privacy__list {
  padding-left: 1.1rem;
  margin: 0;
}

.assistant-chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.assistant-chat__suggestion {
  max-width: 100%;
}

.assistant-message {
  display: flex;
  gap: 8px;
  min-width: 0;
}

.assistant-message--user {
  justify-content: flex-end;
}

.assistant-message__body {
  flex: 1 1 auto;
  min-width: 0;
}

.assistant-bubble {
  display: inline-block;
  max-width: 100%;
  padding: 8px 12px;
  border-radius: 14px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.assistant-bubble--user {
  max-width: 85%;
  color: rgb(var(--v-theme-on-primary));
  background: rgb(var(--v-theme-primary));
  border-bottom-right-radius: 4px;
}

.assistant-bubble--assistant {
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-bottom-left-radius: 4px;
}
</style>
