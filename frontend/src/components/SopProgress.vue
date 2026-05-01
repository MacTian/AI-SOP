<template>
  <div class="bg-white rounded-lg shadow-sm border">
    <div class="p-4 border-b">
      <h3 class="font-medium">SOP Progress</h3>
    </div>
    <div class="p-4">
      <div v-if="store.activeSops.length === 0" class="text-center text-gray-400 py-4">
        No active SOP
      </div>
      <div v-for="sop in store.activeSops" :key="sop.sop_id" class="mb-4 last:mb-0">
        <div class="flex items-center justify-between mb-1">
          <span class="text-sm font-medium">{{ sop.sop_name || sop.sop_id }}</span>
          <span class="text-xs text-gray-500">{{ Math.round(sop.progress * 100) }}%</span>
        </div>
        <!-- Progress bar -->
        <div class="w-full bg-gray-200 rounded-full h-2 mb-2">
          <div
            class="bg-blue-600 h-2 rounded-full transition-all duration-300"
            :style="{ width: `${sop.progress * 100}%` }"
          ></div>
        </div>
        <!-- Step list -->
        <div class="space-y-1">
          <div
            v-for="(status, stepId) in sop.step_statuses"
            :key="stepId"
            class="flex items-center space-x-2 text-xs"
          >
            <span
              class="w-2 h-2 rounded-full"
              :class="stepColor(status)"
            ></span>
            <span class="text-gray-600">{{ stepId }}</span>
            <span class="text-gray-400 ml-auto">{{ status }}</span>
          </div>
        </div>
        <div class="mt-2 text-xs text-gray-400">
          Elapsed: {{ formatTime(sop.elapsed_time) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()

function stepColor(status) {
  const map = {
    pending: 'bg-gray-300',
    active: 'bg-blue-500 animate-pulse',
    completed: 'bg-green-500',
    skipped: 'bg-yellow-400',
    timeout: 'bg-orange-500',
    error: 'bg-red-500',
  }
  return map[status] || 'bg-gray-300'
}

function formatTime(seconds) {
  if (!seconds) return '0s'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}
</script>
