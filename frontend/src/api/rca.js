import API from './auth'

export const analyzeRCA = (resourceId) =>
  API.get(`/rca/analyze/${encodeURIComponent(resourceId)}`)

export const analyzeRCAPost = (resourceId) =>
  API.post('/rca/analyze', { resource_id: resourceId })
