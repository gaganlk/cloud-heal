import { useEffect, useRef, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Terminal, Activity, Zap, ShieldAlert, HeartPulse, Clock,
  RefreshCw, Wifi, WifiOff, AlertTriangle, CheckCircle2,
  Radio, TrendingUp, BarChart3, Brain, Maximize2,
} from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'
import { getStats, getTimeline, getHealingActions, approveHealing, rejectHealing } from '../api/healing'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from 'recharts'
import toast from 'react-hot-toast'

// ── Live Log Terminal ─────────────────────────────────────────────────────────
const MAX_LOGS = 200

const LOG_COLORS = {
  INFO: '#38bdf8',
  WARN: '#f59e0b',
  ERROR: '#ef4444',
  SUCCESS: '#10b981',
  HEAL: '#a855f7',
  SYSTEM: '#64748b',
}

function TerminalLog({ logs }) {
  const bottomRef = useRef(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div
      className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed p-4 space-y-0.5"
      style={{ background: 'rgba(0, 0, 0, 0.6)' }}
    >
      {logs.map((log, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="flex gap-3 group hover:bg-white/[0.02] px-1 rounded"
        >
          <span className="text-slate-600 whitespace-nowrap flex-shrink-0 select-none">{log.time}</span>
          <span
            className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest flex-shrink-0 leading-none"
            style={{ background: `${LOG_COLORS[log.level] || '#64748b'}15`, color: LOG_COLORS[log.level] || '#64748b' }}
          >
            {log.level}
          </span>
          <span className="text-slate-300 break-all">{log.message}</span>
        </motion.div>
      ))}
      {logs.length === 0 && (
        <div className="flex items-center gap-3 text-slate-600 py-8 justify-center">
          <Radio className="w-4 h-4 animate-pulse" />
          <span>Awaiting telemetry stream...</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}

// ── Approval Card ─────────────────────────────────────────────────────────────
function ApprovalCard({ action, onApprove, onReject }) {
  const [submitting, setSubmitting] = useState(false)

  const handleAction = async (fn) => {
    setSubmitting(true)
    try {
      await fn(action.id)
      toast.success('Action processed successfully')
    } catch (err) {
      toast.error('Failed to process action')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="glass-premium rounded-2xl p-4 border border-yellow-500/20 bg-yellow-500/5 relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 p-2">
        <AlertTriangle className="w-3 h-3 text-yellow-500 animate-pulse" />
      </div>
      
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-xl bg-yellow-500/20 text-yellow-500">
          <ShieldAlert className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-black text-white uppercase tracking-tight truncate">
              {action.action_type?.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-[10px] text-slate-300 font-medium">
            Requires approval for {action.resource_name || action.resource_id}
          </p>
          
          <div className="mt-4 flex gap-2">
            <button
              onClick={() => handleAction(onApprove)}
              disabled={submitting}
              className="flex-1 py-1.5 rounded-lg bg-emerald-500 text-black text-[9px] font-black uppercase tracking-widest hover:bg-emerald-400 transition-colors disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => handleAction(onReject)}
              disabled={submitting}
              className="flex-1 py-1.5 rounded-lg bg-white/10 text-white text-[9px] font-black uppercase tracking-widest hover:bg-white/20 transition-colors disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ── AI Decision Card ──────────────────────────────────────────────────────────
function AIDecisionCard({ action, index }) {
  const statusStyle = {
    success: 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20',
    failed: 'text-rose-400 bg-rose-400/10 border-rose-400/20',
    pending: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
    running: 'text-sky-400 bg-sky-400/10 border-sky-400/20',
  }

  const actionIcons = {
    restart: '🔄', scale_up: '📈', failover: '🔁',
    isolate: '🔒', reroute: '↔️', rollback: '⏪',
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass-premium rounded-2xl p-4 border border-white/5 group hover:border-white/10 transition-all relative overflow-hidden"
    >
      <div className="absolute left-0 top-0 bottom-0 w-0.5 rounded-full"
        style={{ background: action.status === 'success' ? '#10b981' : action.status === 'failed' ? '#ef4444' : '#f59e0b' }} />

      <div className="flex items-start justify-between gap-3 pl-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-base">{actionIcons[action.action_type] || '⚡'}</span>
            <span className="text-xs font-black text-white uppercase tracking-tight truncate">
              {action.action_type?.replace(/_/g, ' ')}
            </span>
          </div>
          <p className="text-[10px] text-slate-400 truncate font-mono">
            {action.resource_name || action.resource_id?.substring(0, 24)}
          </p>
          <p className="text-[9px] text-slate-600 mt-1">
            {action.created_at ? formatDistanceToNow(new Date(action.created_at), { addSuffix: true }) : '—'}
          </p>
        </div>
        <span className={clsx('px-2 py-0.5 rounded-full text-[8px] font-black uppercase tracking-widest border flex-shrink-0', statusStyle[action.status] || statusStyle.pending)}>
          {action.status}
        </span>
      </div>
    </motion.div>
  )
}

// ── Mini Sparkline ────────────────────────────────────────────────────────────
function MiniSparkline({ data, color }) {
  return (
    <ResponsiveContainer width="100%" height={40}>
      <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <YAxis domain={[0, 100]} hide />
        <Area type="monotone" dataKey="v" stroke={color} fill={`url(#spark-${color})`} strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── Metric Tile ───────────────────────────────────────────────────────────────
function MetricTile({ icon: Icon, label, value, color, sparkData }) {
  return (
    <div className="glass-premium rounded-2xl p-4 border border-white/5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4" style={{ color }} />
          <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">{label}</span>
        </div>
        <span className="text-xl font-black font-mono" style={{ color }}>{value}</span>
      </div>
      {sparkData && <MiniSparkline data={sparkData} color={color} />}
    </div>
  )
}

// ── Main War Room ─────────────────────────────────────────────────────────────
export default function WarRoom() {
  const { connected, lastMessage } = useWebSocket()
  const [logs, setLogs] = useState([])
  const [actions, setActions] = useState([])
  const [stats, setStats] = useState(null)
  const [cpuHistory, setCpuHistory] = useState([])
  const [memHistory, setMemHistory] = useState([])
  const [alertBanner, setAlertBanner] = useState(null)
  const [liveMetrics, setLiveMetrics] = useState({ cpu: 0, memory: 0, network: 0 })
  const [pendingApprovals, setPendingApprovals] = useState([])

  const pushLog = useCallback((level, message) => {
    const time = new Date().toLocaleTimeString('en', { hour12: false })
    setLogs((prev) => [...prev.slice(-MAX_LOGS + 1), { time, level, message }])
  }, [])

  // WebSocket events → log stream
  useEffect(() => {
    if (!lastMessage) return
    const { type, data } = lastMessage

    if (type === 'metrics_update') {
      setLiveMetrics(data)
      setCpuHistory((p) => [...p.slice(-29), { v: data.cpu }])
      setMemHistory((p) => [...p.slice(-29), { v: data.memory }])
      
      if (data.cpu > 85) {
        pushLog('WARN', `HIGH CPU: ${data.cpu?.toFixed(1)}% across fleet`)
        setAlertBanner(`⚠️ Critical CPU load detected: ${data.cpu?.toFixed(1)}%`)
        setTimeout(() => setAlertBanner(null), 8000)
      } else {
        pushLog('INFO', `Telemetry: CPU=${data.cpu?.toFixed(1)}% MEM=${data.memory?.toFixed(1)}%`)
      }
    }

    if (type === 'healing_started') {
      pushLog('HEAL', `🔧 Healing initiated: ${data.action_type} → ${data.resource_name || data.resource_id}`)
    }
    if (type === 'healing_completed') {
      const ok = data.status === 'success'
      pushLog(ok ? 'SUCCESS' : 'ERROR', `${ok ? '✅' : '❌'} Healing ${data.status}: ${data.action_type} on ${data.resource_name}`)
    }
    if (type === 'drift_detected') {
      pushLog('WARN', `🔀 Drift detected on ${data.resource_name}: ${data.field} changed`)
      setAlertBanner(`🔀 Drift detected on ${data.resource_name}`)
      setTimeout(() => setAlertBanner(null), 10000)
    }
    if (type === 'scan_completed') {
      pushLog('SUCCESS', `🔍 Discovery complete: ${data.count || 0} resources found`)
    }
  }, [lastMessage, pushLog])

  // Initial system logs
  useEffect(() => {
    pushLog('SYSTEM', '▶ War Room initialized — streaming telemetry')
    pushLog('SYSTEM', `${connected ? '✅' : '⏳'} WebSocket: ${connected ? 'CONNECTED' : 'CONNECTING...'}`)
    pushLog('SYSTEM', '🤖 Aura AI companion: ACTIVE')
    pushLog('SYSTEM', '🔍 Autonomous healing engine: LISTENING')
  }, [])

  useEffect(() => {
    if (connected) pushLog('SUCCESS', '🔗 Real-time telemetry link established')
  }, [connected])

  const load = useCallback(async () => {
    try {
      const [sRes, aRes] = await Promise.all([getStats(), getHealingActions()])
      setStats(sRes.data)
      const allActions = aRes.data || []
      setActions(allActions.slice(0, 15))
      setPendingApprovals(allActions.filter(a => a.status === 'pending_approval'))
      pushLog('INFO', `Dashboard sync: ${sRes.data?.total_resources || 0} resources loaded`)
    } catch (e) {
      pushLog('ERROR', `Failed to sync dashboard: ${e.message}`)
    }
  }, [pushLog])

  useEffect(() => {
    load()
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [load])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="h-[calc(100vh-9rem)] flex flex-col gap-4 pb-2"
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-red-500 to-orange-600 flex items-center justify-center shadow-lg shadow-red-500/20">
            <Radio className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
              War Room
              <span className="text-[9px] font-black text-red-400 bg-red-400/10 border border-red-400/20 rounded-full px-2 py-0.5 uppercase tracking-widest animate-pulse">
                LIVE
              </span>
            </h1>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">
              AIOps Command Center — Real-Time Observability
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={clsx(
            'flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest border',
            connected ? 'bg-emerald-500/5 text-emerald-400 border-emerald-500/20' : 'bg-white/5 text-slate-500 border-white/10'
          )}>
            {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {connected ? 'Telemetry Live' : 'Reconnecting...'}
          </div>
          <button onClick={load} id="warroom-refresh" className="btn-secondary-glass !py-1.5 !px-4 flex items-center gap-2 text-[10px]">
            <RefreshCw className="w-3.5 h-3.5" /> Sync
          </button>
        </div>
      </div>

      {/* ── Alert Banner ── */}
      <AnimatePresence>
        {alertBanner && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="flex items-center gap-3 px-5 py-3 rounded-2xl bg-red-500/10 border border-red-500/30 text-sm font-bold text-red-300"
          >
            <AlertTriangle className="w-4 h-4 flex-shrink-0 animate-pulse" />
            {alertBanner}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Metric Tiles ── */}
      <div className="grid grid-cols-4 gap-3 flex-shrink-0">
        <MetricTile icon={Activity} label="CPU Load" value={`${liveMetrics.cpu?.toFixed(1) || 0}%`} color="#0ea5e9" sparkData={cpuHistory} />
        <MetricTile icon={Brain} label="Memory" value={`${liveMetrics.memory?.toFixed(1) || 0}%`} color="#a855f7" sparkData={memHistory} />
        <MetricTile icon={ShieldAlert} label="Critical" value={stats?.critical_resources ?? '—'} color="#ef4444" />
        <MetricTile icon={HeartPulse} label="Healed" value={stats?.healing_total ?? '—'} color="#10b981" />
      </div>

      {/* ── Main Split Pane ── */}
      <div className="flex-1 grid grid-cols-5 gap-4 min-h-0">
        {/* Left — Terminal */}
        <div className="col-span-3 glass-premium rounded-[2rem] overflow-hidden flex flex-col border border-white/5">
          {/* Terminal header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-black/40 flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/60" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/60" />
              </div>
              <div className="w-px h-4 bg-white/10 mx-1" />
              <Terminal className="w-4 h-4 text-sky-400" />
              <span className="text-[10px] font-black text-sky-400 uppercase tracking-widest">
                System Intelligence Feed
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-600 font-mono">{logs.length} events</span>
              <button
                onClick={() => setLogs([])}
                className="text-[9px] text-slate-600 hover:text-slate-400 uppercase font-black tracking-wider transition-colors px-2 py-1 rounded-lg hover:bg-white/5"
              >
                Clear
              </button>
            </div>
          </div>

          <TerminalLog logs={logs} />

          {/* Terminal input bar (cosmetic) */}
          <div className="flex items-center gap-2 px-4 py-2.5 bg-black/40 border-t border-white/5 flex-shrink-0">
            <span className="text-emerald-400 font-mono text-xs">aiops❯</span>
            <span className="text-slate-600 font-mono text-xs">streaming telemetry...</span>
            <motion.span
              className="w-2 h-4 bg-sky-400 inline-block"
              animate={{ opacity: [1, 0, 1] }}
              transition={{ repeat: Infinity, duration: 1 }}
            />
          </div>
        </div>

        {/* Right — AI Decisions */}
        <div className="col-span-2 flex flex-col gap-4 min-h-0">
          {/* AI Decision Feed */}
          <div className="flex-1 glass-premium rounded-[2rem] overflow-hidden flex flex-col border border-white/5 min-h-0">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-black text-white uppercase tracking-tight">AI Decision Log</span>
              </div>
              <span className="text-[9px] text-slate-600 font-mono">{actions.length} actions</span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2 min-h-0">
              {/* Pending Approvals Section */}
              <AnimatePresence>
                {pendingApprovals.length > 0 && (
                  <div className="mb-6 space-y-3">
                    <h4 className="text-[9px] font-black text-yellow-500 uppercase tracking-widest flex items-center gap-2 mb-3">
                      <ShieldAlert className="w-3 h-3" /> Pending Approvals
                    </h4>
                    {pendingApprovals.map((a) => (
                      <ApprovalCard 
                        key={a.id} 
                        action={a} 
                        onApprove={async () => {
                          await approveHealing(a.id)
                          load()
                        }}
                        onReject={async () => {
                          await rejectHealing(a.id)
                          load()
                        }}
                      />
                    ))}
                    <div className="h-px bg-white/5 my-4" />
                  </div>
                )}
              </AnimatePresence>

              <AnimatePresence initial={false}>
                {actions.length > 0 ? (
                  actions.map((a, i) => <AIDecisionCard key={a.id ?? i} action={a} index={i} />)
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <HeartPulse className="w-10 h-10 text-slate-800 mb-3" />
                    <p className="text-xs font-bold uppercase tracking-widest text-slate-600">No AI Actions Yet</p>
                    <p className="text-[10px] text-slate-700 mt-1">Autonomous healing will log here</p>
                  </div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* System Status Grid */}
          <div className="glass-premium rounded-[2rem] p-5 border border-white/5 flex-shrink-0">
            <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5" /> System Matrix
            </h4>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Resources', value: stats?.total_resources ?? '—', color: 'text-sky-400' },
                { label: 'Providers', value: Object.keys(stats?.providers || {}).length || '—', color: 'text-purple-400' },
                { label: 'Health %', value: `${stats?.health_score ?? 0}%`, color: 'text-emerald-400' },
                { label: 'Avg CPU %', value: `${stats?.avg_cpu?.toFixed(1) ?? 0}%`, color: 'text-yellow-400' },
              ].map((s) => (
                <div key={s.label} className="bg-white/[0.02] rounded-xl p-3 border border-white/5">
                  <div className={clsx('text-xl font-black font-mono', s.color)}>{s.value}</div>
                  <div className="text-[9px] text-slate-600 font-black uppercase tracking-widest mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
