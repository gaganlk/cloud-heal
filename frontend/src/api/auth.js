import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const API = axios.create({ baseURL: '/api' })

API.interceptors.request.use((config) => {
  const state = useAuthStore.getState()
  if (state.token) {
    config.headers.Authorization = `Bearer ${state.token}`
  }
  return config
})

API.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

export const registerUser = (data) => API.post('/auth/register', data)
export const loginUser = (data) => API.post('/auth/login', data)
export const getMe = () => API.get('/auth/me')

export default API
