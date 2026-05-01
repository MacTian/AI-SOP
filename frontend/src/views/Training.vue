<template>
  <div class="space-y-6">
    <h2 class="text-xl font-semibold">SOP Training</h2>

    <!-- Training Controls -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Video Preview + Controls -->
      <div class="lg:col-span-2 space-y-4">
        <!-- Video Preview -->
        <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
          <div class="p-4 border-b flex items-center justify-between">
            <h3 class="font-medium">Camera Preview</h3>
            <div class="flex items-center space-x-2">
              <span
                v-if="trainingStatus.status === 'recording'"
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700"
              >
                <span class="w-2 h-2 bg-red-500 rounded-full mr-1 animate-pulse"></span>
                REC {{ formatDuration(timer) }}
              </span>
              <span
                v-else-if="trainingStatus.status === 'ready'"
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700"
              >
                Ready
              </span>
              <span
                v-else
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600"
              >
                Idle
              </span>
            </div>
          </div>
          <div class="relative bg-black aspect-video flex items-center justify-center">
            <img
              ref="videoEl"
              :src="streamUrl"
              class="w-full h-full object-contain"
              alt="Camera preview"
            />
          </div>
        </div>

        <!-- Controls -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <div class="flex items-center space-x-4">
            <!-- SOP Name Input -->
            <div class="flex-1" v-if="trainingStatus.status === 'idle'">
              <input
                v-model="sopName"
                placeholder="SOP Name (e.g. PCB Assembly Process)"
                class="w-full border rounded-md px-3 py-2 text-sm"
              />
            </div>

            <!-- Start Button -->
            <button
              v-if="trainingStatus.status === 'idle'"
              @click="startTraining"
              :disabled="!sopName.trim()"
              class="px-6 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              Start Training
            </button>

            <!-- Stop Button -->
            <button
              v-if="trainingStatus.status === 'recording'"
              @click="stopTraining"
              class="px-6 py-2 bg-gray-700 text-white rounded-md hover:bg-gray-800 text-sm font-medium"
            >
              Stop Training
            </button>

            <!-- Reset Button -->
            <button
              v-if="trainingStatus.status === 'ready'"
              @click="resetTraining"
              class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 text-sm"
            >
              New Training
            </button>
          </div>
        </div>
      </div>

      <!-- Right Sidebar: Training Info -->
      <div class="space-y-4">
        <!-- Training Status Card -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Training Status</h3>
          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-gray-500">Status</span>
              <span class="font-medium">{{ trainingStatus.status || 'idle' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Frames</span>
              <span class="font-medium">{{ trainingStatus.frame_count || 0 }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Duration</span>
              <span class="font-medium">{{ formatDuration(trainingStatus.duration || 0) }}</span>
            </div>
            <div v-if="analysisResult" class="flex justify-between">
              <span class="text-gray-500">Steps Found</span>
              <span class="font-medium text-blue-600">{{ analysisResult.steps_found }}</span>
            </div>
          </div>
        </div>

        <!-- Detected Steps Summary -->
        <div v-if="steps.length > 0" class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Identified Steps</h3>
          <div class="space-y-2">
            <div
              v-for="(step, i) in steps"
              :key="step.step_id"
              class="flex items-center space-x-2 text-sm"
            >
              <span class="w-5 h-5 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium">
                {{ i + 1 }}
              </span>
              <span class="flex-1 truncate">{{ step.name }}</span>
              <span class="text-xs text-gray-400">{{ step.expected_objects?.join(', ') }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Step Editor (shown after analysis) -->
    <StepEditor
      v-if="steps.length > 0"
      :steps="steps"
      @update="updateStep"
      @delete="deleteStep"
      @reorder="reorderSteps"
      @save="showSaveDialog = true"
    />

    <!-- LSTM Model Training Section -->
    <div class="bg-white rounded-lg shadow-sm border p-6">
      <h3 class="font-medium mb-4">LSTM Action Classifier Training</h3>
      <p class="text-sm text-gray-500 mb-4">
        Train an LSTM model for temporal action recognition. Uses synthetic data to learn step patterns
        from YOLO detections + hand keypoint features.
      </p>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Number of Classes</label>
          <input v-model.number="lstmForm.num_classes" type="number" min="2" max="20"
            class="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Epochs</label>
          <input v-model.number="lstmForm.epochs" type="number" min="5" max="200"
            class="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Hidden Size</label>
          <input v-model.number="lstmForm.hidden_size" type="number" min="32" max="512"
            class="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <button
          @click="trainLstm"
          :disabled="lstmStatus.is_training"
          class="px-6 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
        >
          {{ lstmStatus.is_training ? 'Training...' : 'Train LSTM Model' }}
        </button>

        <span v-if="lstmResult" class="text-sm" :class="lstmResult.status === 'completed' ? 'text-green-600' : 'text-red-600'">
          {{ lstmResult.status === 'completed'
            ? `Done! Accuracy: ${(lstmResult.final_accuracy * 100).toFixed(1)}% (${lstmResult.elapsed_seconds}s)`
            : lstmResult.error || 'Failed' }}
        </span>
      </div>

      <!-- Training Progress -->
      <div v-if="lstmStatus.history && lstmStatus.history.length > 0" class="mt-4">
        <div class="flex items-center space-x-2 mb-2">
          <span class="text-xs text-gray-500">Training Progress</span>
          <div class="flex-1 bg-gray-200 rounded-full h-1.5">
            <div
              class="bg-purple-600 h-1.5 rounded-full transition-all"
              :style="{ width: `${(lstmStatus.history.length / lstmForm.epochs) * 100}%` }"
            ></div>
          </div>
          <span class="text-xs text-gray-500">{{ lstmStatus.history.length }}/{{ lstmForm.epochs }}</span>
        </div>
        <div class="text-xs text-gray-500">
          Last: loss={{ lstmStatus.history[lstmStatus.history.length - 1]?.loss }},
          acc={{ (lstmStatus.history[lstmStatus.history.length - 1]?.accuracy * 100)?.toFixed(1) }}%
        </div>
      </div>
    </div>

    <!-- Save Dialog -->
    <div v-if="showSaveDialog" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <h3 class="text-lg font-medium mb-4">Save as SOP</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">SOP ID</label>
            <input v-model="saveForm.sop_id" class="w-full border rounded-md px-3 py-2 text-sm" placeholder="my_sop" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input v-model="saveForm.name" class="w-full border rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea v-model="saveForm.description" class="w-full border rounded-md px-3 py-2 text-sm" rows="2"></textarea>
          </div>
        </div>
        <div class="flex justify-end space-x-2 mt-4">
          <button @click="showSaveDialog = false" class="px-4 py-2 border rounded-md text-sm">Cancel</button>
          <button @click="saveSop" class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import StepEditor from '../components/StepEditor.vue'

const router = useRouter()
const streamUrl = '/video/stream'
const videoEl = ref(null)

const sopName = ref('')
const trainingStatus = ref({ status: 'idle', frame_count: 0, duration: 0 })
const analysisResult = ref(null)
const steps = ref([])
const showSaveDialog = ref(false)
const saveForm = ref({ sop_id: '', name: '', description: '' })

// LSTM training
const lstmForm = ref({ num_classes: 5, epochs: 30, hidden_size: 128 })
const lstmStatus = ref({ is_training: false, history: [] })
const lstmResult = ref(null)

const timer = ref(0)
let timerInterval = null
let statusInterval = null

async function startTraining() {
  if (!sopName.value.trim()) return
  try {
    await http.post('/api/training/start', { sop_name: sopName.value })
    trainingStatus.value = { status: 'recording', frame_count: 0, duration: 0 }
    timer.value = 0
    timerInterval = setInterval(() => { timer.value++ }, 1000)
    startStatusPolling()
  } catch (e) {
    console.error('Start training failed:', e)
  }
}

async function stopTraining() {
  try {
    const { data } = await http.post('/api/training/stop')
    if (timerInterval) clearInterval(timerInterval)
    analysisResult.value = data
    trainingStatus.value = { ...trainingStatus.value, status: 'ready' }
    await fetchResult()
    await fetchStatus()
  } catch (e) {
    console.error('Stop training failed:', e)
  }
}

async function resetTraining() {
  try {
    await http.post('/api/training/reset')
    trainingStatus.value = { status: 'idle', frame_count: 0, duration: 0 }
    steps.value = []
    analysisResult.value = null
    sopName.value = ''
  } catch (e) {
    console.error('Reset failed:', e)
  }
}

async function fetchStatus() {
  try {
    const { data } = await http.get('/api/training/status')
    trainingStatus.value = data
  } catch {}
}

async function fetchResult() {
  try {
    const { data } = await http.get('/api/training/result')
    steps.value = data.steps || []
    saveForm.value.name = sopName.value
    saveForm.value.sop_id = sopName.value.toLowerCase().replace(/\s+/g, '_')
  } catch {}
}

async function updateStep(stepId, updates) {
  try {
    await http.put(`/api/training/step/${stepId}`, updates)
    await fetchResult()
  } catch (e) {
    console.error('Update step failed:', e)
  }
}

async function deleteStep(stepId) {
  try {
    await http.delete(`/api/training/step/${stepId}`)
    await fetchResult()
  } catch (e) {
    console.error('Delete step failed:', e)
  }
}

async function reorderSteps(orderedIds) {
  try {
    await http.post('/api/training/step/reorder', orderedIds)
    await fetchResult()
  } catch (e) {
    console.error('Reorder failed:', e)
  }
}

async function saveSop() {
  try {
    await http.post('/api/training/save', saveForm.value)
    showSaveDialog.value = false
    steps.value = []
    trainingStatus.value = { status: 'idle', frame_count: 0, duration: 0 }
    sopName.value = ''
    router.push('/sop-editor')
  } catch (e) {
    console.error('Save failed:', e)
  }
}

function startStatusPolling() {
  statusInterval = setInterval(fetchStatus, 2000)
}

async function trainLstm() {
  lstmResult.value = null
  lstmStatus.value = { is_training: true, history: [] }
  try {
    const { data } = await http.post('/api/training/lstm/train', lstmForm.value)
    lstmResult.value = data
    lstmStatus.value = { is_training: false, history: data.history || [] }
  } catch (e) {
    lstmResult.value = { status: 'failed', error: e.response?.data?.error || e.message }
    lstmStatus.value = { is_training: false, history: [] }
  }
}

function formatDuration(seconds) {
  if (!seconds) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

onMounted(fetchStatus)
onUnmounted(() => {
  if (timerInterval) clearInterval(timerInterval)
  if (statusInterval) clearInterval(statusInterval)
})
</script>
