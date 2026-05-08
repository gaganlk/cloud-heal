import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ShieldCheck, ArrowLeft, Loader2, Mail, RefreshCw } from 'lucide-react'
import API from '../api/auth'
import toast from 'react-hot-toast'
import { useAuthStore } from '../store/authStore'

export default function VerifyOTP() {
  const navigate = useNavigate()
  const location = useLocation()
  const email = location.state?.email || ''

  const [otp, setOtp] = useState(['', '', '', '', '', ''])
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [timer, setTimer] = useState(60)

  const { setAuth } = useAuthStore()

  useEffect(() => {
    if (!email) {
      toast.error('Session expired. Please register again.')
      navigate('/register')
    }
  }, [email, navigate])

  useEffect(() => {
    let interval = null
    if (timer > 0) {
      interval = setInterval(() => setTimer(prev => prev - 1), 1000)
    }
    return () => clearInterval(interval)
  }, [timer])

  const handleChange = (index, value) => {
    if (isNaN(value)) return
    const newOtp = [...otp]
    newOtp[index] = value.substring(value.length - 1)
    setOtp(newOtp)

    // Auto-focus next input
    if (value && index < 5) {
      document.getElementById(`otp-${index + 1}`).focus()
    }
  }

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      document.getElementById(`otp-${index - 1}`).focus()
    }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    const fullOtp = otp.join('')
    if (fullOtp.length < 6) return toast.error('Please enter all 6 digits')

    setLoading(true)
    try {
      const res = await API.post('/auth/verify-otp', { email, otp: fullOtp })

      if (res.data && res.data.access_token) {
        setAuth(res.data.access_token, res.data.user)
        toast.success(`Welcome, ${res.data.user.username}!`)
        navigate('/dashboard')
      } else {
        toast.success('Email verified! You can now login.')
        navigate('/login')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (timer > 0) return
    setResending(true)
    try {
      await API.post(`/auth/resend-otp`, { email })
      toast.success('New code sent to your email!')
      setTimer(60)
    } catch (err) {
      toast.error('Failed to resend code')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#020617] flex items-center justify-center p-6 relative overflow-hidden">
      {/* Background Blobs */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-sky-500/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-indigo-500/10 blur-[120px] rounded-full" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md w-full"
      >
        <div className="glass-premium rounded-[2.5rem] p-10 border border-white/5 relative z-10">
          <div className="text-center mb-10">
            <div className="w-16 h-16 bg-sky-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6 border border-sky-500/20">
              <ShieldCheck className="w-8 h-8 text-sky-400" />
            </div>
            <h1 className="text-3xl font-black text-white tracking-tighter mb-2">Verify Email</h1>
            <p className="text-slate-500 text-sm font-medium flex items-center justify-center gap-2">
              <Mail className="w-4 h-4" /> We've sent a code to <span className="text-slate-300">{email}</span>
            </p>
          </div>

          <form onSubmit={handleVerify} className="space-y-8">
            <div className="flex justify-between gap-2">
              {otp.map((digit, i) => (
                <input
                  key={i}
                  id={`otp-${i}`}
                  type="text"
                  inputMode="numeric"
                  value={digit}
                  onChange={(e) => handleChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  className="w-12 h-16 text-center text-2xl font-black bg-white/5 border border-white/10 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition-all"
                  maxLength={1}
                  required
                />
              ))}
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary-glow !py-4 text-sm font-black uppercase tracking-widest flex items-center justify-center gap-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Confirm Verification'}
            </button>

            <div className="text-center space-y-4">
              <button
                type="button"
                onClick={handleResend}
                disabled={timer > 0 || resending}
                className="text-xs font-black uppercase tracking-widest text-slate-500 hover:text-sky-400 disabled:opacity-50 transition-colors flex items-center justify-center gap-2 mx-auto"
              >
                {resending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                {timer > 0 ? `Resend code in ${timer}s` : 'Resend Verification Code'}
              </button>

              <button
                type="button"
                onClick={() => navigate('/register')}
                className="text-xs font-bold text-slate-600 hover:text-white flex items-center justify-center gap-1 mx-auto transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Use different email
              </button>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  )
}