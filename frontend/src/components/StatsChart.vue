<template>
  <div class="bg-white rounded-lg shadow-sm border">
    <div class="p-4 border-b flex items-center justify-between">
      <h3 class="font-medium">Detection Statistics</h3>
      <select v-model="timeRange" class="text-sm border rounded px-2 py-1">
        <option :value="15">Last 15 min</option>
        <option :value="30">Last 30 min</option>
        <option :value="60">Last 1 hour</option>
        <option :value="120">Last 2 hours</option>
      </select>
    </div>
    <div class="p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Timeline chart -->
      <div class="lg:col-span-2">
        <div ref="timelineChart" class="w-full h-48"></div>
      </div>
      <!-- Status pie chart -->
      <div>
        <div ref="statusChart" class="w-full h-48"></div>
      </div>
    </div>
    <!-- Summary cards -->
    <div class="px-4 pb-4 grid grid-cols-4 gap-3">
      <div class="bg-gray-50 rounded-md p-3 text-center">
        <div class="text-2xl font-bold text-blue-600">{{ summary.total_events }}</div>
        <div class="text-xs text-gray-500">Total Events</div>
      </div>
      <div class="bg-gray-50 rounded-md p-3 text-center">
        <div class="text-2xl font-bold text-green-600">{{ statusBreakdown.completed || 0 }}</div>
        <div class="text-xs text-gray-500">Completed</div>
      </div>
      <div class="bg-gray-50 rounded-md p-3 text-center">
        <div class="text-2xl font-bold text-yellow-600">{{ statusBreakdown.timeout || 0 }}</div>
        <div class="text-xs text-gray-500">Timeouts</div>
      </div>
      <div class="bg-gray-50 rounded-md p-3 text-center">
        <div class="text-2xl font-bold text-red-600">{{ statusBreakdown.error || 0 }}</div>
        <div class="text-xs text-gray-500">Errors</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const timelineChart = ref(null)
const statusChart = ref(null)
const timeRange = ref(30)
const summary = ref({ total_events: 0, unique_sops: 0, status_breakdown: {} })
const statusBreakdown = ref({})

let timelineInstance = null
let statusInstance = null

async function fetchData() {
  try {
    const [summaryRes, timelineRes, statsRes] = await Promise.all([
      axios.get('/api/stats/summary'),
      axios.get('/api/stats/timeline', { params: { minutes: timeRange.value } }),
      axios.get('/api/stats/detections', { params: { minutes: timeRange.value } }),
    ])

    summary.value = summaryRes.data
    statusBreakdown.value = summaryRes.data.status_breakdown || {}

    await nextTick()
    renderTimeline(timelineRes.data.timeline || [])
    renderStatusPie(summaryRes.data.status_breakdown || {})
  } catch {
    // API not available yet
  }
}

function renderTimeline(data) {
  if (!timelineChart.value) return
  if (!timelineInstance) {
    timelineInstance = echarts.init(timelineChart.value)
  }

  const times = data.map(d => {
    const date = new Date(d.time)
    return `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
  })
  const totals = data.map(d => d.total)

  timelineInstance.setOption({
    tooltip: { trigger: 'axis' },
    grid: { top: 10, right: 10, bottom: 20, left: 40 },
    xAxis: { type: 'category', data: times, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      data: totals,
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 },
      itemStyle: { color: '#3b82f6' },
    }],
  })
}

function renderStatusPie(data) {
  if (!statusChart.value) return
  if (!statusInstance) {
    statusInstance = echarts.init(statusChart.value)
  }

  const colorMap = {
    detected: '#3b82f6',
    completed: '#22c55e',
    timeout: '#eab308',
    error: '#ef4444',
    skipped: '#a3a3a3',
  }

  const pieData = Object.entries(data).map(([name, value]) => ({
    name,
    value,
    itemStyle: { color: colorMap[name] || '#6b7280' },
  }))

  statusInstance.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { fontSize: 10 },
      data: pieData,
    }],
  })
}

function handleResize() {
  timelineInstance?.resize()
  statusInstance?.resize()
}

watch(timeRange, fetchData)
onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  timelineInstance?.dispose()
  statusInstance?.dispose()
})
</script>
