import { createContext, useContext, useState, useCallback, useRef } from 'react'

const AuraContext = createContext(null)

export const AURA_STATES = {
  IDLE: 'idle',
  THINKING: 'thinking',
  HAPPY: 'happy',
  ALERT: 'alert',
  SPEAKING: 'speaking',
}

export function AuraProvider({ children }) {
  const [isOpen, setIsOpen] = useState(false)
  const [auraState, setAuraState] = useState(AURA_STATES.IDLE)
  const [alertCount, setAlertCount] = useState(0)
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'aura',
      content: "👋 Hi! I'm **Aura**, your AI healing companion. I have real-time access to your cloud infrastructure. Ask me anything — like *\"show me degraded resources\"* or *\"explain the last healing action\"*.",
      timestamp: new Date(),
    },
  ])
  const stateTimerRef = useRef(null)

  const transitionState = useCallback((state, durationMs = 3000) => {
    setAuraState(state)
    if (stateTimerRef.current) clearTimeout(stateTimerRef.current)
    if (state !== AURA_STATES.IDLE) {
      stateTimerRef.current = setTimeout(() => setAuraState(AURA_STATES.IDLE), durationMs)
    }
  }, [])

  const openChat = useCallback(() => {
    setIsOpen(true)
    setAlertCount(0)
  }, [])

  const closeChat = useCallback(() => setIsOpen(false), [])

  const addMessage = useCallback((msg) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), timestamp: new Date(), ...msg },
    ])
  }, [])

  const triggerAlert = useCallback(() => {
    setAlertCount((c) => c + 1)
    transitionState(AURA_STATES.ALERT, 5000)
  }, [transitionState])

  return (
    <AuraContext.Provider
      value={{
        isOpen, openChat, closeChat,
        auraState, transitionState,
        alertCount, triggerAlert,
        messages, addMessage, setMessages,
      }}
    >
      {children}
    </AuraContext.Provider>
  )
}

export const useAura = () => {
  const ctx = useContext(AuraContext)
  if (!ctx) throw new Error('useAura must be used inside AuraProvider')
  return ctx
}
