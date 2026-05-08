import { useWebSocketStore } from '../store/websocketStore'

/**
 * Modernized useWebSocket hook that taps into the global WebSocket session.
 * This prevents individual components from opening redundant connections.
 */
export function useWebSocket() {
  const { connected, lastMessage, sendMessage } = useWebSocketStore()

  return { connected, lastMessage, sendMessage }
}
