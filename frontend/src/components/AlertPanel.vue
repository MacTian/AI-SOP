<template>
  <div class="bg-white rounded-lg shadow-sm border">
    <div class="p-4 border-b flex items-center justify-between">
      <h3 class="font-medium">Alerts</h3>
      <span v-if="store.alerts.length > 0" class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full">
        {{ store.alerts.length }}
      </span>
    </div>
    <div class="max-h-64 overflow-y-auto">
      <div
        v-for="alert in store.alerts"
        :key="alert.alert_id"
        class="p-3 border-b last:border-0 hover:bg-gray-50"
      >
        <div class="flex items-start space-x-2">
          <span
            class="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
            :class="levelColor(alert.level)"
          ></span>
          <div class="flex-1 min-w-0">
            <div class="text-sm">{{ alert.message }}</div>
            <div class="text-xs text-gray-400 mt-0.5">
              {{ formatTime(alert.timestamp) }}
            </div>
          </div>
          <button
            v-if="!alert.acknowledged"
            @click="acknowledge(alert.alert_id)"
            class="text-xs text-blue-600 hover:underline flex-shrink-0"
          >
            ACK
          </button>
        </div>
      </div>
      <div v-if="store.alerts.length === 0" class="p-6 text-center text-gray-400 text-sm">
        No alerts
      </div>
    </div>
  </div>
</template>

<script setup>
import http from '../api/http'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()

function levelColor(level) {
  const map = {
    info: 'bg-blue-400',
    warning: 'bg-yellow-400',
    error: 'bg-red-400',
    critical: 'bg-red-600',
  }
  return map[level] || 'bg-gray-400'
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString()
}

async function acknowledge(alertId) {
  await http.post(`/api/monitor/alerts/${alertId}/acknowledge`)
  const alert = store.alerts.find(a => a.alert_id === alertId)
  if (alert) alert.acknowledged = true
}
</script>
