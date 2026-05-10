import { ref, readonly } from 'vue'
import { useServerStore } from '@/stores/server'

type WSMessageHandler = (data: any) => void

let ws: WebSocket | null = null
const handlers = new Map<string, Set<WSMessageHandler>>()
const wsConnected = ref(false)
let reconnectAttempts = 0
const MAX_RECONNECT = 10
const RECONNECT_DELAY = 3000
let reconnectTimer: number | null = null
let heartbeatTimer: number | null = null

function getUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const serverStore = useServerStore()
  const activeUrl = serverStore.activeUrl
  if (activeUrl) {
    const base = activeUrl.replace(/^https?:/, proto)
    return `${base}/ws/monitor`
  }
  return `${proto}//${location.host}/ws/monitor`
}

function connect() {
  if (ws && ws.readyState === WebSocket.OPEN) return
  const url = getUrl()

  ws = new WebSocket(url)

  ws.onopen = () => {
    wsConnected.value = true
    reconnectAttempts = 0
    startHeartbeat()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const msgType = data.type || 'unknown'
      const typeHandlers = handlers.get(msgType)
      if (typeHandlers) {
        typeHandlers.forEach((h) => h(data))
      }
      const allHandlers = handlers.get('*')
      if (allHandlers) {
        allHandlers.forEach((h) => h(data))
      }
    } catch {}
  }

  ws.onclose = () => {
    wsConnected.value = false
    stopHeartbeat()
    scheduleReconnect()
  }

  ws.onerror = () => {
    wsConnected.value = false
    stopHeartbeat()
  }
}

function disconnect() {
  stopHeartbeat()
  clearReconnectTimer()
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
  wsConnected.value = false
}

function scheduleReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT) return
  clearReconnectTimer()
  reconnectTimer = window.setTimeout(() => {
    reconnectAttempts++
    connect()
  }, RECONNECT_DELAY * Math.min(reconnectAttempts, 5))
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function startHeartbeat() {
  heartbeatTimer = window.setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }, 30000)
}

function stopHeartbeat() {
  if (heartbeatTimer !== null) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

export function useMonitorWS() {
  function subscribe(type: string, handler: WSMessageHandler): () => void {
    if (!handlers.has(type)) {
      handlers.set(type, new Set())
    }
    handlers.get(type)!.add(handler)

    connect()

    return () => {
      const typeHandlers = handlers.get(type)
      if (typeHandlers) {
        typeHandlers.delete(handler)
        if (typeHandlers.size === 0) {
          handlers.delete(type)
        }
      }
      if (handlers.size === 0) {
        disconnect()
      }
    }
  }

  return {
    subscribe,
    connected: readonly(wsConnected),
  }
}
