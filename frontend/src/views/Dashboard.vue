<template>
  <div class="space-y-6">
    <!-- Top: Video + SOP Progress + Alerts -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Video Stream (takes 2 columns) -->
      <div class="lg:col-span-2 space-y-4">
        <VideoStream />
        <!-- Video File Analysis -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <div class="flex items-center space-x-4">
            <label class="text-sm font-medium text-gray-700">Analyze Video File:</label>
            <input
              type="file"
              accept="video/*"
              @change="handleVideoUpload"
              ref="fileInput"
              class="text-sm text-gray-500 file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
            <span v-if="videoAnalyzing" class="text-sm text-blue-600">Analyzing...</span>
          </div>
          <div v-if="videoResult" class="mt-3 text-sm">
            <div class="flex items-center space-x-4 text-gray-600">
              <span>Duration: {{ videoResult.video_info?.duration }}s</span>
              <span>Sampled: {{ videoResult.video_info?.sampled_frames }} frames</span>
              <span class="text-green-600 font-medium">Matches: {{ videoResult.matching_events }}</span>
            </div>
            <div v-if="videoResult.timeline?.length > 0" class="mt-2 max-h-40 overflow-y-auto">
              <div v-for="evt in videoResult.timeline.slice(0, 20)" :key="evt.frame" class="text-xs text-gray-500 py-0.5">
                <span class="text-gray-400">{{ evt.timestamp }}s</span>
                <span v-for="d in evt.detections" :key="d.step_id" class="ml-2">
                  <span class="text-blue-600">{{ d.step_name }}</span>
                  <span class="text-gray-400">({{ (d.avg_confidence * 100).toFixed(0) }}%)</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right sidebar: SOP Progress + Alerts -->
      <div class="space-y-6">
        <SopProgress />
        <AlertPanel />
      </div>
    </div>

    <!-- Top-3 Detection Candidates -->
    <div v-if="candidates.length > 0" class="bg-white rounded-lg shadow-sm border p-4">
      <h3 class="font-medium mb-3">Top Detection Candidates</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div
          v-for="(c, i) in candidates"
          :key="c.step_id + c.sop_id"
          class="flex items-center space-x-3 p-3 rounded-lg"
          :class="i === 0 ? 'bg-green-50 border border-green-200' : 'bg-gray-50'"
        >
          <span
            class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
            :class="i === 0 ? 'bg-green-500 text-white' : 'bg-gray-300 text-gray-700'"
          >{{ i + 1 }}</span>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">{{ c.step_name }}</div>
            <div class="text-xs text-gray-500">{{ c.sop_id }}</div>
          </div>
          <div class="text-right">
            <div class="text-sm font-medium" :class="i === 0 ? 'text-green-700' : 'text-gray-600'">
              {{ (c.confidence * 100).toFixed(0) }}%
            </div>
            <div class="text-xs text-gray-400">{{ c.matched_objects?.join(', ') }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom: Statistics Charts -->
    <StatsChart :refreshKey="statsRefreshKey" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import axios from 'axios'
import VideoStream from '../components/VideoStream.vue'
import SopProgress from '../components/SopProgress.vue'
import AlertPanel from '../components/AlertPanel.vue'
import StatsChart from '../components/StatsChart.vue'
import { useWebSocket } from '../composables/useWebSocket'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()
const { data, connected } = useWebSocket()
const statsRefreshKey = ref(0)
const candidates = ref([])
const videoAnalyzing = ref(false)
const videoResult = ref(null)
const fileInput = ref(null)
let candidatesTimer = null

// Sync WebSocket state to store
watch(connected, (val) => store.setWsConnected(val))
watch(data, (msg) => {
  if (msg) {
    store.handleWsMessage(msg)
    // Trigger stats refresh on sop_event or alert
    if (msg.type === 'sop_event' || msg.type === 'alert') {
      statsRefreshKey.value++
      fetchCandidates()
    }
  }
})

async function fetchCandidates() {
  try {
    const { data } = await axios.get('/api/monitor/detection/candidates')
    candidates.value = data.candidates || []
  } catch {
    // ignore
  }
}

async function handleVideoUpload(event) {
  const file = event.target.files[0]
  if (!file) return

  videoAnalyzing.value = true
  videoResult.value = null

  try {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await axios.post('/api/video/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    videoResult.value = data
  } catch (e) {
    videoResult.value = { error: e.response?.data?.error || e.message }
  } finally {
    videoAnalyzing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

onMounted(async () => {
  await Promise.all([
    store.fetchStatus(),
    store.fetchAlerts(),
    store.fetchSopList(),
  ])
  fetchCandidates()
  candidatesTimer = setInterval(fetchCandidates, 3000)
})
onUnmounted(() => {
  if (candidatesTimer) clearInterval(candidatesTimer)
})
</script>
