import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url) {
  const data = ref(null)
  const connected = ref(false)
  let ws = null
  let reconnectTimer = null
  let retryDelay = 1000
  let retryCount = 0
  const MAX_RETRIES = 10
  let stopped = false

  function connect() {
    if (stopped) return

    const token = localStorage.getItem('token')
    if (!token) {
      console.warn('WebSocket: no auth token, skipping connect')
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = url || `${protocol}//${window.location.host}/ws`
    const wsUrl = `${baseUrl}?token=${encodeURIComponent(token)}`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      retryDelay = 1000
      retryCount = 0
      console.log('WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        data.value = JSON.parse(event.data)
      } catch {
        data.value = event.data
      }
    }

    ws.onclose = (event) => {
      connected.value = false

      // Auth failure — don't retry
      if (event.code === 4001) {
        console.warn('WebSocket auth failed, not retrying')
        return
      }

      if (!stopped && retryCount < MAX_RETRIES) {
        retryCount++
        console.log(`WebSocket disconnected, reconnecting in ${retryDelay}ms... (attempt ${retryCount}/${MAX_RETRIES})`)
        reconnectTimer = setTimeout(connect, retryDelay)
        retryDelay = Math.min(retryDelay * 2, 30000)
      }
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
    stopped = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { data, connected, send, disconnect }
}
