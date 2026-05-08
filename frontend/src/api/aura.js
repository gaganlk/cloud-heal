import API from './auth'

// Send a chat message to Aura (RAG-enhanced)
export const chatWithAura = (data) => API.post('/aura/chat', data)

// Get current system context for RAG
export const getAuraContext = () => API.get('/aura/context')

// Get Aura's interpretation of a natural language command
export const auraCommand = (data) => API.post('/aura/command', data)
