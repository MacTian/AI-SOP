<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold">Operation History</h2>

    <div class="bg-white rounded-lg shadow-sm border">
      <div class="p-4 border-b">
        <div class="flex items-center justify-between">
          <h3 class="font-medium">Recent Records</h3>
          <button @click="fetchRecords" class="text-sm text-blue-600 hover:underline">
            Refresh
          </button>
        </div>
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
            </tr>
            <tr v-if="records.length === 0">
              <td colspan="5" class="px-4 py-8 text-center text-gray-400">
                No records yet.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const records = ref([])

async function fetchRecords() {
  try {
    const { data } = await axios.get('/api/monitor/records', { params: { limit: 200 } })
    records.value = data.records || []
  } catch {
    records.value = []
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

onMounted(fetchRecords)
</script>
