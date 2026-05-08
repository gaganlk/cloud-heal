import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Cloud, GitBranch, Brain, Zap, HeartPulse,
  Clock, LogOut, ChevronLeft, ChevronRight, Activity,
  ShieldCheck, Wifi, WifiOff, Radio, GitMerge, Search, Sparkles,
  DollarSign, Shield, Settings,
} from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAura } from '../aura/AuraContext'
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'

const NAV_GROUPS = [
  {
    label: 'Core',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard',        color: '#0ea5e9' },
      { to: '/connect',   icon: Cloud,         label: 'Cloud Connect',     color: '#a855f7' },
      { to: '/graph',     icon: GitBranch,     label: 'Topology Graph',    color: '#06b6d4' },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/prediction',  icon: Brain,       label: 'Risk Prediction',   color: '#f59e0b' },
      { to: '/propagation', icon: Zap,         label: 'Propagation Sim',   color: '#f97316' },
      { to: '/healing',     icon: HeartPulse,  label: 'Auto-Healing',      color: '#10b981' },
      { to: '/finops',      icon: DollarSign,  label: 'FinOps',            color: '#6366f1' },
      { to: '/security',    icon: Shield,      label: 'Security',          color: '#ec4899' },
    ],
  },
  {
    label: 'Advanced AIOps',
    items: [
      { to: '/war-room', icon: Radio,     label: 'War Room',          color: '#ef4444', badge: 'LIVE' },
      { to: '/drift',    icon: GitMerge,  label: 'Drift Detection',   color: '#8b5cf6' },
      { to: '/rca',      icon: Search,    label: 'Root Cause (RCA)',  color: '#fb923c' },
    ],
  },
  {
    label: 'Audit',
    items: [
      { to: '/timeline', icon: Clock,    label: 'Event Timeline', color: '#ec4899' },
      { to: '/settings', icon: Settings, label: 'Settings',        color: '#94a3b8' },
      { to: '/demo',     icon: Zap,      label: 'Demo Scenarios',  color: '#f59e0b', badge: 'DEMO' },
    ],
  },
]

export default function Sidebar({ isOpen, setIsOpen }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { connected } = useWebSocket()
  const { openChat, alertCount, auraState } = useAura()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <aside
      className={clsx(
        'flex flex-col h-full transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] relative z-40',
        'glass-dark border-r border-white/5 shadow-[20px_0_60px_rgba(0,0,0,0.6)]',
        'fixed inset-y-0 left-0 lg:relative', // Mobile overlay logic
        isOpen ? 'w-64 translate-x-0' : 'w-[72px] lg:translate-x-0 -translate-x-full lg:flex hidden',
      )}
    >
      {/* ── Logo ── */}
      <div className={clsx(
        'flex items-center gap-3 px-4 py-5 border-b border-white/5 flex-shrink-0',
        !isOpen && 'justify-center px-2',
      )}>
        <motion.div
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 relative overflow-hidden"
          style={{ background: 'linear-gradient(135deg, #020818 0%, #0d1528 100%)', border: '1px solid rgba(0,212,255,0.25)', boxShadow: '0 0 16px rgba(0,212,255,0.15)' }}
          whileHover={{ scale: 1.08, boxShadow: '0 0 24px rgba(0,212,255,0.35)' }}
        >
          <svg width="26" height="26" viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="logoGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#00d4ff"/>
                <stop offset="100%" stopColor="#a855f7"/>
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="1.2" result="coloredBlur"/>
                <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>
            {/* Cloud silhouette */}
            <path
              d="M7 17.5 C4.5 17.5 2.5 15.5 2.5 13 C2.5 10.8 4.1 9 6.2 8.7 C6.5 6.6 8.4 5 10.7 5 C12.3 5 13.7 5.8 14.6 7 C15.1 6.8 15.7 6.7 16.3 6.7 C18.7 6.7 20.7 8.7 20.7 11.1 C20.7 11.2 20.7 11.3 20.7 11.4 C22.3 11.8 23.5 13.2 23.5 14.9 C23.5 16.9 21.9 18.5 19.9 18.5 L7 18.5 Z"
              fill="none"
              stroke="url(#logoGrad)"
              strokeWidth="1.1"
              strokeLinejoin="round"
              filter="url(#glow)"
            />
            {/* Heartbeat / pulse line through cloud */}
            <polyline
              points="5,14 8,14 9.5,11 11,17 12.5,10 14,15.5 15.5,14 21,14"
              fill="none"
              stroke="url(#logoGrad)"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#glow)"
            />
            {/* Neural nodes at peaks */}
            <circle cx="9.5" cy="11" r="1.1" fill="#00d4ff" filter="url(#glow)"/>
            <circle cx="12.5" cy="10" r="1.1" fill="#a855f7" filter="url(#glow)"/>
          </svg>
        </motion.div>
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.2 }}
            >
              <h1 className="text-sm font-black text-white leading-tight tracking-tight">CloudHeal</h1>
              <p className="text-[9px] text-slate-500 font-mono tracking-widest uppercase">AIOps Platform</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Toggle button ── */}
      <motion.button
        id="sidebar-toggle"
        onClick={() => setIsOpen(!isOpen)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        className="absolute -right-3 top-[4.5rem] w-6 h-6 rounded-full bg-[#0d0d1a] border border-white/10
                   flex items-center justify-center text-slate-400 hover:text-white z-30
                   hover:border-sky-500/30 hover:shadow-[0_0_10px_rgba(14,165,233,0.2)] transition-all"
      >
        {isOpen ? <ChevronLeft className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </motion.button>

      {/* ── Nav Groups ── */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-4 custom-scrollbar">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {isOpen && (
              <p className="text-[9px] font-black text-slate-700 uppercase tracking-[0.25em] px-3 pb-2">
                {group.label}
              </p>
            )}
            <div className="space-y-0.5">
              {group.items.map(({ to, icon: Icon, label, color, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  id={`nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative',
                      isActive
                        ? 'bg-white/8 text-white'
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/4',
                      !isOpen && 'justify-center px-2',
                    )
                  }
                  title={!isOpen ? label : undefined}
                >
                  {({ isActive }) => (
                    <>
                      {/* Active indicator bar */}
                      {isActive && (
                        <motion.div
                          layoutId="activeBar"
                          className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full"
                          style={{ background: color }}
                        />
                      )}
                      <Icon
                        className="w-4.5 h-4.5 flex-shrink-0 transition-transform duration-200 group-hover:scale-110"
                        style={{ color: isActive ? color : undefined }}
                      />
                      {isOpen && (
                        <span className="truncate text-[12px] font-semibold tracking-tight flex items-center gap-2">
                          {label}
                          {badge && (
                            <span className="text-[7px] font-black tracking-widest px-1 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/20">
                              {badge}
                            </span>
                          )}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* ── Bottom section ── */}
      <div className="border-t border-white/5 p-2 space-y-1.5 flex-shrink-0">
        {/* Aura button */}
        <motion.button
          id="aura-sidebar-btn"
          onClick={openChat}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 relative',
            'bg-gradient-to-r from-sky-500/8 to-purple-500/8 hover:from-sky-500/15 hover:to-purple-500/15',
            'border border-sky-500/10 hover:border-sky-500/25 text-sky-400',
            !isOpen && 'justify-center px-2',
          )}
          title={!isOpen ? 'Aura AI' : undefined}
        >
          <Sparkles className="w-4 h-4 flex-shrink-0" />
          {isOpen && (
            <span className="text-[12px] font-black uppercase tracking-wider truncate">Aura AI</span>
          )}
          {alertCount > 0 && (
            <motion.span
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className={clsx(
                'w-4 h-4 bg-rose-500 rounded-full flex items-center justify-center text-[8px] font-black text-white flex-shrink-0',
                !isOpen ? 'absolute -top-1 -right-1' : 'ml-auto'
              )}
            >
              {alertCount}
            </motion.span>
          )}
        </motion.button>

        {/* WS Status */}
        {isOpen && (
          <div className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-lg text-[11px]',
            connected ? 'text-emerald-400 bg-emerald-400/5' : 'text-slate-500 bg-white/2',
          )}>
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span className="text-[10px] font-bold">{connected ? 'Live Feed' : 'Reconnecting...'}</span>
            {connected && (
              <motion.span
                className="w-1.5 h-1.5 bg-emerald-400 rounded-full ml-auto"
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
              />
            )}
          </div>
        )}

        {/* User card */}
        {isOpen && user && (
          <div className="flex items-center gap-2.5 px-3 py-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #00d4ff, #a855f7)' }}
            >
              {user.username?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-black text-white truncate">{user.username}</p>
              <p className="text-[9px] text-slate-500 truncate">{user.email}</p>
            </div>
          </div>
        )}

        {/* Logout */}
        <motion.button
          id="logout-btn"
          onClick={handleLogout}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl',
            'text-slate-500 hover:text-red-400 hover:bg-red-400/5 transition-all text-[12px] font-semibold',
            !isOpen && 'justify-center px-2',
          )}
          title={!isOpen ? 'Logout' : undefined}
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          {isOpen && <span className="truncate">Logout</span>}
        </motion.button>
      </div>
    </aside>
  )
}
