import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  GitMerge, RefreshCw, AlertTriangle, CheckCircle2,
  Shield, Clock, Trash2, Play, Database, ChevronRight,
  Info, Zap, Filter
} from 'lucide-react'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'

const API_BASE = '/api'

async function getDriftStatus() {
  const r = await fetch(`${API_BASE}/drift/status`, {
    headers: { Authorization: `Bearer ${JSON.parse(localStorage.getItem('cloud-heal-auth') || '{}')?.state?.token}` }
  })
  return r.json()
}

async function triggerDriftScan() {
  const r = await fetch(`${API_BASE}/drift/scan`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${JSON.parse(localStorage.getItem('cloud-heal-auth') || '{}')?.state?.token}` }
  })
  return r.json()
}

// ── DriftHistory Timeline ──────────────────────────────────────────────────
function DriftTimeline({ resourceId }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchHistory() {
      try {
        const r = await fetch(`${API_BASE}/drift/history/${resourceId}`, {
          headers: { Authorization: `Bearer ${JSON.parse(localStorage.getItem('cloud-heal-auth') || '{}')?.state?.token}` }
        })
        const d = await r.json()
        setHistory(d)
      } catch (e) {
        console.error('History fetch failed', e)
      } finally {
        setLoading(false)
      }
    }
    fetchHistory()
  }, [resourceId])

  if (loading) return <div className="p-4 text-[9px] text-slate-500 animate-pulse font-mono tracking-widest uppercase">Loading Timeline...</div>
  if (history.length === 0) return <div className="p-4 text-[9px] text-slate-600 font-mono italic">No historical changes recorded.</div>

  return (
    <div className="space-y-4 py-4 relative ml-4 border-l border-white/5 pl-6">
      {history.map((h, i) => (
        <div key={i} className="relative group">
          <div className="absolute -left-[27px] top-1.5 w-2.5 h-2.5 rounded-full bg-slate-700 border border-slate-600 group-hover:bg-indigo-500 group-hover:border-indigo-400 transition-all shadow-lg" />
          <div className="flex flex-col gap-1">
            <span className="text-[10px] font-black text-white/80 uppercase tracking-tighter">
              {h.field.replace('_', ' ')} Updated
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[8px] text-slate-500 font-mono line-through opacity-40">{h.old_value}</span>
              <ChevronRight className="w-2.5 h-2.5 text-slate-700" />
              <span className="text-[8px] text-emerald-400 font-mono font-black">{h.new_value}</span>
            </div>
            <span className="text-[7px] text-slate-600 font-mono mt-0.5">
              {formatDistanceToNow(new Date(h.detected_at), { addSuffix: true })}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── DriftField Card ───────────────────────────────────────────────────────────
function DriftFieldRow({ drift }) {
  const sev = drift.severity === 'critical'
    ? { color: 'text-rose-400', bg: 'bg-rose-400/10', border: 'border-rose-400/20' }
    : { color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-400/20' }

  return (
    <div className={clsx('flex items-center justify-between p-3 rounded-xl border', sev.bg, sev.border)}>
      <div className="flex items-center gap-3">
        <AlertTriangle className={clsx('w-3.5 h-3.5 flex-shrink-0', sev.color)} />
        <div>
          <span className={clsx('text-[10px] font-black uppercase tracking-widest', sev.color)}>
            {drift.field}
          </span>
          <div className="flex flex-col gap-1 mt-1">
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-500 font-mono">baseline: <span className="text-white bg-white/5 px-1 rounded">{String(drift.desired)}</span></span>
              <ChevronRight className="w-2.5 h-2.5 text-slate-600" />
              <span className="text-[9px] text-slate-500 font-mono">current: <span className={clsx('font-bold', sev.color)}>{String(drift.current)}</span></span>
            </div>
          </div>
        </div>
      </div>
      <span className={clsx('text-[8px] font-black uppercase tracking-widest px-2 py-1 rounded-full border', sev.bg, sev.color, sev.border)}>
        {drift.severity}
      </span>
    </div>
  )
}

// ── DriftReport Card ──────────────────────────────────────────────────────────
function DriftReportCard({ report, index }) {
  const [expanded, setExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState('drift') // drift | remediation | history

  const riskColor = report.risk_score > 80 ? 'text-rose-400' : report.risk_score > 50 ? 'text-orange-400' : 'text-emerald-400'

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={clsx(
        'glass-premium rounded-2xl border overflow-hidden transition-all duration-300',
        expanded ? 'ring-1 ring-indigo-500/30' : '',
        report.is_critical ? 'border-rose-500/20' : 'border-yellow-500/15'
      )}
    >
      <div
        className="w-full flex items-center justify-between p-5 hover:bg-white/[0.02] transition-all text-left cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4">
          <div className={clsx(
            'w-10 h-10 rounded-xl flex items-center justify-center border',
            report.is_critical ? 'bg-rose-500/10 border-rose-500/20' : 'bg-yellow-500/10 border-yellow-500/20'
          )}>
            <GitMerge className={clsx('w-5 h-5', report.is_critical ? 'text-rose-400' : 'text-yellow-400')} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-black text-white">{report.resource_name}</h3>
              {report.compliance_id && (
                <span className="text-[8px] font-black bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-1.5 py-0.5 rounded tracking-widest">
                  {report.compliance_id}
                </span>
              )}
            </div>
            <p className="text-[9px] text-slate-500 font-mono mt-0.5 uppercase tracking-widest">
              {report.drift_count} field(s) drifted • ID: {report.resource_id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className={clsx('text-xs font-black', riskColor)}>{report.risk_score?.toFixed(0)}</div>
            <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest">Risk Score</div>
          </div>
          <div className="flex items-center gap-3">
            {report.is_critical && (
              <motion.span
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                className="text-[8px] font-black uppercase tracking-widest px-2 py-1 rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/20 shadow-lg shadow-rose-500/10"
              >
                CRITICAL
              </motion.span>
            )}
            <ChevronRight className={clsx('w-4 h-4 text-slate-500 transition-transform', expanded && 'rotate-90')} />
          </div>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/5"
          >
            {/* Tabs */}
            <div className="flex items-center gap-4 px-5 pt-4 border-b border-white/5">
              {[
                { id: 'drift', label: 'Drift Report', icon: AlertTriangle },
                { id: 'remediation', label: 'Remediation', icon: Zap },
                { id: 'history', label: 'Timeline', icon: Clock }
              ].map(t => (
                <button
                  key={t.id}
                  onClick={(e) => { e.stopPropagation(); setActiveTab(t.id) }}
                  className={clsx(
                    'flex items-center gap-2 pb-3 transition-all relative',
                    activeTab === t.id ? 'text-white' : 'text-slate-500 hover:text-slate-300'
                  )}
                >
                  <t.icon className="w-3 h-3" />
                  <span className="text-[10px] font-black uppercase tracking-widest">{t.label}</span>
                  {activeTab === t.id && (
                    <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-500" />
                  )}
                </button>
              ))}
            </div>

            <div className="p-5">
              {activeTab === 'drift' && (
                <div className="space-y-2">
                  <div className="bg-rose-500/5 border border-rose-500/10 p-3 rounded-xl mb-4">
                    <p className="text-[9px] font-black text-rose-400 uppercase tracking-widest mb-1">Impact Analysis</p>
                    <p className="text-[11px] text-slate-300 leading-relaxed font-medium">
                      {report.impact}
                    </p>
                  </div>
                  {report.drifted_fields?.map((df, i) => (
                    <DriftFieldRow key={i} drift={df} />
                  ))}
                </div>
              )}

              {activeTab === 'remediation' && (
                <div className="space-y-4">
                  <div className="glass-premium p-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-6 h-6 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                        <Zap className="w-3 h-3 text-emerald-400" />
                      </div>
                      <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Recommended Fix</span>
                    </div>
                    <p className="text-xs text-white leading-relaxed">
                      {report.remediation}
                    </p>
                  </div>
                  <button className="w-full btn-primary-glow flex items-center justify-center gap-2 py-3">
                    <Play className="w-3 h-3" />
                    Apply Auto-Remediation
                  </button>
                </div>
              )}

              {activeTab === 'history' && (
                <DriftTimeline resourceId={report.resource_id} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}


// ── Main DriftDetection Page ──────────────────────────────────────────────────
export default function DriftDetection() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getDriftStatus()
      setData(res)
    } catch (e) {
      toast.error('Failed to load drift status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleScan = async () => {
    setScanning(true)
    try {
      const res = await triggerDriftScan()
      toast.success(`Drift scan complete: ${res.drifted_resources} resource(s) drifted`)
      await load()
    } catch {
      toast.error('Drift scan failed')
    } finally {
      setScanning(false)
    }
  }

  const [filter, setFilter] = useState('all')

  const reports = (data?.reports || []).filter(r => 
    filter === 'all' || 
    (filter === 'critical' && r.is_critical) || 
    (filter === 'drifted' && r.drift_count > 0) ||
    r.resource_type === filter
  )

  const totalDrifted = data?.total_drifted || 0
  const critical = data?.critical || 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8 pb-12"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <GitMerge className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-black text-white tracking-tighter">Drift Detection</h1>
            <p className="text-slate-500 text-sm mt-1 font-medium">
              Desired State Engine — detect & auto-remediate configuration drift
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={load} disabled={loading} className="btn-secondary-glass flex items-center gap-2">
            <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            Refresh
          </button>
          <button
            id="drift-scan-btn"
            onClick={handleScan}
            disabled={scanning}
            className="btn-primary-glow flex items-center gap-2"
          >
            {scanning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run Drift Scan
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Monitored Resources', value: (data?.reports || []).length, color: '#0ea5e9', icon: Shield },
          { label: 'Drifted Resources', value: totalDrifted, color: totalDrifted > 0 ? '#f59e0b' : '#10b981', icon: GitMerge },
          { label: 'Critical Drifts', value: critical, color: critical > 0 ? '#ef4444' : '#10b981', icon: AlertTriangle },
        ].map((s) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-premium rounded-3xl p-6 border border-white/5 relative overflow-hidden group hover-glow"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${s.color}15` }}>
                <s.icon className="w-5 h-5" style={{ color: s.color }} />
              </div>
            </div>
            <div className="text-3xl font-black text-white" style={{ color: s.value > 0 && s.color !== '#10b981' ? s.color : undefined }}>
              {s.value}
            </div>
            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-1">{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* How it works info */}
      <div className="glass-premium rounded-3xl p-6 border border-indigo-500/10 bg-indigo-500/[0.02] flex items-start gap-4">
        <Info className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-black text-white mb-1">How Drift Detection Works</p>
          <p className="text-xs text-slate-400 leading-relaxed">
            Snapshot any resource's current state as its <strong className="text-white">"desired state"</strong> baseline.
            The engine polls every 60 seconds, comparing live telemetry to that baseline.
            When a field drifts beyond threshold (e.g. CPU jumps 30%, status changes), a WebSocket alert fires
            and appears in the <strong className="text-white">War Room</strong>. Critical drifts auto-trigger a healing action.
          </p>
        </div>
      </div>

      {/* Drift reports */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-black text-white tracking-tight">Drift Reports</h2>
            <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1 rounded-lg">
              <Filter className="w-3 h-3 text-slate-500" />
              <select 
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-transparent text-[10px] font-black uppercase tracking-widest focus:outline-none text-slate-400"
              >
                <option value="all">All Reports</option>
                <option value="drifted">Drifted Only</option>
                <option value="critical">Critical Only</option>
                <option value="compute">Compute</option>
                <option value="database">Database</option>
              </select>
            </div>
          </div>
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
            {reports.length} Displayed
          </span>
        </div>

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 glass-premium rounded-2xl animate-pulse" />
            ))}
          </div>
        ) : reports.length === 0 ? (
          <div className="glass-premium rounded-3xl p-16 text-center border border-white/5">
            <CheckCircle2 className="w-16 h-16 mx-auto mb-4 text-emerald-500/30" />
            <h3 className="text-xl font-black text-white mb-2">No Drift Detected</h3>
            <p className="text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
              No desired state snapshots configured yet. After running a cloud scan,
              use the Topology Graph to snapshot resources as baselines.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map((r, i) => (
              <DriftReportCard key={r.resource_id} report={r} index={i} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}
