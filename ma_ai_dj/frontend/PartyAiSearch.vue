<template>
  <div class="space-y-3">
    <p v-if="!tabs.length" role="status">
      Music search is disabled in Home Assistant.
    </p>
    <div class="flex gap-2" role="tablist" aria-label="Music search mode">
      <Button
        v-for="tab in tabs"
        :key="tab.id"
        :variant="mode === tab.id ? 'default' : 'outline'"
        role="tab"
        :aria-selected="mode === tab.id"
        @click="changeMode(tab.id)"
        >{{ tab.label }}</Button
      >
    </div>
    <p class="text-sm text-muted-foreground">{{ help }}</p>
    <MediaSearch
      v-if="mode === 'search' && libraryEnabled"
      v-model="query"
      :allowed-media-types="[MediaType.TRACK, MediaType.ARTIST]"
      :placeholder="$t('providers.party.guest_page.search_placeholder')"
      @select="emit('select', $event)"
    />
    <form v-else-if="tabs.length" class="flex gap-2" @submit.prevent="search">
      <SearchInput
        v-model="query"
        class="flex-1"
        :placeholder="
          mode === 'ai'
            ? 'Quiet jazz with saxophone…'
            : 'Calm jazz with saxophone…'
        "
        :maxlength="1000"
      />
      <Button type="submit" :disabled="busy || !query.trim()">{{
        busy ? $t("searching") : $t("search")
      }}</Button>
    </form>
    <Button
      v-if="similarEnabled && currentTrack"
      variant="outline"
      :disabled="busy"
      @click="similarToCurrent"
    >
      Similar to {{ currentTrack.name }}
    </Button>
    <p v-if="status" role="status" class="text-sm text-muted-foreground">
      {{ status }}
    </p>
  </div>
</template>

<script setup lang="ts">
import MediaSearch from "@/components/MediaSearch.vue";
import { SearchInput } from "@/components/ui/search-input";
import { Button } from "@/components/ui/button";
import api from "@/plugins/api";
import {
  MediaType,
  type MediaItemTypeOrItemMapping,
  type Track,
} from "@/plugins/api/interfaces";
import { $t } from "@/plugins/i18n";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps<{ currentTrack?: Track | null }>();
const emit = defineEmits<{
  select: [item: MediaItemTypeOrItemMapping];
  results: [tracks: Track[]];
}>();
type Mode = "search" | "similar" | "ai";
const mode = ref<Mode>("search"),
  query = ref(""),
  aiEnabled = ref(false),
  libraryEnabled = ref(true),
  similarEnabled = ref(true),
  busy = ref(false),
  status = ref("");
let revision = 0,
  timer: ReturnType<typeof setTimeout> | undefined;
let configTimer: ReturnType<typeof setInterval> | undefined;
let disposed = false;
const tabs = computed(() => [
  ...(libraryEnabled.value
    ? [{ id: "search" as Mode, label: $t("search") }]
    : []),
  ...(similarEnabled.value
    ? [{ id: "similar" as Mode, label: "Similar" }]
    : []),
  ...(aiEnabled.value ? [{ id: "ai" as Mode, label: "AI DJ" }] : []),
]);
const help = computed(() =>
  mode.value === "ai"
    ? "Describe your music wish. AI suggestions are matched against your connected music sources."
    : mode.value === "similar"
      ? "Use the current track, or describe a sound to search your Sonic Similarity library."
      : "Find a track or artist in your music sources.",
);
function changeMode(value: Mode) {
  mode.value = value;
  revision++;
  clearTimeout(timer);
  busy.value = false;
  status.value = "";
  emit("results", []);
}
function failed(error: unknown, run: number) {
  if (run === revision) {
    busy.value = false;
    status.value = error instanceof Error ? error.message : "Search failed";
  }
}
async function search() {
  const prompt = query.value.trim();
  if (!prompt || busy.value) return;
  const run = ++revision;
  busy.value = true;
  status.value = $t("searching");
  emit("results", []);
  try {
    if (mode.value === "similar") {
      const found = await api.sendCommand<{ tracks: Track[] }>("music/search", {
        search_query: prompt,
        media_types: ["track"],
        providers: ["sonic_similarity"],
        limit: 12,
      });
      if (run === revision) {
        emit("results", found.tracks || []);
        busy.value = false;
        status.value = found.tracks?.length
          ? ""
          : "No matches. Enable and analyse Sonic Similarity first.";
      }
    } else {
      const job = await api.sendCommand<{ id: string }>("ai_dj/suggest", {
        prompt,
        count: 8,
      });
      if (run === revision) await poll(job.id, run, Date.now());
    }
  } catch (error) {
    failed(error, run);
  }
}
async function poll(id: string, run: number, started: number) {
  if (run !== revision) return;
  if (Date.now() - started > 180000) {
    failed(new Error("AI request timed out"), run);
    return;
  }
  try {
    const job = await api.sendCommand<{
      state: string;
      tracks?: Track[];
      progress?: string;
      error?: string;
    }>("ai_dj/job", { job_id: id });
    if (run !== revision) return;
    if (job.state === "error")
      throw new Error(job.error || "AI could not find music");
    if (job.state === "ready") {
      emit("results", job.tracks || []);
      busy.value = false;
      status.value = job.tracks?.length
        ? ""
        : "No playable matches in your music sources";
      return;
    }
    status.value = job.progress || "AI is finding music…";
    timer = setTimeout(() => void poll(id, run, started), 1500);
  } catch (error) {
    failed(error, run);
  }
}
async function similarToCurrent() {
  const track = props.currentTrack;
  if (!track || busy.value) return;
  const run = ++revision;
  busy.value = true;
  status.value = $t("searching");
  emit("results", []);
  try {
    const tracks = await api.sendCommand<Track[]>(
      "music/tracks/similar_tracks",
      {
        item_id: track.item_id,
        provider_instance_id_or_domain: track.provider,
        limit: 12,
        allow_lookup: true,
      },
    );
    if (run === revision) {
      emit("results", tracks);
      busy.value = false;
      status.value = tracks.length ? "" : "No similar tracks found";
    }
  } catch (error) {
    failed(error, run);
  }
}
async function refreshConfig() {
  try {
    const config = await api.sendCommand<{
      enabled: boolean;
      library: boolean;
      similar: boolean;
      ai: boolean;
    }>("ai_dj/config");
    if (disposed) return;
    libraryEnabled.value = config.library;
    similarEnabled.value = config.similar;
    aiEnabled.value = config.enabled && config.ai;
  } catch {
    if (disposed) return;
    aiEnabled.value = false;
  }
  if (!tabs.value.some((tab) => tab.id === mode.value)) {
    changeMode(tabs.value[0]?.id || "search");
  }
}
onMounted(() => {
  void refreshConfig();
  configTimer = setInterval(() => void refreshConfig(), 15000);
});
onBeforeUnmount(() => {
  disposed = true;
  clearInterval(configTimer);
  revision++;
  clearTimeout(timer);
});
</script>
