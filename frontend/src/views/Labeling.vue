<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">YOLO Data Labeling</h2>
      <div class="flex items-center space-x-2">
        <span class="text-sm text-gray-500">{{ images.length }} images</span>
        <span class="text-sm text-gray-400">|</span>
        <span class="text-sm text-gray-500">{{ totalLabels }} labels</span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
      <!-- Left: Image List -->
      <div class="lg:col-span-1 space-y-4">
        <!-- Upload -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Upload Images</h3>
          <input
            ref="fileInput"
            type="file"
            multiple
            accept="image/*"
            class="hidden"
            @change="handleFileUpload"
          />
          <button
            @click="fileInput.click()"
            class="w-full px-4 py-2 border-2 border-dashed border-gray-300 rounded-md text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600"
          >
            + Select Images
          </button>
          <p class="text-xs text-gray-400 mt-2">Supports JPG, PNG, BMP</p>
        </div>

        <!-- Image List -->
        <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
          <div class="p-3 border-b bg-gray-50">
            <h3 class="font-medium text-sm">Image List</h3>
          </div>
          <div class="max-h-96 overflow-y-auto divide-y">
            <div
              v-for="(img, i) in images"
              :key="img.name"
              @click="selectImage(i)"
              class="p-2 cursor-pointer flex items-center space-x-2 text-sm"
              :class="currentIndex === i ? 'bg-blue-50' : 'hover:bg-gray-50'"
            >
              <img
                :src="img.url"
                class="w-10 h-10 object-cover rounded"
              />
              <div class="flex-1 min-w-0">
                <p class="truncate">{{ img.name }}</p>
                <p class="text-xs text-gray-400">{{ (img.labels || []).length }} labels</p>
              </div>
              <button
                @click.stop="removeImage(i)"
                class="text-gray-400 hover:text-red-500"
              >×</button>
            </div>
            <div v-if="images.length === 0" class="p-4 text-center text-sm text-gray-400">
              No images uploaded
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="bg-white rounded-lg shadow-sm border p-4 space-y-2">
          <button
            @click="runAutoLabel"
            :disabled="images.length === 0 || isAutoLabeling"
            class="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {{ isAutoLabeling ? 'Labeling...' : 'Auto Label (YOLO)' }}
          </button>
          <button
            @click="exportLabels"
            :disabled="totalLabels === 0"
            class="w-full px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 text-sm"
          >
            Export YOLO Format
          </button>
          <button
            @click="clearAll"
            class="w-full px-4 py-2 border border-red-200 text-red-600 rounded-md hover:bg-red-50 text-sm"
          >
            Clear All
          </button>
        </div>
      </div>

      <!-- Center: Canvas -->
      <div class="lg:col-span-2 space-y-4">
        <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
          <div class="p-3 border-b flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <h3 class="font-medium text-sm">Labeling Canvas</h3>
              <span v-if="currentImage" class="text-xs text-gray-400">
                {{ currentImage.name }}
              </span>
            </div>
            <div class="flex items-center space-x-2">
              <select
                v-model="selectedClass"
                class="text-sm border rounded px-2 py-1"
              >
                <option v-for="cls in classes" :key="cls" :value="cls">{{ cls }}</option>
              </select>
              <button
                @click="deleteSelectedLabel"
                :disabled="selectedLabelIndex === null"
                class="px-2 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-50"
              >Delete</button>
            </div>
          </div>
          <div class="relative bg-gray-900 flex items-center justify-center" style="min-height: 480px;">
            <canvas
              ref="canvas"
              @mousedown="onMouseDown"
              @mousemove="onMouseMove"
              @mouseup="onMouseUp"
              @mouseleave="onMouseUp"
              class="max-w-full max-h-[480px] cursor-crosshair"
            />
            <div v-if="!currentImage" class="absolute inset-0 flex items-center justify-center text-gray-500">
              <div class="text-center">
                <p class="text-lg mb-2">No image selected</p>
                <p class="text-sm">Upload images to start labeling</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Navigation -->
        <div class="flex items-center justify-between bg-white rounded-lg shadow-sm border p-3">
          <button
            @click="prevImage"
            :disabled="currentIndex <= 0"
            class="px-3 py-1 border rounded text-sm disabled:opacity-50"
          >← Prev</button>
          <span class="text-sm text-gray-600">
            {{ images.length > 0 ? currentIndex + 1 : 0 }} / {{ images.length }}
          </span>
          <button
            @click="nextImage"
            :disabled="currentIndex >= images.length - 1"
            class="px-3 py-1 border rounded text-sm disabled:opacity-50"
          >Next →</button>
        </div>
      </div>

      <!-- Right: Labels & Classes -->
      <div class="lg:col-span-1 space-y-4">
        <!-- Class Manager -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Classes</h3>
          <div class="flex space-x-2 mb-3">
            <input
              v-model="newClass"
              placeholder="Add class..."
              class="flex-1 border rounded px-2 py-1 text-sm"
              @keyup.enter="addClass"
            />
            <button
              @click="addClass"
              class="px-3 py-1 bg-gray-100 rounded text-sm hover:bg-gray-200"
            >+</button>
          </div>
          <div class="space-y-1 max-h-40 overflow-y-auto">
            <div
              v-for="(cls, i) in classes"
              :key="cls"
              class="flex items-center justify-between p-1.5 rounded text-sm cursor-pointer"
              :class="selectedClass === cls ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'"
              @click="selectedClass = cls"
            >
              <div class="flex items-center space-x-2">
                <span
                  class="w-3 h-3 rounded"
                  :style="{ backgroundColor: classColors[i % classColors.length] }"
                ></span>
                <span>{{ cls }}</span>
              </div>
              <button
                @click.stop="removeClass(i)"
                class="text-gray-400 hover:text-red-500 text-xs"
                v-if="i > 0"
              >×</button>
            </div>
          </div>
        </div>

        <!-- Current Labels -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-3">Current Labels</h3>
          <div v-if="currentImage" class="space-y-1 max-h-60 overflow-y-auto">
            <div
              v-for="(label, i) in currentImage.labels || []"
              :key="i"
              @click="selectedLabelIndex = i"
              class="flex items-center space-x-2 p-1.5 rounded text-xs cursor-pointer"
              :class="selectedLabelIndex === i ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50'"
            >
              <span
                class="w-2.5 h-2.5 rounded"
                :style="{ backgroundColor: classColors[classes.indexOf(label.cls) % classColors.length] }"
              ></span>
              <span class="flex-1">{{ label.cls }}</span>
              <span class="text-gray-400">{{ (label.conf * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="!currentImage.labels || currentImage.labels.length === 0" class="text-sm text-gray-400 text-center py-2">
              No labels yet
            </div>
          </div>
          <div v-else class="text-sm text-gray-400 text-center py-2">
            Select an image
          </div>
        </div>

        <!-- Import/Export Classes -->
        <div class="bg-white rounded-lg shadow-sm border p-4">
          <h3 class="font-medium mb-2 text-sm">Classes Config</h3>
          <textarea
            v-model="classesYaml"
            class="w-full border rounded px-2 py-1 text-xs font-mono"
            rows="4"
            placeholder="class1&#10;class2&#10;class3"
          ></textarea>
          <button
            @click="importClasses"
            class="mt-2 w-full px-3 py-1 border rounded text-xs hover:bg-gray-50"
          >Import Classes</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import http from '../api/http'

// State
const images = ref([])
const currentIndex = ref(-1)
const classes = ref(['board', 'hand', 'tool', 'solder', 'component'])
const newClass = ref('')
const selectedClass = ref('board')
const selectedLabelIndex = ref(null)
const isAutoLabeling = ref(false)
const classesYaml = ref('')
const fileInput = ref(null)

// Canvas
const canvas = ref(null)
const isDrawing = ref(false)
const drawStart = ref({ x: 0, y: 0 })
const drawEnd = ref({ x: 0, y: 0 })
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })

// Image cache for loaded images
const loadedImages = new Map()

// Colors for classes
const classColors = [
  '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
  '#EC4899', '#06B6D4', '#F97316', '#84CC16', '#6366F1',
]

const currentImage = computed(() => images.value[currentIndex.value] || null)
const totalLabels = computed(() =>
  images.value.reduce((sum, img) => sum + (img.labels?.length || 0), 0)
)

// File upload
function handleFileUpload(e) {
  const files = Array.from(e.target.files)
  files.forEach(file => {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const url = ev.target.result
      images.value.push({
        name: file.name,
        url,
        labels: [],
        file,
      })
      if (currentIndex.value < 0) currentIndex.value = 0
    }
    reader.readAsDataURL(file)
  })
  e.target.value = ''
}

function removeImage(i) {
  images.value.splice(i, 1)
  if (currentIndex.value >= images.value.length) {
    currentIndex.value = images.value.length - 1
  }
}

function selectImage(i) {
  currentIndex.value = i
}

function prevImage() {
  if (currentIndex.value > 0) currentIndex.value--
}

function nextImage() {
  if (currentIndex.value < images.value.length - 1) currentIndex.value++
}

// Classes
function addClass() {
  const cls = newClass.value.trim()
  if (cls && !classes.value.includes(cls)) {
    classes.value.push(cls)
    selectedClass.value = cls
    newClass.value = ''
  }
}

function removeClass(i) {
  const removed = classes.value.splice(i, 1)[0]
  if (selectedClass.value === removed) {
    selectedClass.value = classes.value[0] || ''
  }
}

function importClasses() {
  const lines = classesYaml.value.split('\n').map(l => l.trim()).filter(l => l)
  lines.forEach(cls => {
    if (!classes.value.includes(cls)) {
      classes.value.push(cls)
    }
  })
  classesYaml.value = ''
}

// Canvas drawing
function getImageCoords(e) {
  const rect = canvas.value.getBoundingClientRect()
  const x = (e.clientX - rect.left) / scale.value
  const y = (e.clientY - rect.top) / scale.value
  return { x, y }
}

function onMouseDown(e) {
  if (!currentImage.value) return
  isDrawing.value = true
  const coords = getImageCoords(e)
  drawStart.value = coords
  drawEnd.value = coords
}

function onMouseMove(e) {
  if (!isDrawing.value) return
  drawEnd.value = getImageCoords(e)
  renderCanvas()
}

function onMouseUp(e) {
  if (!isDrawing.value) return
  isDrawing.value = false
  drawEnd.value = getImageCoords(e)

  // Normalize to YOLO format (0-1)
  const img = loadedImages.get(currentImage.value.url)
  if (!img) return

  const x1 = Math.min(drawStart.value.x, drawEnd.value.x)
  const y1 = Math.min(drawStart.value.y, drawEnd.value.y)
  const x2 = Math.max(drawStart.value.x, drawEnd.value.x)
  const y2 = Math.max(drawStart.value.y, drawEnd.value.y)

  // Minimum box size
  if (Math.abs(x2 - x1) < 5 || Math.abs(y2 - y1) < 5) return

  const label = {
    cls: selectedClass.value,
    x: (x1 + x2) / 2 / img.naturalWidth,
    y: (y1 + y2) / 2 / img.naturalHeight,
    w: Math.abs(x2 - x1) / img.naturalWidth,
    h: Math.abs(y2 - y1) / img.naturalHeight,
    conf: 1.0,
  }

  if (!currentImage.value.labels) currentImage.value.labels = []
  currentImage.value.labels.push(label)
  selectedLabelIndex.value = currentImage.value.labels.length - 1
  renderCanvas()
}

function deleteSelectedLabel() {
  if (selectedLabelIndex.value === null || !currentImage.value) return
  currentImage.value.labels.splice(selectedLabelIndex.value, 1)
  selectedLabelIndex.value = null
  renderCanvas()
}

function renderCanvas() {
  const cvs = canvas.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  const img = loadedImages.get(currentImage.value?.url)
  if (!img) return

  // Set canvas size to match image display
  const maxW = cvs.parentElement.clientWidth
  const maxH = 480
  const imgRatio = img.naturalWidth / img.naturalHeight
  let displayW, displayH

  if (maxW / maxH > imgRatio) {
    displayH = maxH
    displayW = maxH * imgRatio
  } else {
    displayW = maxW
    displayH = maxW / imgRatio
  }

  cvs.width = displayW
  cvs.height = displayH
  scale.value = displayW / img.naturalWidth

  // Draw image
  ctx.drawImage(img, 0, 0, displayW, displayH)

  // Draw existing labels
  const labels = currentImage.value?.labels || []
  labels.forEach((label, i) => {
    const color = classColors[classes.value.indexOf(label.cls) % classColors.length]
    const bx = label.x * displayW
    const by = label.y * displayH
    const bw = label.w * displayW
    const bh = label.h * displayH

    ctx.strokeStyle = color
    ctx.lineWidth = i === selectedLabelIndex.value ? 3 : 2
    ctx.strokeRect(bx - bw / 2, by - bh / 2, bw, bh)

    // Label text
    ctx.fillStyle = color
    ctx.fillRect(bx - bw / 2, by - bh / 2 - 16, ctx.measureText(label.cls).width + 8, 16)
    ctx.fillStyle = '#fff'
    ctx.font = '12px sans-serif'
    ctx.fillText(label.cls, bx - bw / 2 + 4, by - bh / 2 - 4)
  })

  // Draw current drawing box
  if (isDrawing.value) {
    const x = Math.min(drawStart.value.x, drawEnd.value.x) * scale.value
    const y = Math.min(drawStart.value.y, drawEnd.value.y) * scale.value
    const w = Math.abs(drawEnd.value.x - drawStart.value.x) * scale.value
    const h = Math.abs(drawEnd.value.y - drawStart.value.y) * scale.value
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.strokeRect(x, y, w, h)
    ctx.setLineDash([])
  }
}

// Watch for image changes and render
watch(currentIndex, async () => {
  selectedLabelIndex.value = null
  if (!currentImage.value) return

  // Load image if not cached
  if (!loadedImages.has(currentImage.value.url)) {
    const img = new Image()
    img.src = currentImage.value.url
    await new Promise(resolve => { img.onload = resolve })
    loadedImages.set(currentImage.value.url, img)
  }

  renderCanvas()
})

// Auto label via YOLO
async function runAutoLabel() {
  isAutoLabeling.value = true
  try {
    for (const img of images.value) {
      if (!img.file) continue
      const formData = new FormData()
      formData.append('file', img.file)
      const { data } = await http.post('/api/label/auto', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      img.labels = [...(img.labels || []), ...data.detections.map(d => ({
        cls: d.cls,
        x: d.x,
        y: d.y,
        w: d.w,
        h: d.h,
        conf: d.conf,
      }))]
    }
    if (currentImage.value) renderCanvas()
  } catch (e) {
    console.error('Auto label failed:', e)
    alert('Auto label failed: ' + (e.response?.data?.error || e.message))
  }
  isAutoLabeling.value = false
}

// Export YOLO format
function exportLabels() {
  const lines = []
  lines.push('# YOLO dataset export')
  lines.push(`# Classes: ${classes.value.join(', ')}`)
  lines.push('')

  // classes.txt
  const classesContent = classes.value.join('\n')
  downloadFile('classes.txt', classesContent)

  // labels for each image
  images.value.forEach(img => {
    if (!img.labels || img.labels.length === 0) return
    const labelLines = img.labels.map(l => {
      const classIdx = classes.value.indexOf(l.cls)
      return `${classIdx} ${l.x.toFixed(6)} ${l.y.toFixed(6)} ${l.w.toFixed(6)} ${l.h.toFixed(6)}`
    })
    downloadFile(img.name.replace(/\.[^.]+$/, '.txt'), labelLines.join('\n'))
  })

  alert(`Exported labels for ${images.value.filter(i => i.labels?.length).length} images`)
}

function downloadFile(filename, content) {
  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function clearAll() {
  if (!confirm('Clear all images and labels?')) return
  images.value = []
  currentIndex.value = -1
  loadedImages.clear()
}

onMounted(() => {
  window.addEventListener('resize', () => renderCanvas())
})
</script>
