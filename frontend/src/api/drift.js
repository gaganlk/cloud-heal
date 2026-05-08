import API from './auth'

export const getDriftStatus = () => API.get('/drift/status')
export const triggerDriftScan = () => API.post('/drift/scan')
export const snapshotDesiredState = (resourceId, state) =>
  API.post(`/drift/snapshot/${encodeURIComponent(resourceId)}`, { resource_id: resourceId, state })
export const getDesiredState = (resourceId) =>
  API.get(`/drift/snapshot/${encodeURIComponent(resourceId)}`)
export const deleteSnapshot = (resourceId) =>
  API.delete(`/drift/snapshot/${encodeURIComponent(resourceId)}`)
