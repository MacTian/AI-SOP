<template>
  <div class="bg-white rounded-lg shadow-sm border">
    <div class="p-4 border-b flex items-center justify-between">
      <h3 class="font-medium">SOP Progress</h3>
      <div class="flex items-center space-x-2">
        <select
          v-model="selectedSop"
          class="text-xs border border-gray-300 rounded px-2 py-1 max-w-[9rem]"
          :disabled="starting"
        >
          <option value="">{{ availableSops.length ? 'Select SOP…' : 'No SOP' }}</option>
          <option v-for="s in availableSops" :key="s.sop_id" :value="s.sop_id">
            {{ s.name || s.sop_id }}
          </option>
        </select>
        <button
          @click="startSelected"
          :disabled="!selectedSop || starting"
          class="px-2 py-1 text-xs rounded border border-green-300 text-green-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-green-50"
        >
          {{ starting ? 'Starting…' : 'Start' }}
        </button>
      </div>
    </div>
    <div class="p-4">
      <div v-if="error" class="mb-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">
        {{ error }}
      </div>
      <div v-if="store.activeSops.length === 0" class="text-center text-gray-400 py-4">
        No active SOP
      </div>
      <div v-for="sop in store.activeSops" :key="sop.sop_id" class="mb-4 last:mb-0">
        <div class="flex items-center justify-between mb-1">
          <span class="text-sm font-medium">{{ sop.sop_name || sop.sop_id }}</span>
          <div class="flex items-center space-x-2">
            <span class="text-xs text-gray-500">{{ Math.round(sop.progress * 100) }}%</span>
            <button
              @click="stopSop(sop.sop_id)"
              class="text-xs text-gray-400 hover:text-red-600"
              title="Stop this SOP"
            >Stop</button>
          </div>
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
import { ref, computed } from 'vue'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()
const selectedSop = ref('')
const starting = ref(false)
const error = ref('')

// SOPs that are defined but not yet running
const availableSops = computed(() => {
  const activeIds = new Set(store.activeSops.map(s => s.sop_id))
  return (store.sopList || []).filter(s => !activeIds.has(s.sop_id))
})

async function startSelected() {
  if (!selectedSop.value) return
  starting.value = true
  error.value = ''
  try {
    await store.startSop(selectedSop.value)
    selectedSop.value = ''
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  } finally {
    starting.value = false
  }
}

async function stopSop(sopId) {
  error.value = ''
  try {
    await store.stopSop(sopId)
  } catch (e) {
    error.value = e.response?.data?.detail || e.message
  }
}

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
