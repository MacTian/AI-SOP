<template>
  <div class="bg-white rounded-lg shadow-sm border">
    <div class="p-4 border-b flex items-center justify-between">
      <h3 class="font-medium">Step Editor</h3>
      <button
        @click="$emit('save')"
        class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
      >
        Save as SOP
      </button>
    </div>

    <div class="divide-y">
      <div
        v-for="(step, index) in steps"
        :key="step.step_id"
        class="p-4 hover:bg-gray-50"
        draggable="true"
        @dragstart="dragStart(index, $event)"
        @dragover.prevent
        @drop="drop(index)"
      >
        <div class="flex items-start space-x-3">
          <!-- Drag Handle + Step Number -->
          <div class="flex flex-col items-center space-y-1 cursor-grab">
            <span class="text-gray-400">⠿</span>
            <span class="w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium">
              {{ index + 1 }}
            </span>
          </div>

          <!-- Step Content -->
          <div class="flex-1 min-w-0 space-y-2">
            <!-- Name (editable) -->
            <div v-if="editingId === step.step_id" class="flex items-center space-x-2">
              <input
                v-model="editForm.name"
                class="flex-1 border rounded px-2 py-1 text-sm"
                @keyup.enter="saveEdit(step.step_id)"
                @keyup.escape="cancelEdit"
              />
              <button @click="saveEdit(step.step_id)" class="text-green-600 text-sm">Save</button>
              <button @click="cancelEdit" class="text-gray-400 text-sm">Cancel</button>
            </div>
            <div v-else class="flex items-center space-x-2">
              <span class="font-medium text-sm">{{ step.name }}</span>
              <button @click="startEdit(step)" class="text-gray-400 hover:text-blue-600 text-xs">Edit</button>
            </div>

            <!-- Description -->
            <div class="text-xs text-gray-500">{{ step.description }}</div>

            <!-- Objects & Confidence -->
            <div class="flex items-center space-x-2 flex-wrap">
              <span
                v-for="obj in step.expected_objects"
                :key="obj"
                class="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
              >
                {{ obj }}
              </span>
              <span class="text-xs text-gray-400">
                conf: {{ (step.min_confidence * 100).toFixed(0) }}%
              </span>
              <span class="text-xs text-gray-400">
                timeout: {{ step.timeout }}s
              </span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center space-x-1">
            <button
              @click="moveUp(index)"
              :disabled="index === 0"
              class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-30"
              title="Move up"
            >
              ▲
            </button>
            <button
              @click="moveDown(index)"
              :disabled="index === steps.length - 1"
              class="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-30"
              title="Move down"
            >
              ▼
            </button>
            <button
              @click="$emit('delete', step.step_id)"
              class="p-1 text-gray-400 hover:text-red-600"
              title="Delete step"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- Expanded Edit Panel -->
        <div v-if="editingId === step.step_id" class="mt-3 ml-9 grid grid-cols-3 gap-2">
          <div>
            <label class="block text-xs text-gray-500 mb-1">Expected Objects</label>
            <input
              v-model="editForm.expected_objects"
              class="w-full border rounded px-2 py-1 text-xs"
              placeholder="object1, object2"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Min Confidence</label>
            <input
              v-model.number="editForm.min_confidence"
              type="number"
              min="0"
              max="1"
              step="0.05"
              class="w-full border rounded px-2 py-1 text-xs"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Timeout (s)</label>
            <input
              v-model.number="editForm.timeout"
              type="number"
              min="10"
              class="w-full border rounded px-2 py-1 text-xs"
            />
          </div>
        </div>
      </div>

      <div v-if="steps.length === 0" class="p-8 text-center text-gray-400">
        No steps identified. Try recording a training session.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
})

const emit = defineEmits(['update', 'delete', 'reorder', 'save'])

const editingId = ref(null)
const editForm = ref({})

let dragIndex = null

function startEdit(step) {
  editingId.value = step.step_id
  editForm.value = {
    name: step.name,
    expected_objects: (step.expected_objects || []).join(', '),
    min_confidence: step.min_confidence || 0.5,
    timeout: step.timeout || 120,
  }
}

function cancelEdit() {
  editingId.value = null
}

function saveEdit(stepId) {
  const updates = {
    name: editForm.value.name,
    expected_objects: editForm.value.expected_objects.split(',').map(s => s.trim()).filter(Boolean),
    min_confidence: editForm.value.min_confidence,
    timeout: editForm.value.timeout,
  }
  emit('update', stepId, updates)
  editingId.value = null
}

function moveUp(index) {
  if (index <= 0) return
  const ids = props.steps.map(s => s.step_id)
  ;[ids[index - 1], ids[index]] = [ids[index], ids[index - 1]]
  emit('reorder', ids)
}

function moveDown(index) {
  if (index >= props.steps.length - 1) return
  const ids = props.steps.map(s => s.step_id)
  ;[ids[index], ids[index + 1]] = [ids[index + 1], ids[index]]
  emit('reorder', ids)
}

function dragStart(index, event) {
  dragIndex = index
  event.dataTransfer.effectAllowed = 'move'
}

function drop(targetIndex) {
  if (dragIndex === null || dragIndex === targetIndex) return
  const ids = props.steps.map(s => s.step_id)
  const [moved] = ids.splice(dragIndex, 1)
  ids.splice(targetIndex, 0, moved)
  emit('reorder', ids)
  dragIndex = null
}
</script>
