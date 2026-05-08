import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Activity, Eye, EyeOff, LogIn, Lock, User } from 'lucide-react'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'

export default function Login() {
  const [form, setForm] = useState({ username: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const { login, loading } = useAuth()

  const handleSubmit = (e) => {
    e.preventDefault()
    login(form)
  }

  return (
    <div className="min-h-screen hero-bg grid-pattern flex items-center justify-center px-4 py-8">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div 
            initial={{ y: -20, rotate: -5 }}
            animate={{ y: 0, rotate: 0 }}
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 glass-premium"
            style={{ background: 'linear-gradient(135deg, #00d4ff, #5c72ff)', boxShadow: '0 0 50px rgba(0,212,255,0.4)' }}
          >
            <Activity className="w-8 h-8 text-white" />
          </motion.div>
          <h1 className="text-3xl font-black text-white tracking-tight">Welcome Back</h1>
          <p className="text-sm text-slate-500 mt-2">Manage your cloud autonomy in one secure place</p>
        </div>

        {/* Card */}
        <div className="glass-premium rounded-3xl p-8 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/10 blur-3xl -mr-16 -mt-16" />
          
          <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
            <div>
              <label className="block text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-widest flex items-center gap-2">
                <User className="w-3 h-3 text-sky-400" /> Username
              </label>
              <input
                id="login-username"
                type="text"
                placeholder="Enter your username"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="input-premium"
                required
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 mb-2 uppercase tracking-widest flex items-center gap-2">
                <Lock className="w-3 h-3 text-sky-400" /> Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPass ? 'text' : 'password'}
                  placeholder="••••••••"
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
            </div>

            <button
              id="login-submit"
              type="submit"
              disabled={loading}
              className="btn-primary-glow w-full py-3.5 mt-2"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  Sign In to Dashboard
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-8">
            Don't have an account yet?{' '}
            <Link to="/register" className="text-sky-400 hover:text-sky-300 font-bold underline underline-offset-4 decoration-sky-400/30 hover:decoration-sky-400">
              Create one for free
            </Link>
          </p>

          {/* New account hint */}
          <div className="mt-8 pt-6 border-t border-white/5 flex items-start gap-3">
             <div className="w-8 h-8 rounded-lg bg-sky-500/10 flex items-center justify-center flex-shrink-0">
               <span className="text-lg">✨</span>
             </div>
             <p className="text-[11px] text-slate-500 leading-relaxed">
               <strong className="text-slate-400">Tip for reviewers:</strong> Create any account with a strong password to explore our simulated multi-cloud environment instantly.
             </p>
          </div>
        </div>

        <motion.p 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-center text-xs text-slate-600 mt-8"
        >
          <Link to="/" className="hover:text-slate-400 transition-colors">← Back to Homepage</Link>
        </motion.p>
      </motion.div>
    </div>
  )
}
