<template>
  <div class="fixed top-4 right-4 z-50 space-y-2 pointer-events-none">
    <transition-group name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="pointer-events-auto max-w-sm w-full bg-white rounded-lg shadow-lg border-l-4 p-4 flex items-start space-x-3"
        :class="borderColor(toast.level)"
      >
        <span
          class="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
          :class="dotColor(toast.level)"
        ></span>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-gray-900">{{ toast.message }}</div>
          <div class="text-xs text-gray-500 mt-0.5">{{ toast.step_name }}</div>
        </div>
        <button
          @click="dismiss(toast.id)"
          class="text-gray-400 hover:text-gray-600 flex-shrink-0"
        >
          &times;
        </button>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()
const toasts = ref([])
let toastId = 0

// Audio context for alert sounds
let audioCtx = null

function playSound(level) {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = audioCtx.createOscillator()
    const gain = audioCtx.createGain()
    osc.connect(gain)
    gain.connect(audioCtx.destination)

    // Different tones for different levels
    const freqs = { info: 440, warning: 523, error: 659, critical: 880 }
    osc.frequency.value = freqs[level] || 440
    osc.type = level === 'critical' ? 'sawtooth' : 'sine'
    gain.gain.value = level === 'critical' ? 0.3 : 0.15

    osc.start()
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.5)
    osc.stop(audioCtx.currentTime + 0.5)
  } catch { /* ignore audio errors */ }
}

function borderColor(level) {
  const map = {
    info: 'border-l-blue-400',
    warning: 'border-l-yellow-400',
    error: 'border-l-red-400',
    critical: 'border-l-red-600',
  }
  return map[level] || 'border-l-gray-400'
}

function dotColor(level) {
  const map = {
    info: 'bg-blue-400',
    warning: 'bg-yellow-400',
    error: 'bg-red-400',
    critical: 'bg-red-600',
  }
  return map[level] || 'bg-gray-400'
}

function dismiss(id) {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

// Watch for new alerts from the store
watch(
  () => store.alerts,
  (newAlerts, oldAlerts) => {
    if (!newAlerts.length) return
    const latest = newAlerts[0]
    if (latest && !latest.acknowledged) {
      // Check if this is a new alert (not in old list)
      const isNew = !oldAlerts?.some(a => a.alert_id === latest.alert_id)
      if (isNew) {
        const id = ++toastId
        toasts.value.push({ id, ...latest })
        playSound(latest.level)
        // Auto dismiss after 6 seconds
        setTimeout(() => dismiss(id), 6000)
      }
    }
  },
  { deep: true }
)
</script>

<style scoped>
.toast-enter-active {
  transition: all 0.3s ease-out;
}
.toast-leave-active {
  transition: all 0.2s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(100px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100px);
}
</style>
