<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">SOP Editor</h2>
      <div class="flex space-x-2">
        <button
          @click="showTemplate = true"
          class="px-4 py-2 border border-blue-300 text-blue-700 rounded-md hover:bg-blue-50 text-sm"
        >
          From Template
        </button>
        <button
          @click="showCreate = true"
          class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
        >
          + New SOP
        </button>
      </div>
    </div>

    <!-- SOP List -->
    <div class="bg-white rounded-lg shadow-sm border">
      <div class="p-4 border-b">
        <h3 class="font-medium">SOP Definitions</h3>
      </div>
      <div class="divide-y">
        <div
          v-for="sop in store.sopList"
          :key="sop.sop_id"
          class="p-4 flex items-center justify-between hover:bg-gray-50"
        >
          <div>
            <div class="font-medium">{{ sop.name }}</div>
            <div class="text-sm text-gray-500">
              {{ sop.sop_id }} · v{{ sop.version }} · {{ sop.step_count }} steps
            </div>
          </div>
          <div class="flex space-x-2">
            <button
              @click="editSop(sop.sop_id)"
              class="px-3 py-1 text-sm border rounded-md hover:bg-gray-50"
            >
              Edit
            </button>
            <button
              @click="handleDelete(sop.sop_id)"
              class="px-3 py-1 text-sm border border-red-300 text-red-600 rounded-md hover:bg-red-50"
            >
              Delete
            </button>
          </div>
        </div>
        <div v-if="store.sopList.length === 0" class="p-8 text-center text-gray-400">
          No SOP definitions yet. Click "New SOP" to create one.
        </div>
      </div>
    </div>

    <!-- Create/Edit Form (simplified) -->
    <div v-if="showCreate" class="bg-white rounded-lg shadow-sm border p-6">
      <h3 class="font-medium mb-4">{{ editingId ? 'Edit' : 'Create' }} SOP</h3>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">SOP ID</label>
          <input v-model="form.sop_id" class="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input v-model="form.name" class="w-full border rounded-md px-3 py-2 text-sm" />
        </div>
        <div class="col-span-2">
          <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
          <textarea v-model="form.description" class="w-full border rounded-md px-3 py-2 text-sm" rows="2"></textarea>
        </div>
      </div>

      <!-- Steps (simplified) -->
      <div class="mt-4">
        <div class="flex items-center justify-between mb-2">
          <h4 class="text-sm font-medium">Steps</h4>
          <button @click="addStep" class="text-sm text-blue-600 hover:underline">+ Add Step</button>
        </div>
        <div v-for="(step, i) in form.steps" :key="i" class="border rounded-md p-3 mb-2">
          <div class="grid grid-cols-3 gap-2">
            <input v-model="step.step_id" placeholder="Step ID" class="border rounded px-2 py-1 text-sm" />
            <input v-model="step.name" placeholder="Step Name" class="border rounded px-2 py-1 text-sm" />
            <input v-model="step.rule.expected_objects" placeholder="Objects (comma-separated)" class="border rounded px-2 py-1 text-sm" />
          </div>
        </div>
      </div>

      <div class="mt-4 flex space-x-2">
        <button @click="handleSave" class="px-4 py-2 bg-blue-600 text-white rounded-md text-sm">Save</button>
        <button @click="showCreate = false" class="px-4 py-2 border rounded-md text-sm">Cancel</button>
      </div>
    </div>
  </div>

  <!-- Template Selector -->
  <TemplateSelector
    v-if="showTemplate"
    @close="showTemplate = false"
    @created="store.fetchSopList()"
  />
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useMonitorStore } from '../stores/monitor'
import TemplateSelector from '../components/TemplateSelector.vue'

const store = useMonitorStore()
const showCreate = ref(false)
const showTemplate = ref(false)
const editingId = ref(null)

const form = reactive({
  sop_id: '',
  name: '',
  version: '1.0',
  description: '',
  max_total_duration: 3600,
  steps: [],
})

function addStep() {
  form.steps.push({
    step_id: `step_${form.steps.length + 1}`,
    name: '',
    order: form.steps.length,
    rule: { expected_objects: [], min_confidence: 0.5, required_count: 1 },
  })
}

async function handleSave() {
  // Parse comma-separated objects
  for (const step of form.steps) {
    if (typeof step.rule.expected_objects === 'string') {
      step.rule.expected_objects = step.rule.expected_objects.split(',').map(s => s.trim()).filter(Boolean)
    }
  }
  await store.saveSop({ ...form })
  showCreate.value = false
  resetForm()
}

async function editSop(sopId) {
  const detail = await store.fetchSopDetail(sopId)
  Object.assign(form, detail)
  editingId.value = sopId
  showCreate.value = true
}

async function handleDelete(sopId) {
  if (confirm(`Delete SOP "${sopId}"?`)) {
    await store.deleteSop(sopId)
  }
}

function resetForm() {
  form.sop_id = ''
  form.name = ''
  form.version = '1.0'
  form.description = ''
  form.steps = []
  editingId.value = null
}

onMounted(() => store.fetchSopList())
</script>
