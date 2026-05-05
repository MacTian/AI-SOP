<template>
  <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
    <div class="p-4 border-b flex items-center justify-between">
      <h3 class="font-medium">Camera Feed</h3>
      <div class="flex items-center space-x-2">
        <span class="text-xs text-gray-500">{{ fps }} fps</span>
        <button
          @click="toggleStream"
          class="px-3 py-1 text-sm border rounded-md"
          :class="streaming ? 'border-red-300 text-red-600' : 'border-green-300 text-green-600'"
        >
          {{ streaming ? 'Pause' : 'Resume' }}
        </button>
      </div>
    </div>
    <div class="relative bg-black aspect-video flex items-center justify-center">
      <img
        v-if="streaming"
        ref="videoEl"
        :src="streamUrl"
        class="w-full h-full object-contain"
        @error="onError"
        @load="onFrame"
        alt="Camera stream"
      />
      <div v-else class="text-gray-400 text-sm">Stream paused</div>
      <div
        v-if="connectionError && streaming"
        class="absolute bottom-2 left-2 bg-red-600/80 text-white text-xs px-2 py-1 rounded"
      >
        Camera Disconnected
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const streamUrl = '/video/stream'
const streaming = ref(true)
const connectionError = ref(false)
const fps = ref(0)
const videoEl = ref(null)

let frameCount = 0
let lastTime = Date.now()

function toggleStream() {
  streaming.value = !streaming.value
  connectionError.value = false
}

function onError() {
  connectionError.value = true
}

function onFrame() {
  connectionError.value = false
  frameCount++
  const now = Date.now()
  if (now - lastTime >= 1000) {
    fps.value = frameCount
    frameCount = 0
    lastTime = now
  }
}
</script>
