<template>
  <div class="space-y-6">
    <!-- Top: Video + SOP Progress + Alerts -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Video Stream (takes 2 columns) -->
      <div class="lg:col-span-2">
        <VideoStream />
      </div>

      <!-- Right sidebar: SOP Progress + Alerts -->
      <div class="space-y-6">
        <SopProgress />
        <AlertPanel />
      </div>
    </div>

    <!-- Bottom: Statistics Charts -->
    <StatsChart />
  </div>
</template>

<script setup>
import { onMounted, watch } from 'vue'
import VideoStream from '../components/VideoStream.vue'
import SopProgress from '../components/SopProgress.vue'
import AlertPanel from '../components/AlertPanel.vue'
import StatsChart from '../components/StatsChart.vue'
import { useWebSocket } from '../composables/useWebSocket'
import { useMonitorStore } from '../stores/monitor'

const store = useMonitorStore()
const { data, connected } = useWebSocket()

// Sync WebSocket state to store
watch(connected, (val) => store.setWsConnected(val))
watch(data, (msg) => { if (msg) store.handleWsMessage(msg) })

onMounted(async () => {
  await Promise.all([
    store.fetchStatus(),
    store.fetchAlerts(),
    store.fetchSopList(),
  ])
})
</script>
