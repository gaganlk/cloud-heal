import API from './auth'

export const addCredential = (data) => API.post('/credentials/', data)
export const listCredentials = () => API.get('/credentials/')
export const deleteCredential = (id) => API.delete(`/credentials/${id}`)
export const validateCredential = (id) => API.post(`/credentials/${id}/validate`)
