import API from './auth'

export const getGraph = (credId) => API.get(`/graph/${credId}`)
export const getCombinedGraph = () => API.get('/graph/all/combined')
export const getAllPredictions = () => API.get('/prediction/all')
export const getResourcePrediction = (resourceId) =>
  API.get(`/prediction/resource/${encodeURIComponent(resourceId)}`)
export const simulatePropagation = (data) => API.post('/propagation/simulate', data)
export const getPropagationResources = (credId) =>
  API.get(`/propagation/resources/${credId}`)
