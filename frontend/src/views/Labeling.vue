<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">YOLO Data Labeling</h2>
      <div class="flex items-center space-x-3">
        <span class="text-sm text-gray-500">{{ images.length }} images</span>
        <span class="text-sm text-gray-400">|</span>
        <span class="text-sm text-gray-500">{{ totalLabels }} labels</span>
        <span class="text-sm text-gray-400">|</span>
        <span class="text-sm text-gray-500">{{ rectCount }} boxes, {{ rotRectCount }} rotRects, {{ circleCount }} circles, {{ polyCount }} polygons</span>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <!-- Left Sidebar -->
      <div class="lg:col-span-2 space-y-3">
        <!-- Drawing Tools -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-sm mb-2">Tools</h3>
          <div class="grid grid-cols-2 gap-1.5">
            <button @click="tool = 'rectangle'"
              class="px-2 py-1.5 text-xs rounded border text-center transition-colors"
              :class="tool === 'rectangle' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'">
              <span class="block text-base mb-0.5">▭</span>Box
            </button>
            <button @click="tool = 'rotatedRect'"
              class="px-2 py-1.5 text-xs rounded border text-center transition-colors"
              :class="tool === 'rotatedRect' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'">
              <span class="block text-base mb-0.5">▰</span>RotRect
            </button>
            <button @click="tool = 'circle'"
              class="px-2 py-1.5 text-xs rounded border text-center transition-colors"
              :class="tool === 'circle' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'">
              <span class="block text-base mb-0.5">◯</span>Circle
            </button>
            <button @click="tool = 'polygon'"
              class="px-2 py-1.5 text-xs rounded border text-center transition-colors"
              :class="tool === 'polygon' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'">
              <span class="block text-base mb-0.5">⬠</span>Polygon
            </button>
            <button @click="tool = 'select'"
              class="px-2 py-1.5 text-xs rounded border text-center transition-colors"
              :class="tool === 'select' ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 hover:bg-gray-50'">
              <span class="block text-base mb-0.5">↖</span>Select
            </button>
            <button @click="undoLast" :disabled="!canUndo"
              class="px-2 py-1.5 text-xs rounded border text-center bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-40">
              <span class="block text-base mb-0.5">↩</span>Undo
            </button>
          </div>
          <p class="text-xs text-gray-400 mt-2 leading-tight">
            <template v-if="tool === 'rectangle'">Click & drag to draw box</template>
            <template v-else-if="tool === 'rotatedRect'">Click center, drag to set width & angle, then drag to set height</template>
            <template v-else-if="tool === 'circle'">Click center, drag to set radius</template>
            <template v-else-if="tool === 'polygon'">Click vertices, double-click to close</template>
            <template v-else-if="tool === 'select'">Click label to select & delete</template>
          </p>
        </div>

        <!-- Zoom -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-sm mb-2">Zoom: {{ (zoom * 100).toFixed(0) }}%</h3>
          <input type="range" v-model.number="zoom" min="0.25" max="4" step="0.25" class="w-full" />
          <button @click="zoom = 1; panOffset = { x: 0, y: 0 }"
            class="mt-1 w-full text-xs text-gray-500 hover:text-gray-700">Reset View</button>
        </div>

        <!-- Upload -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-sm mb-2">Upload</h3>
          <input ref="fileInput" type="file" multiple accept="image/*" class="hidden" @change="handleFileUpload" />
          <button @click="fileInput.click()"
            class="w-full px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-xs text-gray-600 hover:border-blue-400 hover:text-blue-600">
            + Select Images
          </button>
        </div>

        <!-- Image List -->
        <div class="bg-white rounded-lg shadow-sm border overflow-hidden">
          <div class="p-2 border-b bg-gray-50 flex items-center justify-between">
            <h3 class="font-medium text-xs">Images</h3>
            <span class="text-xs text-gray-400">{{ currentIndex + 1 }}/{{ images.length }}</span>
          </div>
          <div class="max-h-52 overflow-y-auto divide-y">
            <div v-for="(img, i) in images" :key="img.name" @click="selectImage(i)"
              class="p-1.5 cursor-pointer flex items-center space-x-2 text-xs"
              :class="currentIndex === i ? 'bg-blue-50' : 'hover:bg-gray-50'">
              <img :src="img.url" class="w-8 h-8 object-cover rounded" />
              <div class="flex-1 min-w-0">
                <p class="truncate">{{ img.name }}</p>
                <p class="text-[10px] text-gray-400">{{ (img.labels || []).length }} labels</p>
              </div>
              <button @click.stop="removeImage(i)" class="text-gray-400 hover:text-red-500 px-1">×</button>
            </div>
            <div v-if="images.length === 0" class="p-3 text-center text-xs text-gray-400">No images</div>
          </div>
        </div>
      </div>

      <!-- Center: Canvas -->
      <div class="lg:col-span-8 space-y-3">
        <!-- Canvas Toolbar -->
        <div class="bg-white rounded-lg shadow-sm border p-2 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-sm font-medium">Canvas</span>
            <span v-if="currentImage" class="text-xs text-gray-400">{{ currentImage.name }}</span>
            <span v-if="currentImage" class="text-xs text-gray-400">
              ({{ currentImage.width }}×{{ currentImage.height }})
            </span>
          </div>
          <div class="flex items-center space-x-2">
            <select v-model="selectedClass" class="text-xs border rounded px-2 py-1">
              <option v-for="cls in classes" :key="cls" :value="cls">{{ cls }}</option>
            </select>
            <button @click="deleteSelectedLabel" :disabled="selectedLabelIndex === null"
              class="px-2 py-1 text-xs border rounded hover:bg-gray-50 disabled:opacity-40">Delete</button>
            <button @click="runAutoLabel" :disabled="!currentImage || isAutoLabeling"
              class="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-40">
              {{ isAutoLabeling ? '...' : 'Auto Label' }}
            </button>
          </div>
        </div>

        <!-- Canvas -->
        <div ref="canvasWrapper" class="relative bg-gray-900 rounded-lg overflow-hidden"
          style="min-height: 520px; height: calc(100vh - 240px);">
          <canvas ref="canvas"
            class="absolute inset-0 w-full h-full"
            :class="{ 'cursor-crosshair': tool !== 'select', 'cursor-default': tool === 'select' }"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
            @mouseleave="onMouseUp"
            @dblclick="onDoubleClick"
            @contextmenu.prevent="onRightClick"
            @wheel.prevent="onWheel"
          />
          <div v-if="!currentImage"
            class="absolute inset-0 flex items-center justify-center text-gray-500 pointer-events-none">
            <div class="text-center">
              <p class="text-lg mb-2">No image selected</p>
              <p class="text-sm">Upload images to start labeling</p>
            </div>
          </div>
          <div v-if="tool === 'polygon' && isDrawingPolygon"
            class="absolute bottom-3 left-3 bg-black/70 text-white text-xs px-2 py-1 rounded">
            Polygon: {{ currentPolygon.length }} vertices — double-click to close
          </div>
          <div v-if="tool === 'rotatedRect' && isDrawingRotRect"
            class="absolute bottom-3 left-3 bg-black/70 text-white text-xs px-2 py-1 rounded">
            <template v-if="rotRectStep === 1">RotRect: drag to set width & angle</template>
            <template v-else-if="rotRectStep === 2">RotRect: drag to set height — right-click to cancel</template>
          </div>
        </div>

        <!-- Navigation -->
        <div class="flex items-center justify-between bg-white rounded-lg shadow-sm border p-2">
          <button @click="prevImage" :disabled="currentIndex <= 0"
            class="px-3 py-1 border rounded text-sm disabled:opacity-40">← Prev</button>
          <div class="flex items-center space-x-1">
            <button v-for="(_, i) in images.slice(Math.max(0, currentIndex - 3), currentIndex + 4)" :key="i"
              @click="selectImage(i + Math.max(0, currentIndex - 3))"
              class="w-6 h-6 rounded text-xs"
              :class="i + Math.max(0, currentIndex - 3) === currentIndex
                ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'">
              {{ i + Math.max(0, currentIndex - 3) + 1 }}
            </button>
          </div>
          <button @click="nextImage" :disabled="currentIndex >= images.length - 1"
            class="px-3 py-1 border rounded text-sm disabled:opacity-40">Next →</button>
        </div>
      </div>

      <!-- Right Sidebar -->
      <div class="lg:col-span-2 space-y-3">
        <!-- Classes -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-sm mb-2">Classes</h3>
          <div class="flex space-x-1 mb-2">
            <input v-model="newClass" placeholder="Add class..." class="flex-1 border rounded px-2 py-1 text-xs"
              @keyup.enter="addClass" />
            <button @click="addClass" class="px-2 py-1 bg-gray-100 rounded text-xs hover:bg-gray-200">+</button>
          </div>
          <div class="space-y-0.5 max-h-36 overflow-y-auto">
            <div v-for="(cls, i) in classes" :key="cls"
              class="flex items-center justify-between p-1 rounded text-xs cursor-pointer"
              :class="selectedClass === cls ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'"
              @click="selectedClass = cls">
              <div class="flex items-center space-x-1.5">
                <span class="w-2.5 h-2.5 rounded-sm"
                  :style="{ backgroundColor: classColors[i % classColors.length] }"></span>
                <span>{{ cls }}</span>
              </div>
              <button v-if="i > 0" @click.stop="removeClass(i)"
                class="text-gray-400 hover:text-red-500 px-1">×</button>
            </div>
          </div>
        </div>

        <!-- Labels -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-sm mb-2">Labels ({{ currentLabels.length }})</h3>
          <div v-if="currentImage" class="space-y-0.5 max-h-48 overflow-y-auto">
            <div v-for="(label, i) in currentLabels" :key="i"
              @click="selectedLabelIndex = i; renderCanvas()"
              class="flex items-center space-x-1.5 p-1 rounded text-xs cursor-pointer"
              :class="selectedLabelIndex === i ? 'bg-blue-50 border border-blue-200' : 'hover:bg-gray-50'">
              <span class="w-2 h-2 rounded-sm"
                :style="{ backgroundColor: classColors[classes.indexOf(label.cls) % classColors.length] }"></span>
              <span class="flex-1 truncate">
                {{ label.cls }}<template v-if="label.type === 'rotatedRect' && label.angle !== undefined"> {{ (label.angle * 180 / Math.PI).toFixed(0) }}°</template>
              </span>
              <span class="text-gray-400 text-[10px]">
                {{ label.type === 'polygon' ? '⬠' : label.type === 'rotatedRect' ? '▰' : label.type === 'circle' ? '◯' : '▭' }}
              </span>
              <span class="text-gray-400 text-[10px]">{{ (label.conf * 100).toFixed(0) }}%</span>
            </div>
            <div v-if="currentLabels.length === 0" class="text-xs text-gray-400 text-center py-2">No labels</div>
          </div>
          <div v-else class="text-xs text-gray-400 text-center py-2">Select an image</div>
        </div>

        <!-- Actions -->
        <div class="bg-white rounded-lg shadow-sm border p-3 space-y-1.5">
          <button @click="exportLabels" :disabled="totalLabels === 0"
            class="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs hover:bg-gray-50 disabled:opacity-40">
            Export YOLO Format
          </button>
          <button @click="exportCOCO" :disabled="totalLabels === 0"
            class="w-full px-3 py-1.5 border border-gray-300 rounded-md text-xs hover:bg-gray-50 disabled:opacity-40">
            Export COCO JSON
          </button>
          <button @click="clearAll"
            class="w-full px-3 py-1.5 border border-red-200 text-red-600 rounded-md text-xs hover:bg-red-50">
            Clear All
          </button>
        </div>

        <!-- Import Classes -->
        <div class="bg-white rounded-lg shadow-sm border p-3">
          <h3 class="font-medium text-xs mb-1">Import Classes</h3>
          <textarea v-model="classesYaml" class="w-full border rounded px-2 py-1 text-xs font-mono" rows="3"
            placeholder="class1&#10;class2"></textarea>
          <button @click="importClasses"
            class="mt-1 w-full px-2 py-1 border rounded text-xs hover:bg-gray-50">Import</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import http from '../api/http'

// ==================== State ====================
const images = ref([])
const currentIndex = ref(-1)
const classes = ref(['board', 'hand', 'tool', 'solder', 'component'])
const newClass = ref('')
const selectedClass = ref('board')
const selectedLabelIndex = ref(null)
const isAutoLabeling = ref(false)
const classesYaml = ref('')
const fileInput = ref(null)

const tool = ref('rectangle') // 'rectangle' | 'rotatedRect' | 'circle' | 'polygon' | 'select'
const zoom = ref(1)
const panOffset = ref({ x: 0, y: 0 })

const canvas = ref(null)
const canvasWrapper = ref(null)

// Rectangle drawing
const isDrawingRect = ref(false)
const rectStart = ref({ x: 0, y: 0 })
const rectEnd = ref({ x: 0, y: 0 })

// Polygon drawing
const isDrawingPolygon = ref(false)
const currentPolygon = ref([])

// Image cache
const loadedImages = new Map()

// Undo
const undoStack = ref([])

// Colors
const classColors = [
  '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
  '#EC4899', '#06B6D4', '#F97316', '#84CC16', '#6366F1',
]

// ==================== Computed ====================
const currentImage = computed(() => images.value[currentIndex.value] || null)
const currentLabels = computed(() => currentImage.value?.labels || [])
const totalLabels = computed(() =>
  images.value.reduce((sum, img) => sum + (img.labels?.length || 0), 0)
)
const rectCount = computed(() =>
  images.value.reduce((sum, img) => sum + (img.labels?.filter(l => l.type === 'box' || !l.type).length || 0), 0)
)
const polyCount = computed(() =>
  images.value.reduce((sum, img) => sum + (img.labels?.filter(l => l.type === 'polygon').length || 0), 0)
)
const canUndo = computed(() => undoStack.value.length > 0)

// ==================== Helpers ====================
function saveUndo() {
  const snapshot = images.value.map(img => ({
    ...img,
    labels: (img.labels || []).map(l => ({ ...l, points: l.points ? [...l.points.map(p => ({ ...p }))] : undefined })),
  }))
  undoStack.value.push(snapshot)
  if (undoStack.value.length > 50) undoStack.value.shift()
}

function undoLast() {
  if (!canUndo.value) return
  const snapshot = undoStack.value.pop()
  images.value = snapshot
  renderCanvas()
}

function toImageCoords(e) {
  const rect = canvas.value.getBoundingClientRect()
  return {
    x: (e.clientX - rect.left - panOffset.value.x) / zoom.value,
    y: (e.clientY - rect.top - panOffset.value.y) / zoom.value,
  }
}

function pointInPolygon(pt, polygon) {
  // Ray casting algorithm
  let inside = false
  const n = polygon.length
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y
    const xj = polygon[j].x, yj = polygon[j].y
    if ((yi > pt.y) !== (yj > pt.y) && pt.x < (xj - xi) * (pt.y - yi) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

// ==================== File Upload ====================
function handleFileUpload(e) {
  const files = Array.from(e.target.files)
  files.forEach(file => {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const url = ev.target.result
      const img = new Image()
      img.onload = () => {
        images.value.push({
          name: file.name,
          url,
          labels: [],
          file,
          width: img.naturalWidth,
          height: img.naturalHeight,
        })
        if (currentIndex.value < 0) {
          currentIndex.value = 0
          loadAndRender(0)
        }
      }
      img.src = url
    }
    reader.readAsDataURL(file)
  })
  e.target.value = ''
}

function removeImage(i) {
  images.value.splice(i, 1)
  if (currentIndex.value >= images.value.length) currentIndex.value = images.value.length - 1
  if (currentIndex.value >= 0) loadAndRender(currentIndex.value)
  else renderCanvas()
}

function selectImage(i) {
  currentIndex.value = i
  loadAndRender(i)
}

function prevImage() { if (currentIndex.value > 0) selectImage(currentIndex.value - 1) }
function nextImage() { if (currentIndex.value < images.value.length - 1) selectImage(currentIndex.value + 1) }

async function loadAndRender(i) {
  selectedLabelIndex.value = null
  const img = images.value[i]
  if (!img) return
  if (!loadedImages.has(img.url)) {
    const imageObj = new Image()
    imageObj.src = img.url
    await new Promise(resolve => { imageObj.onload = resolve })
    loadedImages.set(img.url, imageObj)
  }
  await nextTick()
  renderCanvas()
}

// ==================== Classes ====================
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
  if (selectedClass.value === removed) selectedClass.value = classes.value[0] || ''
}

function importClasses() {
  classesYaml.value.split('\n').map(l => l.trim()).filter(l => l).forEach(cls => {
    if (!classes.value.includes(cls)) classes.value.push(cls)
  })
  classesYaml.value = ''
}

// ==================== Mouse Events ====================
function onMouseDown(e) {
  if (!currentImage.value || e.button !== 0) return
  const coords = toImageCoords(e)

  if (tool.value === 'rectangle') {
    saveUndo()
    isDrawingRect.value = true
    rectStart.value = coords
    rectEnd.value = coords
    renderCanvas()
  } else if (tool.value === 'polygon') {
    saveUndo()
    if (!isDrawingPolygon.value) {
      isDrawingPolygon.value = true
      currentPolygon.value = [coords]
    } else {
      // Check closing: near first vertex
      if (currentPolygon.value.length >= 3) {
        const first = currentPolygon.value[0]
        const dist = Math.hypot(coords.x - first.x, coords.y - first.y)
        if (dist < 10 / zoom.value) {
          finishPolygon()
          return
        }
      }
      currentPolygon.value.push(coords)
    }
    renderCanvas()
  } else if (tool.value === 'select') {
    const labels = currentLabels.value
    let hit = false
    for (let i = labels.length - 1; i >= 0; i--) {
      const label = labels[i]
      if (label.type === 'polygon') {
        const img = loadedImages.get(currentImage.value.url)
        const pts = label.points.map(p => ({
          x: p.x * img.naturalWidth,
          y: p.y * img.naturalHeight,
        }))
        if (pointInPolygon(coords, pts)) {
          selectedLabelIndex.value = i
          hit = true
          break
        }
      } else {
        const img = loadedImages.get(currentImage.value.url)
        const cx = label.x * img.naturalWidth
        const cy = label.y * img.naturalHeight
        const hw = (label.w * img.naturalWidth) / 2
        const hh = (label.h * img.naturalHeight) / 2
        if (coords.x >= cx - hw && coords.x <= cx + hw && coords.y >= cy - hh && coords.y <= cy + hh) {
          selectedLabelIndex.value = i
          hit = true
          break
        }
      }
    }
    if (!hit) selectedLabelIndex.value = null
    renderCanvas()
  }
}

function onMouseMove(e) {
  if (tool.value === 'rectangle' && isDrawingRect.value) {
    rectEnd.value = toImageCoords(e)
    renderCanvas()
  } else if (tool.value === 'polygon' && isDrawingPolygon.value) {
    renderCanvas(toImageCoords(e))
  }
}

function onMouseUp(e) {
  if (tool.value === 'rectangle' && isDrawingRect.value) {
    isDrawingRect.value = false
    rectEnd.value = toImageCoords(e)
    const img = loadedImages.get(currentImage.value.url)
    if (!img) { renderCanvas(); return }

    const x1 = Math.min(rectStart.value.x, rectEnd.value.x)
    const y1 = Math.min(rectStart.value.y, rectEnd.value.y)
    const x2 = Math.max(rectStart.value.x, rectEnd.value.x)
    const y2 = Math.max(rectStart.value.y, rectEnd.value.y)
    if (Math.abs(x2 - x1) < 3 || Math.abs(y2 - y1) < 3) { renderCanvas(); return }

    const label = {
      type: 'box',
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
}

function onDoubleClick(e) {
  if (tool.value === 'polygon' && isDrawingPolygon.value && currentPolygon.value.length >= 3) {
    finishPolygon()
  }
}

function onRightClick(e) {
  if (tool.value === 'polygon' && isDrawingPolygon.value) {
    if (currentPolygon.value.length >= 3) {
      finishPolygon()
    } else {
      isDrawingPolygon.value = false
      currentPolygon.value = []
      renderCanvas()
    }
  }
}

function onWheel(e) {
  const delta = e.deltaY > 0 ? -0.25 : 0.25
  const newZoom = Math.max(0.25, Math.min(4, zoom.value + delta))
  zoom.value = newZoom
  renderCanvas()
}

function finishPolygon() {
  const img = loadedImages.get(currentImage.value.url)
  if (!img || currentPolygon.value.length < 3) {
    isDrawingPolygon.value = false
    currentPolygon.value = []
    renderCanvas()
    return
  }

  // Normalize polygon points to 0-1
  const points = currentPolygon.value.map(p => ({
    x: p.x / img.naturalWidth,
    y: p.y / img.naturalHeight,
  }))

  // Compute bounding box for the polygon
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)

  const label = {
    type: 'polygon',
    cls: selectedClass.value,
    points,
    // Also store bbox for compatibility
    x: (minX + maxX) / 2,
    y: (minY + maxY) / 2,
    w: maxX - minX,
    h: maxY - minY,
    conf: 1.0,
  }

  if (!currentImage.value.labels) currentImage.value.labels = []
  currentImage.value.labels.push(label)
  selectedLabelIndex.value = currentImage.value.labels.length - 1

  isDrawingPolygon.value = false
  currentPolygon.value = []
  renderCanvas()
}

// Helper: get the 4 corners of a rotated rectangle
function getRotRectCorners(cx, cy, w, h, angle) {
	  const cos = Math.cos(angle)
	  const sin = Math.sin(angle)
	  const hw = w / 2
	  const hh = h / 2
	  return [
	    { x: cx + cos * hw - sin * hh, y: cy + sin * hw + cos * hh },
	    { x: cx - cos * hw - sin * hh, y: cy - sin * hw + cos * hh },
	    { x: cx - cos * hw + sin * hh, y: cy - sin * hw - cos * hh },
	    { x: cx + cos * hw + sin * hh, y: cy + sin * hw - cos * hh },
	  ]
}

// Helper: check point in rotated rectangle
function pointInRotRect(pt, label, img) {
	  const cx = label.x * img.naturalWidth
	  const cy = label.y * img.naturalHeight
	  const w = label.w * img.naturalWidth
	  const h = label.h * img.naturalHeight
	  const angle = label.angle || 0
	  // Transform point into rect local space
	  const cos = Math.cos(-angle)
	  const sin = Math.sin(-angle)
	  const dx = pt.x - cx
	  const dy = pt.y - cy
	  const lx = dx * cos - dy * sin
	  const ly = dx * sin + dy * cos
	  return Math.abs(lx) <= w / 2 && Math.abs(ly) <= h / 2
}

function finishRotatedRect(mouseCoords) {
	  const img = loadedImages.get(currentImage.value.url)
	  if (!img) {
	    isDrawingRotRect.value = false
	    rotRectStep.value = 0
	    renderCanvas()
	    return
	  }

	  // Calculate height from mouse position
	  const cx = rotRectCenter.value.x
	  const cy = rotRectCenter.value.y
	  const angle = rotRectAngle.value

	  // Project mouse-center vector onto the direction perpendicular to width
	  const perpAngle = angle + Math.PI / 2
	  const dx = mouseCoords.x - cx
	  const dy = mouseCoords.y - cy
	  const height = Math.abs(dx * Math.cos(perpAngle) + dy * Math.sin(perpAngle)) * 2

	  if (rotRectWidth.value < 3 || height < 3) {
	    isDrawingRotRect.value = false
	    rotRectStep.value = 0
	    renderCanvas()
	    return
	  }

	  const label = {
	    type: 'rotatedRect',
	    cls: selectedClass.value,
	    x: cx / img.naturalWidth,
	    y: cy / img.naturalHeight,
	    w: rotRectWidth.value / img.naturalWidth,
	    h: height / img.naturalHeight,
	    angle: angle,
	    conf: 1.0,
	  }
	  if (!currentImage.value.labels) currentImage.value.labels = []
	  currentImage.value.labels.push(label)
	  selectedLabelIndex.value = currentImage.value.labels.length - 1

	  isDrawingRotRect.value = false
	  rotRectStep.value = 0
	  renderCanvas()
	}

function deleteSelectedLabel() {
  if (selectedLabelIndex.value === null || !currentImage.value) return
  saveUndo()
  currentImage.value.labels.splice(selectedLabelIndex.value, 1)
  selectedLabelIndex.value = null
  renderCanvas()
}

// ==================== Canvas Rendering ====================
function renderCanvas(mousePos = null) {
  const cvs = canvas.value
  if (!cvs) return
  const ctx = cvs.getContext('2d')
  const wrapper = canvasWrapper.value
  if (!wrapper) return

  // Resize canvas to match display
  const dpr = window.devicePixelRatio || 1
  const rect = wrapper.getBoundingClientRect()
  cvs.width = rect.width * dpr
  cvs.height = rect.height * dpr
  ctx.scale(dpr, dpr)

  const w = rect.width
  const h = rect.height
  ctx.clearRect(0, 0, w, h)

  // Draw checkerboard background
  const tileSize = 16
  for (let y = 0; y < h; y += tileSize) {
    for (let x = 0; x < w; x += tileSize) {
      ctx.fillStyle = ((x + y) / tileSize) % 2 === 0 ? '#1a1a2e' : '#16213e'
      ctx.fillRect(x, y, tileSize, tileSize)
    }
  }

  const img = loadedImages.get(currentImage.value?.url)
  if (!img) return

  // Calculate image display area with zoom and pan
  const imgW = img.naturalWidth * zoom.value
  const imgH = img.naturalHeight * zoom.value
  const drawX = panOffset.value.x
  const drawY = panOffset.value.y

  ctx.save()
  // Clip to image area
  ctx.beginPath()
  ctx.rect(drawX, drawY, imgW, imgH)
  ctx.clip()
  ctx.drawImage(img, drawX, drawY, imgW, imgH)

  // Draw labels
  const labels = currentImage.value?.labels || []
  labels.forEach((label, i) => {
    const color = classColors[classes.value.indexOf(label.cls) % classColors.length]
    const isSelected = i === selectedLabelIndex.value

    if (label.type === 'polygon' && label.points) {
      // Draw polygon
      ctx.beginPath()
      label.points.forEach((p, j) => {
        const px = drawX + p.x * imgW
        const py = drawY + p.y * imgH
        if (j === 0) ctx.moveTo(px, py)
        else ctx.lineTo(px, py)
      })
      ctx.closePath()
      ctx.fillStyle = color + (isSelected ? '60' : '30')
      ctx.fill()
      ctx.strokeStyle = color
      ctx.lineWidth = isSelected ? 3 : 2
      ctx.stroke()

      // Draw vertices
      label.points.forEach((p) => {
        const px = drawX + p.x * imgW
        const py = drawY + p.y * imgH
        ctx.beginPath()
        ctx.arc(px, py, isSelected ? 4 : 3, 0, Math.PI * 2)
        ctx.fillStyle = color
        ctx.fill()
      })
    } else {
      // Draw box
      const bx = drawX + label.x * imgW
      const by = drawY + label.y * imgH
      const bw = label.w * imgW
      const bh = label.h * imgH

      ctx.fillStyle = color + (isSelected ? '40' : '15')
      ctx.fillRect(bx - bw / 2, by - bh / 2, bw, bh)
      ctx.strokeStyle = color
      ctx.lineWidth = isSelected ? 3 : 2
      ctx.strokeRect(bx - bw / 2, by - bh / 2, bw, bh)

      // Label text background
      ctx.fillStyle = color
      const text = label.cls
      ctx.font = '11px sans-serif'
      const tw = ctx.measureText(text).width
      ctx.fillRect(bx - bw / 2, by - bh / 2 - 16, tw + 6, 16)
      ctx.fillStyle = '#fff'
      ctx.fillText(text, bx - bw / 2 + 3, by - bh / 2 - 4)
    }
  })

  // Draw current rectangle
  if (isDrawingRect.value) {
    const x = Math.min(rectStart.value.x, rectEnd.value.x) * zoom.value + drawX
    const y = Math.min(rectStart.value.y, rectEnd.value.y) * zoom.value + drawY
    const rw = Math.abs(rectEnd.value.x - rectStart.value.x) * zoom.value
    const rh = Math.abs(rectEnd.value.y - rectStart.value.y) * zoom.value
    ctx.strokeStyle = classColors[classes.value.indexOf(selectedClass.value) % classColors.length]
    ctx.lineWidth = 2
    ctx.setLineDash([6, 4])
    ctx.strokeRect(x, y, rw, rh)
    ctx.setLineDash([])
  }

  // Draw current polygon
  if (isDrawingPolygon.value && currentPolygon.value.length > 0) {
    const color = classColors[classes.value.indexOf(selectedClass.value) % classColors.length]

    // Draw edges
    ctx.beginPath()
    currentPolygon.value.forEach((p, j) => {
      const px = p.x * zoom.value + drawX
      const py = p.y * zoom.value + drawY
      if (j === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    })

    // Line to mouse position for preview
    if (mousePos) {
      ctx.lineTo(mousePos.x * zoom.value + drawX, mousePos.y * zoom.value + drawY)
    }
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.setLineDash([6, 4])
    ctx.stroke()
    ctx.setLineDash([])

    // Draw vertices
    currentPolygon.value.forEach((p, j) => {
      const px = p.x * zoom.value + drawX
      const py = p.y * zoom.value + drawY
      ctx.beginPath()
      ctx.arc(px, py, j === 0 ? 5 : 4, 0, Math.PI * 2)
      ctx.fillStyle = j === 0 ? '#fff' : color
      ctx.fill()
      if (j === 0) {
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.stroke()
      }
    })

    // First vertex hint
    if (currentPolygon.value.length >= 3) {
      const first = currentPolygon.value[0]
      const fx = first.x * zoom.value + drawX
      const fy = first.y * zoom.value + drawY
      ctx.beginPath()
      ctx.arc(fx, fy, 8, 0, Math.PI * 2)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1
      ctx.setLineDash([2, 2])
      ctx.stroke()
      ctx.setLineDash([])
    }
  }

  ctx.restore()
}

// ==================== Watch ====================
watch(currentIndex, async () => {
  selectedLabelIndex.value = null
  if (!currentImage.value) { renderCanvas(); return }
  if (!loadedImages.has(currentImage.value.url)) {
    const img = new Image()
    img.src = currentImage.value.url
    await new Promise(resolve => { img.onload = resolve })
    loadedImages.set(currentImage.value.url, img)
  }
  await nextTick()
  renderCanvas()
})

// ==================== Auto Label ====================
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
      if (!img.labels) img.labels = []
      data.detections.forEach(d => {
        img.labels.push({
          type: 'box',
          cls: d.cls,
          x: d.x,
          y: d.y,
          w: d.w,
          h: d.h,
          conf: d.conf,
        })
      })
    }
    if (currentImage.value) renderCanvas()
  } catch (e) {
    console.error('Auto label failed:', e)
    alert('Auto label failed: ' + (e.response?.data?.error || e.message))
  }
  isAutoLabeling.value = false
}

// ==================== Export ====================
function exportLabels() {
  const classList = classes.value.join('\n')
  downloadFile('classes.txt', classList)

  images.value.forEach(img => {
    if (!img.labels || img.labels.length === 0) return
    const lines = img.labels.map(l => {
      const classIdx = classes.value.indexOf(l.cls)
      if (l.type === 'polygon' && l.points) {
        // YOLO segmentation format: class_idx x1 y1 x2 y2 ...
        return classIdx + ' ' + l.points.map(p => p.x.toFixed(6) + ' ' + p.y.toFixed(6)).join(' ')
      }
      // YOLO bbox format: class_idx cx cy w h
      return `${classIdx} ${l.x.toFixed(6)} ${l.y.toFixed(6)} ${l.w.toFixed(6)} ${l.h.toFixed(6)}`
    })
    downloadFile(img.name.replace(/\.[^.]+$/, '.txt'), lines.join('\n'))
  })
  alert(`Exported ${images.value.filter(i => i.labels?.length).length} image labels`)
}

function exportCOCO() {
  const coco = {
    images: [],
    annotations: [],
    categories: classes.value.map((name, i) => ({ id: i, name })),
  }
  let annId = 1

  images.value.forEach((img, imgIdx) => {
    if (!img.labels || img.labels.length === 0) return
    coco.images.push({
      id: imgIdx,
      file_name: img.name,
      width: img.width || 0,
      height: img.height || 0,
    })
    img.labels.forEach(l => {
      const classIdx = classes.value.indexOf(l.cls)
      if (l.type === 'polygon' && l.points) {
        const flat = l.points.flatMap(p => [
          p.x * (img.width || 1),
          p.y * (img.height || 1),
        ])
        // Compute bbox from polygon
        const xs = l.points.map(p => p.x * (img.width || 1))
        const ys = l.points.map(p => p.y * (img.height || 1))
        const x = Math.min(...xs)
        const y = Math.min(...ys)
        const w = Math.max(...xs) - x
        const h = Math.max(...ys) - y
        coco.annotations.push({
          id: annId++, image_id: imgIdx, category_id: classIdx,
          segmentation: [flat], bbox: [x, y, w, h],
          area: w * h, iscrowd: 0,
        })
      } else {
        const x = (l.x - l.w / 2) * (img.width || 1)
        const y = (l.y - l.h / 2) * (img.height || 1)
        const w = l.w * (img.width || 1)
        const h = l.h * (img.height || 1)
        coco.annotations.push({
          id: annId++, image_id: imgIdx, category_id: classIdx,
          bbox: [x, y, w, h], area: w * h, iscrowd: 0,
        })
      }
    })
  })

  downloadFile('annotations.json', JSON.stringify(coco, null, 2))
  alert(`Exported COCO JSON with ${coco.annotations.length} annotations`)
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
  undoStack.value = []
  renderCanvas()
}

// ==================== Lifecycle ====================
onMounted(() => {
  window.addEventListener('resize', () => renderCanvas())
})

onUnmounted(() => {
  window.removeEventListener('resize', () => renderCanvas())
})
</script>
