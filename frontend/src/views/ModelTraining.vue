<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold">YOLO Model Training</h2>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Config Panel -->
      <div class="lg:col-span-1 space-y-4">
        <!-- Training Config -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Training Configuration</h3>
          <div class="space-y-3">
            <div>
              <label class="block text-sm text-gray-600 mb-1">Model</label>
              <select v-model="config.model" class="w-full border rounded px-2 py-1.5 text-sm">
                <option value="yolov8n.pt">YOLOv8n (nano)</option>
                <option value="yolov8s.pt">YOLOv8s (small)</option>
                <option value="yolov8m.pt">YOLOv8m (medium)</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Epochs</label>
              <input v-model.number="config.epochs" type="number" min="1" max="500"
                class="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Batch Size</label>
              <input v-model.number="config.batch" type="number" min="1" max="64"
                class="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Image Size</label>
              <select v-model.number="config.imgsz" class="w-full border rounded px-2 py-1.5 text-sm">
                <option :value="320">320</option>
                <option :value="640">640</option>
                <option :value="1280">1280</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Learning Rate</label>
              <input v-model.number="config.lr" type="number" step="0.001" min="0.0001" max="0.1"
                class="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Device</label>
              <select v-model="config.device" class="w-full border rounded px-2 py-1.5 text-sm">
                <option value="cpu">CPU</option>
                <option value="0">GPU 0</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Dataset Config -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Dataset</h3>
          <div class="space-y-3">
            <div>
              <label class="block text-sm text-gray-600 mb-1">Dataset Name</label>
              <input v-model="config.dataset_name" placeholder="my_dataset"
                class="w-full border rounded px-2 py-1.5 text-sm" />
            </div>
            <div>
              <label class="block text-sm text-gray-600 mb-1">Train/Val Split</label>
              <div class="flex items-center space-x-2">
                <input v-model.number="config.train_ratio" type="number" min="0.5" max="0.95" step="0.05"
                  class="w-20 border rounded px-2 py-1.5 text-sm" />
                <span class="text-xs text-gray-400">train ratio</span>
              </div>
            </div>

            <!-- Upload dataset zip -->
            <div>
              <label class="block text-sm text-gray-600 mb-1">Upload Dataset (ZIP)</label>
              <input
                ref="datasetInput"
                type="file"
                accept=".zip"
                class="hidden"
                @change="uploadDataset"
              />
              <button
                @click="datasetInput.click()"
                class="w-full px-3 py-2 border-2 border-dashed border-gray-300 rounded text-sm text-gray-500 hover:border-blue-400"
              >
                {{ datasetUploaded ? '✓ Dataset uploaded' : '+ Upload ZIP' }}
              </button>
              <p class="text-xs text-gray-400 mt-1">YOLO format: images/ + labels/ + data.yaml</p>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="bg-white rounded-lg shadow-sm border p-4 space-y-2">
          <button
            @click="startTraining"
            :disabled="isTraining || !datasetUploaded"
            class="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
          >
            {{ isTraining ? 'Training...' : 'Start Training' }}
          </button>
          <button
            @click="stopTraining"
            :disabled="!isTraining"
            class="w-full px-4 py-2 border border-red-300 text-red-600 rounded-md hover:bg-red-50 disabled:opacity-50 text-sm"
          >
            Stop Training
          </button>
        </div>
      </div>

      <!-- Training Progress -->
      <div class="lg:col-span-2 space-y-4">
        <!-- Status Card -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-medium">Training Progress</h3>
            <span
              class="px-2 py-0.5 rounded-full text-xs font-medium"
              :class="statusClass"
            >
              {{ statusText }}
            </span>
          </div>

          <!-- Progress Bar -->
          <div class="mb-4">
            <div class="flex justify-between text-sm mb-1">
              <span>Epoch {{ currentEpoch }} / {{ config.epochs }}</span>
              <span>{{ progressPercent }}%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2">
              <div
                class="h-2 rounded-full transition-all duration-500"
                :class="isTraining ? 'bg-green-500 animate-pulse' : 'bg-blue-500'"
                :style="{ width: `${progressPercent}%` }"
              ></div>
            </div>
          </div>

          <!-- Metrics Grid -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-500">Box Loss</p>
              <p class="text-lg font-semibold">{{ formatMetric(metrics.box_loss) }}</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-500">Cls Loss</p>
              <p class="text-lg font-semibold">{{ formatMetric(metrics.cls_loss) }}</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-500">mAP50</p>
              <p class="text-lg font-semibold text-green-600">{{ formatMetric(metrics.map50, true) }}</p>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <p class="text-xs text-gray-500">mAP50-95</p>
              <p class="text-lg font-semibold text-green-600">{{ formatMetric(metrics.map50_95, true) }}</p>
            </div>
          </div>
        </div>

        <!-- Training Chart -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Training Metrics</h3>
          <div class="h-64">
            <canvas ref="chartCanvas"></canvas>
          </div>
        </div>

        <!-- Training Log -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Training Log</h3>
          <div class="bg-gray-900 text-green-400 rounded p-3 h-48 overflow-y-auto font-mono text-xs">
            <div v-for="(line, i) in logs" :key="i" class="leading-relaxed">
              {{ line }}
            </div>
            <div v-if="logs.length === 0" class="text-gray-500">
              Training log will appear here...
            </div>
          </div>
        </div>

        <!-- Results (after training) -->
        <div v-if="trainingResult" class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Training Results</h3>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
            <div class="bg-green-50 rounded-lg p-3">
              <p class="text-xs text-green-600">Final mAP50</p>
              <p class="text-xl font-bold text-green-700">{{ (trainingResult.map50 * 100).toFixed(1) }}%</p>
            </div>
            <div class="bg-blue-50 rounded-lg p-3">
              <p class="text-xs text-blue-600">Final mAP50-95</p>
              <p class="text-xl font-bold text-blue-700">{{ (trainingResult.map50_95 * 100).toFixed(1) }}%</p>
            </div>
            <div class="bg-purple-50 rounded-lg p-3">
              <p class="text-xs text-purple-600">Training Time</p>
              <p class="text-xl font-bold text-purple-700">{{ trainingResult.elapsed }}s</p>
            </div>
          </div>
          <div class="flex space-x-2">
            <button
              @click="downloadModel"
              class="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >Download Model</button>
            <button
              @click="useModel"
              class="px-4 py-2 border border-blue-300 text-blue-600 rounded text-sm hover:bg-blue-50"
            >Use as Active Model</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import http from '../api/http'

// Config
const config = ref({
  model: 'yolov8n.pt',
  epochs: 50,
  batch: 16,
  imgsz: 640,
  lr: 0.01,
  device: 'cpu',
  dataset_name: 'sop_dataset',
  train_ratio: 0.8,
})

// State
const isTraining = ref(false)
const currentEpoch = ref(0)
const datasetUploaded = ref(false)
const datasetInput = ref(null)
const trainingResult = ref(null)
const logs = ref([])
const metrics = ref({
  box_loss: null,
  cls_loss: null,
  map50: null,
  map50_95: null,
})
const epochHistory = ref([])
const chartCanvas = ref(null)
let pollInterval = null
let chartInstance = null

const progressPercent = computed(() => {
  if (config.value.epochs === 0) return 0
  return Math.round((currentEpoch.value / config.value.epochs) * 100)
})

const statusText = computed(() => {
  if (isTraining.value) return 'Training'
  if (trainingResult.value) return 'Completed'
  return 'Idle'
})

const statusClass = computed(() => {
  if (isTraining.value) return 'bg-green-100 text-green-700'
  if (trainingResult.value) return 'bg-blue-100 text-blue-700'
  return 'bg-gray-100 text-gray-600'
})

function formatMetric(val, isPercent = false) {
  if (val === null || val === undefined) return '--'
  return isPercent ? (val * 100).toFixed(1) + '%' : val.toFixed(4)
}

// Dataset upload
async function uploadDataset(e) {
  const file = e.target.files[0]
  if (!file) return
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('dataset_name', config.value.dataset_name)
    await http.post('/api/training/yolo/dataset/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    datasetUploaded.value = true
    logs.value.push(`[INFO] Dataset uploaded: ${file.name}`)
  } catch (err) {
    alert('Upload failed: ' + (err.response?.data?.error || err.message))
  }
  e.target.value = ''
}

// Training control
async function startTraining() {
  isTraining.value = true
  currentEpoch.value = 0
  trainingResult.value = null
  epochHistory.value = []
  logs.value = []
  metrics.value = { box_loss: null, cls_loss: null, map50: null, map50_95: null }

  try {
    await http.post('/api/training/yolo/start', config.value)
    logs.value.push('[INFO] Training started')
    logs.value.push(`[INFO] Model: ${config.value.model}, Epochs: ${config.value.epochs}`)
    logs.value.push(`[INFO] Downloading pre-trained model from China mirror...`)
    startPolling()
  } catch (err) {
    isTraining.value = false
    logs.value.push('[ERROR] ' + (err.response?.data?.error || err.message))
  }
}

async function stopTraining() {
  try {
    await http.post('/api/training/yolo/stop')
    logs.value.push('[INFO] Training stopped by user')
  } catch (err) {
    console.error('Stop failed:', err)
  }
  isTraining.value = false
  stopPolling()
}

function startPolling() {
  stopPolling()
  pollInterval = setInterval(pollStatus, 3000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

async function pollStatus() {
  try {
    const { data } = await http.get('/api/training/yolo/status')
    currentEpoch.value = data.current_epoch || 0

    if (data.latest_metrics) {
      metrics.value = { ...metrics.value, ...data.latest_metrics }
      epochHistory.value.push({ ...data.latest_metrics, epoch: currentEpoch.value })
      updateChart()
    }

    if (data.logs && data.logs.length > 0) {
      logs.value.push(...data.logs)
      // Auto-scroll
      nextTick(() => {
        const el = document.querySelector('.bg-gray-900')
        if (el) el.scrollTop = el.scrollHeight
      })
    }

    if (data.status === 'completed' || data.status === 'stopped' || data.status === 'error') {
      isTraining.value = false
      stopPolling()
      if (data.result) {
        trainingResult.value = data.result
      }
    }
  } catch (err) {
    console.error('Poll error:', err)
  }
}

// Chart
function updateChart() {
  const cvs = chartCanvas.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  const parent = cvs.parentElement
  cvs.width = parent.clientWidth
  cvs.height = parent.clientHeight

  const w = cvs.width
  const h = cvs.height
  const padding = 40
  const history = epochHistory.value

  ctx.clearRect(0, 0, w, h)

  if (history.length < 2) {
    ctx.fillStyle = '#9CA3AF'
    ctx.font = '14px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText('Training metrics will appear here...', w / 2, h / 2)
    return
  }

  const maxEpoch = Math.max(...history.map(e => e.epoch), 1)
  const xScale = (w - padding * 2) / maxEpoch

  function drawLine(key, color, label) {
    const values = history.map(e => e[key]).filter(v => v !== null && v !== undefined)
    if (values.length < 2) return
    const maxVal = Math.max(...values) * 1.1 || 1
    const minVal = Math.min(...values) * 0.9

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath()
    history.forEach((e, i) => {
      const val = e[key]
      if (val === null || val === undefined) return
      const x = padding + e.epoch * xScale
      const y = h - padding - ((val - minVal) / (maxVal - minVal)) * (h - padding * 2)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Label
    const lastVal = values[values.length - 1]
    ctx.fillStyle = color
    ctx.font = '12px sans-serif'
    ctx.textAlign = 'left'
    ctx.fillText(`${label}: ${lastVal?.toFixed(4) || '--'}`, padding + 5, h - padding - ((lastVal - minVal) / (maxVal - minVal)) * (h - padding * 2) - 5)
  }

  drawLine('box_loss', '#EF4444', 'Box Loss')
  drawLine('cls_loss', '#3B82F6', 'Cls Loss')
  drawLine('map50', '#10B981', 'mAP50')

  // Axes
  ctx.strokeStyle = '#E5E7EB'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(padding, padding)
  ctx.lineTo(padding, h - padding)
  ctx.lineTo(w - padding, h - padding)
  ctx.stroke()
}

function downloadModel() {
  window.open('/api/training/yolo/download', '_blank')
}

async function useModel() {
  try {
    await http.post('/api/training/yolo/use')
    alert('Model set as active!')
  } catch (err) {
    alert('Failed: ' + (err.response?.data?.error || err.message))
  }
}

onMounted(() => {
  window.addEventListener('resize', updateChart)
  // Check status in case training is already running
  pollStatus()
})

onUnmounted(() => {
  stopPolling()
  window.removeEventListener('resize', updateChart)
})
</script>
