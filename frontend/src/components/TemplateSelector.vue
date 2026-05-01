<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
      <div class="p-4 border-b flex items-center justify-between">
        <h3 class="text-lg font-medium">Select Template</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600">&times;</button>
      </div>

      <div class="flex-1 overflow-y-auto p-4 space-y-3">
        <div
          v-for="template in templates"
          :key="template.sop_id"
          class="border rounded-lg p-4 hover:border-blue-300 hover:bg-blue-50 cursor-pointer transition-colors"
          @click="selectTemplate(template)"
        >
          <div class="font-medium text-sm">{{ template.name }}</div>
          <div class="text-xs text-gray-500 mt-1">
            {{ template.sop_id }} · {{ template.step_count }} steps
          </div>
        </div>
        <div v-if="templates.length === 0" class="text-center text-gray-400 py-8">
          No templates available.
        </div>
      </div>

      <!-- Selected Template Preview -->
      <div v-if="selected" class="p-4 border-t bg-gray-50">
        <div class="text-sm font-medium mb-2">{{ selected.name }}</div>
        <div class="text-xs text-gray-500 mb-3">{{ selected.description }}</div>
        <div class="flex items-center space-x-2">
          <input
            v-model="newName"
            class="flex-1 border rounded px-2 py-1 text-sm"
            placeholder="New SOP name"
          />
          <button
            @click="createFromTemplate"
            :disabled="!newName.trim()"
            class="px-3 py-1 bg-blue-600 text-white rounded text-sm disabled:opacity-50"
          >
            Create
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import http from '../api/http'

const emit = defineEmits(['close', 'created'])

const templates = ref([])
const selected = ref(null)
const newName = ref('')

async function fetchTemplates() {
  try {
    const { data } = await http.get('/api/sop/templates/list')
    templates.value = data.templates || []
  } catch {}
}

function selectTemplate(template) {
  selected.value = template
  newName.value = template.name + ' (Copy)'
}

async function createFromTemplate() {
  if (!selected.value || !newName.value.trim()) return
  const sopId = newName.value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  try {
    await http.post(`/api/sop/templates/${selected.value.sop_id}/use`, {
      sop_id: sopId,
      name: newName.value,
    })
    emit('created')
    emit('close')
  } catch (e) {
    console.error('Create from template failed:', e)
  }
}

onMounted(fetchTemplates)
</script>
