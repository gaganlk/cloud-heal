import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Activity, Eye, EyeOff, UserPlus, CheckCircle2, XCircle, ShieldCheck } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'


export default function Register() {
  const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '' })
  const [showPass, setShowPass] = useState(false)
  const { register, loading } = useAuth()

  const passwordStrength = useMemo(() => {
    const p = form.password
    let score = 0
    if (!p) return 0
    if (p.length >= 8) score += 20
    if (/[A-Z]/.test(p)) score += 20
    if (/[a-z]/.test(p)) score += 20
    if (/[0-9]/.test(p)) score += 20
    if (/[@$!%*?&]/.test(p)) score += 20
    return score
  }, [form.password])

  const strengthLabel = useMemo(() => {
    if (passwordStrength <= 20) return { label: 'Weak', color: 'bg-red-500' }
    if (passwordStrength <= 40) return { label: 'Fair', color: 'bg-orange-500' }
    if (passwordStrength <= 60) return { label: 'Good', color: 'bg-yellow-500' }
    if (passwordStrength <= 80) return { label: 'Strong', color: 'bg-blue-500' }
    return { label: 'Excellent', color: 'bg-emerald-500' }
  }, [passwordStrength])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (form.password !== form.confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    if (passwordStrength < 100) {
      toast.error('Password is too weak. Please follow all security rules.')
      return
    }
    const { confirmPassword, ...registerData } = form
    register(registerData)
  }

  return (
    <div className="min-h-screen hero-bg grid-pattern flex items-center justify-center px-4 py-12">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div 
            initial={{ y: -20 }}
            animate={{ y: 0 }}
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 glass-premium"
            style={{ background: 'linear-gradient(135deg, #a855f7, #ec4899)', boxShadow: '0 0 50px rgba(168,85,247,0.4)' }}
          >
            <Activity className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-black text-white tracking-tight">Join CloudHeal</h1>
          <p className="text-sm text-slate-500 mt-2">The future of autonomous cloud resilience</p>
        </div>

        {/* Card */}
        <div className="glass-premium rounded-3xl p-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 blur-3xl -mr-16 -mt-16" />
          
          <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider">Username</label>
              <input
                id="register-username"
                type="text"
                placeholder="Choose a professional handle"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="input-premium"
                required
                minLength={3}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider">Work Email</label>
              <input
                id="register-email"
                type="email"
                placeholder="admin@yourcompany.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="input-premium"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider">Secure Password</label>
              <div className="relative">
                <input
                  id="register-password"
                  type={showPass ? 'text' : 'password'}
                  placeholder="Create a strong password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="input-premium pr-12"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                >
                  {showPass ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>

              {/* Strength Meter */}
              <div className="pt-2">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[10px] font-bold text-slate-500 uppercase">Password Security</span>
                  <span className={clsx('text-[10px] font-bold uppercase', strengthLabel.color.replace('bg-', 'text-'))}>
                    {strengthLabel.label}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden flex gap-1">
                  {[20, 40, 60, 80, 100].map((step) => (
                    <div 
                      key={step}
                      className={clsx(
                        'h-full flex-1 transition-all duration-500 rounded-full',
                        passwordStrength >= step ? strengthLabel.color : 'bg-white/5'
                      )}
                    />
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-3">
                  <Rule met={form.password.length >= 8} label="8+ Characters" />
                  <Rule met={/[A-Z]/.test(form.password)} label="Uppercase" />
                  <Rule met={/[a-z]/.test(form.password)} label="Lowercase" />
                  <Rule met={/[0-9]/.test(form.password)} label="Number" />
                  <Rule met={/[@$!%*?&]/.test(form.password)} label="Special (@$!%*?&)" />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider">Confirm Password</label>
              <input
                id="register-confirm"
                type="password"
                placeholder="Repeat your password"
                value={form.confirmPassword}
                onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
                className={clsx(
                  'input-premium',
                  form.confirmPassword && (form.password === form.confirmPassword ? 'border-emerald-500/30' : 'border-red-500/30')
                )}
                required
              />
            </div>

            <button
              id="register-submit"
              type="submit"
              disabled={loading}
              className="btn-primary-glow w-full py-3.5 mt-4"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <UserPlus className="w-5 h-5" />
                  Create Your Free Account
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-8">
            Already a member?{' '}
            <Link to="/login" className="text-sky-400 hover:text-sky-300 font-bold underline underline-offset-4 decoration-sky-400/30 hover:decoration-sky-400">
              Sign in here
            </Link>
          </p>
        </div>

        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center text-xs text-slate-600 mt-8"
        >
          <Link to="/" className="hover:text-slate-400 transition-colors">← Return to Landing Page</Link>
        </motion.p>
      </motion.div>
    </div>
  )
}

function Rule({ met, label }) {
  return (
    <div className={clsx('flex items-center gap-1.5 transition-colors', met ? 'text-emerald-400' : 'text-slate-600')}>
      {met ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      <span className="text-[10px] font-medium">{label}</span>
    </div>
  )
}
