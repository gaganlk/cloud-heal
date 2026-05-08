import { create } from 'zustand'

const MAX_RECONNECT_ATTEMPTS = 15

export const useWebSocketStore = create((set, get) => ({
  socket: null,
  connected: false,
  lastMessage: null,
  clientId: null,
  reconnectAttempts: 0,
  reconnectTimer: null,

  setClientId: (id) => set({ clientId: id }),

  connect: () => {
    const { socket, clientId } = get()

    if ((socket && socket.readyState <= 1) || !clientId) return

    try {
      const host = window.location.hostname
      const rawPort = window.location.port
      const portStr = rawPort ? `:${rawPort}` : ''
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${host}${portStr}/ws/${clientId}`

      console.log(`[WS] Connecting: ${url}`)
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log(`[WS] Connected: ${clientId}`)
        const { reconnectTimer } = get()
        if (reconnectTimer) clearTimeout(reconnectTimer)
        set({ connected: true, reconnectAttempts: 0, reconnectTimer: null })
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          set({ lastMessage: data })
        } catch {
          set({ lastMessage: { raw: event.data } })
        }
      }

      ws.onclose = (event) => {
        set({ connected: false, socket: null })

        if (!event.wasClean) {
          const { reconnectAttempts } = get()

          if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            console.error(`[WS] Max reconnect attempts reached. Reload the page to reconnect.`)
            return
          }

          const backoff = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
          console.warn(`[WS] Reconnecting in ${backoff}ms (attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})`)

          const timer = setTimeout(() => get().connect(), backoff)
          set({ reconnectAttempts: reconnectAttempts + 1, reconnectTimer: timer })
        }
      }

      ws.onerror = (error) => {
        console.error(`[WS] Error. ReadyState: ${error.target?.readyState}`)
        set({ connected: false })
      }

      set({ socket: ws })
    } catch (error) {
      console.error('[WS] Initialization failed:', error)
    }
  },

  disconnect: () => {
    const { socket, reconnectTimer } = get()
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (socket) {
      if (socket.readyState < 2) socket.close()
      set({ socket: null, connected: false, reconnectAttempts: 0, reconnectTimer: null })
    }
  },

  // Force reconnect — resets attempt counter (for manual "reconnect" buttons)
  forceReconnect: () => {
    const { socket, reconnectTimer } = get()
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (socket && socket.readyState < 2) socket.close()
    set({ socket: null, connected: false, reconnectAttempts: 0, reconnectTimer: null })
    setTimeout(() => get().connect(), 100)
  },

  sendMessage: (message) => {
    const { socket, connected } = get()
    if (socket && connected && socket.readyState === 1) {
      socket.send(JSON.stringify(message))
    }
  },
}))

// ── Page Visibility Reconnect ─────────────────────────────────────────────────
// When a tab returns from hidden state the WS may be stale (common during demos
// when presenters switch windows). Re-check and reconnect if needed.
if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      const store = useWebSocketStore.getState()
      const { socket, connected, clientId } = store
      const isStale = !socket || socket.readyState > 1 || !connected
      if (isStale && clientId) {
        console.log('[WS] Tab visible — checking connection...')
        store.connect()
      }
    }
  })
}