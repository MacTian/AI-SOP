import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url) {
  const data = ref(null)
  const connected = ref(false)
  let ws = null
  let reconnectTimer = null

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = url || `${protocol}//${window.location.host}/ws`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        data.value = JSON.parse(event.data)
      } catch {
        data.value = event.data
      }
    }

    ws.onclose = () => {
      connected.value = false
      console.log('WebSocket disconnected, reconnecting in 3s...')
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = (err) => {
      console.error('WebSocket error:', err)
      ws.close()
    }
  }

  function send(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof message === 'string' ? message : JSON.stringify(message))
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { data, connected, send, disconnect }
}
