<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">Operation History</h2>
      <div class="flex items-center space-x-3">
        <select v-model="selectedSop" class="text-sm border rounded px-2 py-1">
          <option value="">All SOPs</option>
          <option v-for="sop in store.sopList" :key="sop.sop_id" :value="sop.sop_id">
            {{ sop.name }}
          </option>
        </select>
        <label class="flex items-center space-x-1 text-sm text-gray-600">
          <input type="checkbox" v-model="autoRefresh" class="rounded" />
          <span>Auto-refresh</span>
        </label>
        <button @click="fetchRecords" class="text-sm text-blue-600 hover:underline">
          Refresh
        </button>
        <button @click="exportCsv" class="text-sm text-green-600 hover:underline">
          Export CSV
        </button>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow-sm border">
      <div class="p-4 border-b">
        <h3 class="font-medium">
          Records
          <span class="text-gray-400 font-normal text-sm">({{ records.length }})</span>
        </h3>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left font-medium text-gray-600">Time</th>
              <th class="px-4 py-2 text-left font-medium text-gray-600">SOP</th>
              <th class="px-4 py-2 text-left font-medium text-gray-600">Step</th>
              <th class="px-4 py-2 text-left font-medium text-gray-600">Status</th>
              <th class="px-4 py-2 text-left font-medium text-gray-600">Confidence</th>
              <th class="px-4 py-2 text-left font-medium text-gray-600">Screenshot</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="r in records" :key="r.id" class="hover:bg-gray-50">
              <td class="px-4 py-2 text-gray-500">{{ formatTime(r.timestamp) }}</td>
              <td class="px-4 py-2">{{ r.sop_id }}</td>
              <td class="px-4 py-2">{{ r.step_name }}</td>
              <td class="px-4 py-2">
                <span
                  class="px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="statusClass(r.status)"
                >
                  {{ r.status }}
                </span>
              </td>
              <td class="px-4 py-2">{{ (r.confidence * 100).toFixed(1) }}%</td>
              <td class="px-4 py-2">
                <button
                  v-if="r.screenshot_path"
                  @click="previewScreenshot(r.screenshot_path)"
                  class="text-blue-600 hover:underline text-xs"
                >
                  View
                </button>
                <span v-else class="text-gray-300 text-xs">-</span>
              </td>
            </tr>
            <tr v-if="records.length === 0">
              <td colspan="6" class="px-4 py-8 text-center text-gray-400">
                No records yet.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Screenshot preview modal -->
    <div
      v-if="previewUrl"
      class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50"
      @click.self="previewUrl = null"
    >
      <div class="relative max-w-4xl max-h-[90vh]">
        <button
          @click="previewUrl = null"
          class="absolute -top-3 -right-3 bg-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg text-gray-600 hover:text-gray-900 z-10"
        >
          &times;
        </button>
        <img :src="previewUrl" class="max-w-full max-h-[85vh] rounded-lg shadow-2xl" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import http from '../api/http'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()
const records = ref([])
const selectedSop = ref('')
const autoRefresh = ref(true)
const previewUrl = ref(null)
let refreshTimer = null

async function fetchRecords() {
  try {
    const params = { limit: 200 }
    if (selectedSop.value) params.sop_id = selectedSop.value
    const { data } = await http.get('/api/monitor/records', { params })
    records.value = data.records || []
  } catch {
    records.value = []
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (autoRefresh.value) {
    refreshTimer = setInterval(fetchRecords, 5000)
  }
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function formatTime(ts) {
  if (!ts) return '-'
  return new Date(ts).toLocaleString()
}

function statusClass(status) {
  const map = {
    detected: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    skipped: 'bg-yellow-100 text-yellow-700',
    error: 'bg-red-100 text-red-700',
    timeout: 'bg-orange-100 text-orange-700',
  }
  return map[status] || 'bg-gray-100 text-gray-700'
}

function previewScreenshot(path) {
  // path is absolute like /home/mac/sop-monitor/screenshots/xxx.jpg
  // Extract filename for the API endpoint
  const filename = path.split('/').pop()
  previewUrl.value = `/video/screenshots/${filename}`
}

function exportCsv() {
  const params = new URLSearchParams()
  if (selectedSop.value) params.set('sop_id', selectedSop.value)
  const url = `/api/monitor/records/export${params.toString() ? '?' + params : ''}`
  window.open(url, '_blank')
}

watch(selectedSop, fetchRecords)
watch(autoRefresh, (val) => val ? startAutoRefresh() : stopAutoRefresh())

onMounted(() => {
  store.fetchSopList()
  fetchRecords()
  startAutoRefresh()
})
onUnmounted(stopAutoRefresh)
</script>
