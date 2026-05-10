import type { DownloadWSMessage } from '@/types'
import { useServerStore } from '@/stores/server'

type DownloadWSHandler = (msg: DownloadWSMessage) => void

let ws: WebSocket | null = null
let handlers: Set<DownloadWSHandler> = new Set()
let reconnectTimer: number | null = null
let reconnectAttempts = 0
const MAX_RECONNECT = 5
const RECONNECT_DELAY = 3000

function getWSUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const serverStore = useServerStore()
  const activeUrl = serverStore.activeUrl
  if (activeUrl) {
    const base = activeUrl.replace(/^https?:/, proto)
    return `${base}/ws/download`
  }
  return `${proto}//${location.host}/ws/download`
}

export function connectDownloadWS(): void {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

  ws = new WebSocket(getWSUrl())

  ws.onopen = () => {
    reconnectAttempts = 0
  }

  ws.onmessage = (event) => {
    try {
      const msg: DownloadWSMessage = JSON.parse(event.data)
      handlers.forEach((h) => h(msg))
    } catch {
      // skip non-JSON
    }
  }

  ws.onclose = () => {
    ws = null
    scheduleReconnect()
  }

  ws.onerror = () => {
    ws?.close()
  }
}

export function disconnectDownloadWS(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  reconnectAttempts = 0
  ws?.close()
  ws = null
}

export function onDownloadMessage(handler: DownloadWSHandler): () => void {
  handlers.add(handler)
  connectDownloadWS()
  return () => {
    handlers.delete(handler)
    if (handlers.size === 0) disconnectDownloadWS()
  }
}

function scheduleReconnect(): void {
  if (reconnectAttempts >= MAX_RECONNECT) return
  reconnectTimer = window.setTimeout(() => {
    reconnectAttempts++
    connectDownloadWS()
  }, RECONNECT_DELAY * reconnectAttempts)
}
