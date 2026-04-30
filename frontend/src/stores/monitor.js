import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import http from '../api/http'

export const useMonitorStore = defineStore('monitor', () => {
  // State
  const wsConnected = ref(false)
  const wsData = ref(null)
  const activeSops = ref([])
  const alerts = ref([])
  const sopList = ref([])

  // Detection stats for charts (last N events)
  const detectionHistory = ref([])
  const MAX_HISTORY = 200

  // WebSocket message handler
  function handleWsMessage(msg) {
    wsData.value = msg

    if (msg.type === 'heartbeat') {
      // keep-alive
    } else if (msg.type === 'sop_event') {
      const payload = msg.payload

      // Update active SOP state — refresh from server
      fetchStatus()

      // Track detection history for charts
      detectionHistory.value.unshift({
        ...payload,
        received_at: new Date().toISOString(),
      })
      if (detectionHistory.value.length > MAX_HISTORY) {
        detectionHistory.value.pop()
      }
    } else if (msg.type === 'alert') {
      // Prepend new alert, avoid duplicates
      const exists = alerts.value.some(a => a.alert_id === msg.payload.alert_id)
      if (!exists) {
        alerts.value.unshift(msg.payload)
        if (alerts.value.length > 100) alerts.value.pop()
      }
    }
  }

  // REST API calls
  async function fetchSopList() {
    const { data } = await http.get('/api/sop/list')
    sopList.value = data.sops
  }

  async function fetchSopDetail(sopId) {
    const { data } = await http.get(`/api/sop/${sopId}`)
    return data
  }

  async function saveSop(sopData) {
    await http.post('/api/sop/', sopData)
    await fetchSopList()
  }

  async function deleteSop(sopId) {
    await http.delete(`/api/sop/${sopId}`)
    await fetchSopList()
  }

  async function fetchStatus() {
    const { data } = await http.get('/api/monitor/status')
    activeSops.value = data.active_sops || []
  }

  async function fetchAlerts() {
    const { data } = await http.get('/api/monitor/alerts')
    alerts.value = data.alerts || []
  }

  async function fetchRecords(limit = 100) {
    const { data } = await http.get('/api/monitor/records', { params: { limit } })
    return data.records || []
  }

  function setWsConnected(val) {
    wsConnected.value = val
  }

  return {
    wsConnected,
    wsData,
    activeSops,
    alerts,
    sopList,
    detectionHistory,
    handleWsMessage,
    setWsConnected,
    fetchSopList,
    fetchSopDetail,
    saveSop,
    deleteSop,
    fetchStatus,
    fetchAlerts,
    fetchRecords,
  }
})
