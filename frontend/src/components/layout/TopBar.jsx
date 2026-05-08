import { Bell, Menu, Search, Zap } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useState, useEffect, useMemo } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { LogOut, User as UserIcon, Settings, ChevronDown } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import NotificationPanel from '../notifications/NotificationPanel'
import clsx from 'clsx'

const PAGE_TITLES = {
  '/dashboard':   { title: 'Dashboard',            sub: 'Real-time cloud overview' },
  '/connect':     { title: 'Cloud Connect',         sub: 'Manage cloud credentials' },
  '/graph':       { title: 'Dependency Graph',      sub: 'Interactive service map' },
  '/prediction':  { title: 'Failure Prediction',    sub: 'AI-powered risk analysis' },
  '/propagation': { title: 'Propagation Simulator', sub: 'Cascade failure analysis' },
  '/healing':     { title: 'Auto-Healing Engine',   sub: 'Intelligent remediation' },
  '/timeline':    { title: 'Event Timeline',        sub: 'Audit log & history' },
  '/war-room':    { title: 'War Room',              sub: 'AIOps command center — live' },
  '/drift':       { title: 'Drift Detection',       sub: 'Desired state compliance engine' },
  '/rca':         { title: 'Root Cause Analysis',   sub: 'AI-powered fault attribution' },
  '/finops':      { title: 'FinOps Intelligence',   sub: 'Cost anomaly & cloud spend' },
  '/security':    { title: 'Security Posture',      sub: 'Risk findings & compliance' },
  '/settings':    { title: 'System Settings',       sub: 'Platform configuration' },
  '/profile':     { title: 'Account Profile',       sub: 'User & tenant management' },
  '/demo':        { title: 'Demo Scenarios',        sub: 'Live portfolio walkthrough' },
}

export default function TopBar({ onMenuClick, sidebarOpen }) {
  const { user, logout } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const { connected, lastMessage } = useWebSocket()
  const [liveMetrics, setLiveMetrics] = useState(null)
  const [alerts, setAlerts] = useState(0)
  const [notifOpen, setNotifOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  useEffect(() => {
    if (lastMessage?.type === 'metrics_update') {
      setLiveMetrics(lastMessage.data)
      setAlerts(lastMessage.data?.active_alerts || 0)
    }
  }, [lastMessage])

  const pageInfo = PAGE_TITLES[location.pathname] || { title: 'CloudHeal', sub: '' }

  return (
    <header className="h-20 flex items-center px-8 border-b border-white/5 glass-dark flex-shrink-0 relative z-[100]">
      <div className="absolute top-0 right-0 w-64 h-full bg-sky-500/5 blur-[80px] -z-10" />
      
      {/* Left */}
      <button
        id="menu-toggle"
        onClick={onMenuClick}
        className="w-10 h-10 flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-all mr-6 lg:hidden"
      >
        <Menu className="w-5 h-5" />
      </button>

      <div className="flex flex-col">
        <h2 className="text-lg font-black text-white tracking-tight leading-none mb-1">{pageInfo.title}</h2>
        {pageInfo.sub && <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{pageInfo.sub}</p>}
      </div>

      <div className="flex-1" />

      {/* Live status hub */}
      <div className="flex items-center gap-6">
        {/* Metrics stack */}
        {liveMetrics && (
          <div className="hidden lg:flex items-center gap-2 bg-white/[0.03] p-1 rounded-2xl border border-white/5 shadow-inner">
            <MetricPill label="CPU" value={`${liveMetrics.cpu?.toFixed(1)}%`} color="text-sky-400" />
            <MetricPill label="MEM" value={`${liveMetrics.memory?.toFixed(1)}%`} color="text-purple-400" />
            <MetricPill label="HEALTH" value={`${liveMetrics.health_score?.toFixed(0)}%`} color="text-emerald-400" />
          </div>
        )}

        {/* Connectivity */}
        <div className={clsx(
          'hidden sm:flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all duration-500',
          connected ? 'bg-emerald-500/5 text-emerald-400 border-emerald-500/20' : 'bg-white/5 text-slate-500 border-white/5'
        )}>
          <span className={clsx('w-2 h-2 rounded-full', connected ? 'bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)] animate-pulse' : 'bg-slate-600')} />
          {connected ? 'Sync Connected' : 'Engine Offline'}
        </div>

        {/* Alerts & Notifications */}
        <div className="relative">
          <button
            id="alerts-btn"
            onClick={() => setNotifOpen(!notifOpen)}
            className={clsx(
              'w-10 h-10 flex items-center justify-center rounded-xl transition-all relative',
              notifOpen ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30' : 'text-slate-400 hover:text-white hover:bg-white/5'
            )}
          >
            <Bell className="w-5 h-5" />
            {alerts > 0 && (
              <span className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-[#0d0d18] animate-bounce" />
            )}
          </button>
          <NotificationPanel isOpen={notifOpen} onClose={() => setNotifOpen(false)} />
        </div>

        {/* User profile dropdown */}
        {user && (
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-3 p-1 rounded-2xl hover:bg-white/5 transition-all outline-none"
            >
              <div 
                className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-black text-white shadow-xl border border-white/10"
                style={{ background: 'linear-gradient(135deg, #00d4ff, #a855f7)' }}
              >
                {user.username?.[0]?.toUpperCase()}
              </div>
              <div className="hidden xl:block text-left mr-1">
                <p className="text-xs font-bold text-white leading-tight truncate max-w-[100px]">{user.username}</p>
                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Admin</p>
              </div>
              <ChevronDown className={clsx('w-4 h-4 text-slate-600 transition-transform duration-300', userMenuOpen && 'rotate-180')} />
            </button>

            <AnimatePresence>
              {userMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                  <motion.div
                    initial={{ opacity: 0, y: 15, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 15, scale: 0.95 }}
                    className="absolute top-full right-0 mt-3 w-56 glass-premium border border-white/10 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.8)] z-[110] overflow-hidden"
                  >
                    <div className="p-4 bg-white/[0.02] border-b border-white/5">
                      <p className="text-xs font-black text-white truncate mb-0.5">{user.full_name || user.username}</p>
                      <p className="text-[10px] text-slate-500 font-medium truncate">{user.email}</p>
                    </div>
                    <div className="p-2">
                      <MenuAction to="/profile" icon={UserIcon} label="Account Profile" onClick={() => setUserMenuOpen(false)} />
                      <MenuAction to="/settings" icon={Settings} label="System Settings" onClick={() => setUserMenuOpen(false)} />
                      <div className="h-px bg-white/5 my-2" />
                      <button
                        onClick={() => { logout(); navigate('/login'); }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-bold text-red-400 hover:bg-red-500/10 transition-all text-left"
                      >
                        <LogOut className="w-4 h-4" /> Sign Out
                      </button>
                    </div>
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </header>
  )
}

function MetricPill({ label, value, color }) {
  return (
    <div className="flex flex-col px-3 py-1.5 min-w-[70px]">
      <span className="text-[9px] font-black text-slate-500 mb-0.5 tracking-tighter uppercase">{label}</span>
      <span className={clsx('text-xs font-black font-mono leading-none', color)}>{value}</span>
    </div>
  )
}

function MenuAction({ to, icon: Icon, label, onClick }) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-bold text-slate-400 hover:text-white hover:bg-white/5 transition-all"
    >
      <Icon className="w-4 h-4" /> {label}
    </Link>
  )
}
