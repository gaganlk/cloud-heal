import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { registerUser, loginUser } from '../api/auth'
import toast from 'react-hot-toast'

export function useAuth() {
  const [loading, setLoading] = useState(false)
  const { setAuth, logout: storeLogout } = useAuthStore()
  const navigate = useNavigate()

  const register = async (data) => {
    setLoading(true)
    try {
      await registerUser(data)
      toast.success('Registration successful! Please verify your email.')
      navigate('/verify-otp', { state: { email: data.email } })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const login = async (data) => {
    setLoading(true)
    try {
      const res = await loginUser(data)
      
      if (res.data.status === 'otp_required') {
        toast.success('MFA Required: Please check your email for the verification code.')
        navigate('/verify-otp', { state: { email: res.data.email } })
        return
      }

      setAuth(res.data.access_token, res.data.user)
      toast.success(`Welcome back, ${res.data.user.username}! 👋`)
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Login failed')
      if (err.response?.status === 403) {
        navigate('/verify-otp', { state: { email: data.username.includes('@') ? data.username : null } })
      }
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    storeLogout()
    toast('Logged out', { icon: '👋' })
    navigate('/login')
  }

  return { register, login, logout, loading }
}
