import API from './auth'

export const triggerHealing = (data) => API.post('/healing/trigger', data)
export const autoHeal = (data) => API.post('/healing/auto-heal', data)
export const getHealingActions = () => API.get('/healing/actions')
export const getStats = () => API.get('/dashboard/stats')
export const getMetrics = () => API.get('/dashboard/metrics')
export const getTimeline = (limit = 50) =>
  API.get(`/dashboard/timeline?limit=${limit}`)

export const approveHealing = (id) => API.post(`/healing/${id}/approve`)
export const rejectHealing = (id) => API.post(`/healing/${id}/reject`)
