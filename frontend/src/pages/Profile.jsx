import { useState, useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { User, Mail, Shield, Save, Loader2, AlertCircle } from 'lucide-react'
import API from '../api/auth'
import toast from 'react-hot-toast'
import { motion } from 'framer-motion'

export default function Profile() {
  const { user, token, setUser } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    bio: user?.bio || ''
  })

  useEffect(() => {
    if (user) {
      setFormData({
        full_name: user.full_name || '',
        email: user.email || '',
        bio: user.bio || ''
      })
    }
  }, [user])

  const handleUpdate = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await API.put('/auth/profile', formData)
      setUser(res.data)
      toast.success('Profile updated successfully!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Profile Settings</h1>
          <p className="text-slate-400">Manage your account information and preferences</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Col: Avatar & Identity */}
        <div className="md:col-span-1 space-y-6">
          <div className="glass-dark border border-white/5 rounded-2xl p-6 text-center">
            <div className="w-24 h-24 rounded-full mx-auto mb-4 flex items-center justify-center text-3xl font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #00d4ff, #a855f7)' }}
            >
              {user?.username?.[0]?.toUpperCase()}
            </div>
            <h3 className="text-lg font-semibold text-white">{user?.username}</h3>
            <p className="text-xs text-slate-500 uppercase tracking-wider mt-1">Administrator</p>
            <div className="mt-6 pt-6 border-t border-white/5 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Member since</span>
                <span className="text-slate-300">{user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Verification</span>
                <span className="text-emerald-400 font-medium">Verified</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Col: Form */}
        <div className="md:col-span-2">
          <form onSubmit={handleUpdate} className="glass-dark border border-white/5 rounded-2xl p-8 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400 uppercase">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition-all"
                    placeholder="Enter your full name"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400 uppercase">Email Address</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 pl-10 pr-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition-all"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 uppercase">Biography</label>
              <textarea
                value={formData.bio}
                onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                rows={4}
                className="w-full bg-white/5 border border-white/10 rounded-xl py-2.5 px-4 text-white placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition-all resize-none"
                placeholder="Tell us about your role..."
              />
            </div>

            <div className="pt-4 flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-sky-500 to-indigo-500 text-white font-semibold rounded-xl hover:shadow-[0_0_20px_rgba(14,165,233,0.3)] disabled:opacity-50 transition-all"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Changes
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Security Section Placeholder */}
      <div className="glass-dark border border-white/5 rounded-2xl p-8">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-amber-400/10 rounded-lg">
            <Shield className="w-5 h-5 text-amber-400" />
          </div>
          <h2 className="text-lg font-semibold text-white">Security & Access</h2>
        </div>
        <div className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 border-dashed">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-slate-500" />
            <div>
              <p className="text-sm font-medium text-white">Two-Factor Authentication</p>
              <p className="text-xs text-slate-500">Hardware key or authenticator app required</p>
            </div>
          </div>
          <button className="px-4 py-1.5 bg-white/5 hover:bg-white/10 text-white text-xs font-semibold rounded-lg transition-all">
            Enable 2FA
          </button>
        </div>
      </div>
    </motion.div>
  )
}
