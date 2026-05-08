import API from './auth'

export const triggerScan = (credId) => API.post(`/scanner/scan/${credId}`)
export const getResources = (credId) => API.get(`/scanner/resources/${credId}`)
export const getAllResources = () => API.get('/scanner/all-resources')
export const getScanStatus = (credId) => API.get(`/scanner/status/${credId}`)
