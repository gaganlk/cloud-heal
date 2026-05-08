import { useState, useCallback, useEffect } from 'react'
import {
  HeartPulse, Play, RefreshCw, CheckCircle2, XCircle,
  Clock, Loader2, Zap, Shield, RotateCcw, ArrowUpCircle,
  AlertTriangle, Filter, Activity, Server, ShieldCheck, 
  Info, Search, History, Terminal, BarChart3, ChevronRight,
  Settings2, Power, TrendingUp
} from 'lucide-react'
import { triggerHealing, autoHeal, getHealingActions } from '../api/healing'
import { listCredentials } from '../api/credentials'
import { getPropagationResources } from '../api/graph'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuthStore } from '../store/authStore'
import { motion, AnimatePresence } from 'framer-motion'
import { CardSkeleton, TableSkeleton } from '../components/common/Skeleton'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'

const ACTION_TYPES = [
  { id: 'restart', label: 'Cycle Ops', icon: RotateCcw, color: '#0ea5e9', desc: 'Gracefully restart active service' },
  { id: 'scale_up', label: 'Elastic Scale', icon: ArrowUpCircle, color: '#10b981', desc: 'Add compute resources' },
  { id: 'reroute', label: 'Vector Path', icon: Zap, color: '#f59e0b', desc: 'Redirect ingress traffic' },
  { id: 'isolate', label: 'Quarantine', icon: Shield, color: '#a855f7', desc: 'Isolate compromised node' },
  { id: 'failover', label: 'Failover Burst', icon: Power, color: '#f43f5e', desc: 'Switch to secondary cluster' },
]

const SEVERITY_OPTIONS = ['low', 'medium', 'high', 'critical']

const STATUS_STYLES = {
  success: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-400/10', label: 'Resolved', border: 'border-emerald-500/20' },
  failed: { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-400/10', label: 'Terminal', border: 'border-rose-500/20' },
  running: { icon: Loader2, color: 'text-sky-400', bg: 'bg-sky-400/10', label: 'Executing', spin: true, border: 'border-sky-500/20' },
  pending: { icon: Clock, color: 'text-orange-400', bg: 'bg-orange-400/10', label: 'Queued', border: 'border-orange-500/20' },
}

function ActionHistoryRow({ action }) {
  const s = STATUS_STYLES[action.status] || STATUS_STYLES.pending
  const Icon = s.icon

  return (
    <tr className="group hover:bg-white/[0.03] transition-all duration-300">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
           <div className="w-8 h-8 rounded-lg bg-white/[0.03] border border-white/5 flex items-center justify-center text-xs font-black">
              {action.resource_name?.[0]?.toUpperCase() || 'R'}
           </div>
           <div>
              <p className="text-sm font-bold text-white tracking-tight">{action.resource_name || action.resource_id}</p>
              {action.auto_triggered && (
                <span className="text-[8px] font-black uppercase tracking-[0.2em] text-purple-400">Autonomous Execution</span>
              )}
           </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <span className="text-[10px] font-black uppercase tracking-widest text-slate-400 bg-white/5 px-2 py-0.5 rounded-md border border-white/5">
           {action.action_type?.replace(/_/g, ' ')}
        </span>
      </td>
      <td className="px-6 py-4">
        <div className={clsx('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border', s.bg, s.color, s.border)}>
          <Icon className={clsx('w-3 h-3', s.spin && 'animate-spin')} />
          {s.label}
        </div>
      </td>
      <td className="px-6 py-4 text-[10px] font-black uppercase tracking-widest text-slate-500">
        {action.created_at ? formatDistanceToNow(new Date(action.created_at), { addSuffix: true }) : '—'}
      </td>
      <td className="px-6 py-4">
        <p className="text-xs text-slate-500 font-medium truncate max-w-[200px]">{action.details?.message || 'Protocol complete'}</p>
      </td>
    </tr>
  )
}

export default function Healing() {
  const { user } = useAuthStore()
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [creds, setCreds] = useState([])
  const [resources, setResources] = useState([])
  const [selectedCred, setSelectedCred] = useState('')
  const [selectedResource, setSelectedResource] = useState('')
  const [selectedAction, setSelectedAction] = useState('restart')
  const [selectedSeverity, setSelectedSeverity] = useState('medium')
  const [triggering, setTriggering] = useState(false)
  const [autoHealing, setAutoHealing] = useState(false)
  const [liveLog, setLiveLog] = useState([])
  const [statusFilter, setStatusFilter] = useState('all')

  const { lastMessage } = useWebSocket()

  useEffect(() => {
    if (lastMessage?.type === 'healing_progress' || lastMessage?.type === 'healing_started' || lastMessage?.type === 'healing_completed') {
      setLiveLog((prev) => [
        { ...lastMessage.data, _ts: Date.now() },
        ...prev.slice(0, 19),
      ])
      if (lastMessage?.type === 'healing_completed') loadActions()
    }
  }, [lastMessage])

  const loadActions = useCallback(async () => {
    try {
      const res = await getHealingActions()
      setActions(res.data)
    } catch {}
  }, [])

  useEffect(() => {
    const init = async () => {
      setLoading(true)
      try {
        const [credsRes, actRes] = await Promise.all([listCredentials(), getHealingActions()])
        setCreds(credsRes.data)
        setActions(actRes.data)
        if (credsRes.data.length > 0) {
          const firstId = credsRes.data[0].id
          setSelectedCred(String(firstId))
          const rRes = await getPropagationResources(firstId).catch(() => ({ data: [] }))
          setResources(rRes.data)
          if (rRes.data.length > 0) setSelectedResource(rRes.data[0].resource_id)
        }
      } catch {}
      setLoading(false)
    }
    init()
  }, [])

  const handleCredChange = async (val) => {
    setSelectedCred(val)
    setResources([])
    try {
      const res = await getPropagationResources(val)
      setResources(res.data)
      if (res.data.length > 0) setSelectedResource(res.data[0].resource_id)
    } catch {}
  }

  const handleTrigger = async () => {
    if (!selectedResource) { toast.error('Identify target resource'); return }
    const res = resources.find((r) => r.resource_id === selectedResource)
    setTriggering(true)
    try {
      await triggerHealing({
        resource_id: selectedResource,
        resource_name: res?.name || selectedResource,
        action_type: selectedAction,
        severity: selectedSeverity,
      })
      toast.success(`Protocol initiated: ${selectedAction}`)
      setLiveLog((prev) => [{
        step: `Manual override: Executing '${selectedAction}' protocol on cluster segment ${res?.name}...`,
        timestamp: new Date().toISOString(),
        _ts: Date.now(),
        status: 'running'
      }, ...prev])
      setTimeout(loadActions, 4000)
    } catch (err) {
      toast.error('Trigger mechanism failure')
    } finally {
      setTriggering(false)
    }
  }

  const handleAutoHeal = async () => {
    if (!selectedResource || !selectedCred) { toast.error('Identify target resource'); return }
    setAutoHealing(true)
    try {
      const res = await autoHeal({ resource_id: selectedResource, credential_id: parseInt(selectedCred) })
      toast.success('Neural heal sequence active')
      setTimeout(loadActions, 4000)
    } catch (err) {
      toast.error('AI sequence failed')
    } finally {
      setAutoHealing(false)
    }
  }

  const filtered = statusFilter === 'all' ? actions : actions.filter((a) => a.status === statusFilter)
  const counts = { success: 0, failed: 0, running: 0, pending: 0 }
  actions.forEach((a) => { counts[a.status] = (counts[a.status] || 0) + 1 })

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-7xl mx-auto space-y-8 pb-20"
    >
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <HeartPulse className="w-8 h-8 text-emerald-400" />
            Remediation Hub
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium max-w-sm">
            Autonomous self-healing engine capable of real-time infrastructure patching and state recovery.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-4 gap-8">
        {/* Main Controls Overlay */}
        <div className="lg:col-span-3 space-y-8">
          <div className="glass-premium rounded-[2.5rem] p-8 border border-white/5 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 blur-[100px] -mr-32 -mt-32" />
            
            <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-8 flex items-center gap-2">
               <Settings2 className="w-4 h-4" /> Operations Core
            </h3>

            <div className="grid sm:grid-cols-2 gap-8 mb-8 relative z-10">
              <div>
                <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest block mb-2 px-1">Network Node Segment</label>
                <select id="heal-cred" value={selectedCred} onChange={(e) => handleCredChange(e.target.value)}
                  className="input-premium py-3 px-4 text-xs font-bold">
                  {creds.map((c) => <option key={c.id} value={c.id}>{c.provider.toUpperCase()} · {c.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest block mb-2 px-1">Target Infrastructure</label>
                <select id="heal-resource" value={selectedResource} onChange={(e) => setSelectedResource(e.target.value)}
                  className="input-premium py-3 px-4 text-xs font-bold">
                  {resources.length === 0 ? <option>Discovering Nodes...</option> : resources.map((r) => <option key={r.resource_id} value={r.resource_id}>{r.name}</option>)}
                </select>
              </div>
            </div>

            {/* Action Grid */}
            <div className="mb-10 relative z-10">
              <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest block mb-4 px-1">Select Remedy Protocol</label>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {ACTION_TYPES.map((a) => (
                  <button
                    key={a.id}
                    id={`action-${a.id}`}
                    onClick={() => setSelectedAction(a.id)}
                    className={clsx(
                      'flex flex-col items-center gap-3 p-5 rounded-3xl border transition-all duration-300 relative group overflow-hidden',
                      selectedAction === a.id
                        ? 'border-white/20'
                        : 'border-white/5 hover:border-white/10'
                    )}
                    style={selectedAction === a.id ? { background: `${a.color}15`, boxShadow: `0 0 30px ${a.color}10` } : {}}
                  >
                    <div className={clsx(
                      'w-10 h-10 rounded-xl flex items-center justify-center transition-transform duration-500 group-hover:scale-110 shadow-lg border border-white/10',
                      selectedAction === a.id ? 'bg-white/10' : 'bg-white/[0.02]'
                    )}>
                       <a.icon className="w-5 h-5" style={{ color: selectedAction === a.id ? a.color : '#475569' }} />
                    </div>
                    <span className={clsx('text-[10px] font-black uppercase tracking-tight', selectedAction === a.id ? 'text-white' : 'text-slate-500')}>
                      {a.label}
                    </span>
                    {selectedAction === a.id && (
                       <motion.div layoutId="activeAction" className="absolute bottom-0 inset-x-0 h-1" style={{ background: a.color }} />
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 relative z-10">
              <button
                id="trigger-healing"
                onClick={handleTrigger}
                disabled={triggering || !selectedResource}
                className="btn-primary-glow flex-1 !py-4 text-xs font-black uppercase tracking-[0.2em]"
              >
                {triggering ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                Engage Override Protocol
              </button>
              <button
                id="auto-heal"
                onClick={handleAutoHeal}
                disabled={autoHealing || !selectedResource}
                className="btn-secondary-glass !bg-emerald-500/10 !text-emerald-400 !border-emerald-500/30 flex-1 !py-4 text-xs font-black uppercase tracking-[0.2em] shadow-xl"
              >
                {autoHealing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <ShieldCheck className="w-4 h-4 mr-2" />}
                Neural Auto-Heal Sequence
              </button>
            </div>
          </div>

          {/* History Deck */}
          <div className="glass-premium rounded-[2.5rem] overflow-hidden border border-white/5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-8 py-6 border-b border-white/5 bg-white/[0.01]">
              <div className="flex items-center gap-3">
                 <History className="w-5 h-5 text-slate-500" />
                 <h3 className="text-lg font-black text-white tracking-tight">Recovery Ledger</h3>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 bg-white/[0.03] p-1 rounded-xl border border-white/5">
                  {['all', 'success', 'failed'].map(f => (
                    <button 
                      key={f}
                      onClick={() => setStatusFilter(f)}
                      className={clsx(
                        'px-4 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all',
                        statusFilter === f ? 'bg-white/10 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'
                      )}
                    >
                      {f}
                    </button>
                  ))}
                </div>
                <button id="refresh-healing" onClick={loadActions} className="w-9 h-9 flex items-center justify-center rounded-xl bg-white/[0.03] border border-white/5 text-slate-500 hover:text-white transition-all">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>
            </div>

            {filtered.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-white/5">
                      <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Resource Node</th>
                      <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Protocol Type</th>
                      <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Execution State</th>
                      <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Timestamp</th>
                      <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Telemetry Log</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    <AnimatePresence>
                      {filtered.slice(0, 15).map((a) => <ActionHistoryRow key={a.id} action={a} />)}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-24">
                 <Terminal className="w-16 h-16 text-slate-800 mx-auto mb-4" />
                 <p className="text-xs font-black text-slate-600 uppercase tracking-widest">No previous protocols detected</p>
              </div>
            )}
          </div>
        </div>

        {/* Intelligence Side Panel */}
        <div className="space-y-6">
          {/* Stats Gauge */}
          <div className="glass-premium rounded-[2rem] p-6 border border-white/5 relative overflow-hidden">
             <div className="absolute top-0 left-0 w-32 h-32 bg-sky-500/5 blur-3xl -ml-16 -mt-16" />
             <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6 flex items-center gap-2">
                <BarChart3 className="w-4 h-4" /> Efficiency Matrix
             </h3>
             <div className="space-y-4">
                <StatMetric label="Total Protocols" value={actions.length} color="text-white" />
                <StatMetric label="Restored Nodes" value={counts.success} color="text-emerald-400" />
                <StatMetric label="Active Scopes" value={counts.running} color="text-sky-400" />
                <StatMetric label="Engine Drifts" value={counts.failed} color="text-rose-500" />
                
                <div className="pt-6 border-t border-white/5">
                   <div className="flex justify-between items-center mb-2">
                      <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Success Probability</span>
                      <span className="text-xs font-black text-emerald-400 font-mono">
                         {actions.length ? ((counts.success / actions.length) * 100).toFixed(1) : 0}%
                      </span>
                   </div>
                   <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
                      <motion.div 
                         initial={{ width: 0 }}
                         animate={{ width: `${actions.length ? (counts.success / actions.length) * 100 : 0}%` }}
                         className="h-full bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.5)]" 
                      />
                   </div>
                </div>
             </div>
          </div>

          {/* Real-time Telemetry Stream */}
          <div className="glass-premium rounded-[2rem] p-6 border border-white/5 relative flex-1 min-h-[400px]">
            <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6 flex items-center gap-2">
               <Terminal className="w-4 h-4" /> Console Stream
               <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse ml-auto" />
            </h3>
            <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
               {liveLog.length === 0 ? (
                 <div className="flex flex-col items-center justify-center py-20 text-center opacity-20">
                    <Activity className="w-10 h-10 mb-2" />
                    <p className="text-[9px] font-black uppercase tracking-widest">Establishing Uplink...</p>
                 </div>
               ) : (
                 liveLog.map((entry, i) => (
                   <motion.div 
                     initial={{ opacity: 0, x: -10 }} 
                     animate={{ opacity: 1, x: 0 }} 
                     key={i} 
                     className="bg-white/[0.02] p-3 rounded-xl border border-white/5 space-y-2 group hover:bg-white/[0.05] transition-all"
                   >
                     <div className="flex justify-between items-center">
                        <span className="text-[9px] font-black text-slate-600 font-mono">
                           {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString('en', { hour12: false }) : 'SYS_TIME'}
                        </span>
                        <ChevronRight className="w-3 h-3 text-slate-800 transition-transform group-hover:translate-x-1" />
                     </div>
                     <p className={clsx(
                       'text-[10px] font-bold font-mono leading-relaxed',
                       entry.status === 'success' ? 'text-emerald-400' :
                       entry.status === 'failed' ? 'text-rose-400' :
                       entry.status === 'running' ? 'text-sky-400' : 'text-slate-400',
                     )}>
                       {entry.step || entry.details?.message || `SIG_EXEC: ${entry.action_type}`}
                     </p>
                   </motion.div>
                 ))
               )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function StatMetric({ label, value, color }) {
  return (
    <div className="flex justify-between items-center">
       <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">{label}</span>
       <span className={clsx('text-sm font-black font-mono', color)}>{value}</span>
    </div>
  )
}
