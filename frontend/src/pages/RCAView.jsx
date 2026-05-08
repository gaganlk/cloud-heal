import { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, RefreshCw, AlertTriangle, ChevronRight, GitBranch,
  Target, RadioTower, Zap, CheckCircle2, Brain, ArrowRight,
} from 'lucide-react'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'

const TOKEN = () =>
  JSON.parse(localStorage.getItem('cloud-heal-auth') || '{}')?.state?.token || ''

async function analyzeRCA(resourceId) {
  const r = await fetch(`/api/rca/analyze/${encodeURIComponent(resourceId)}`, {
    headers: { Authorization: `Bearer ${TOKEN()}` },
  })
  if (!r.ok) throw new Error(`RCA failed: ${r.statusText}`)
  return r.json()
}

// ── Causal chain visualization ────────────────────────────────────────────────
function CausalChain({ chain, rootCauseId }) {
  if (!chain || chain.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      {chain.map((nodeId, i) => {
        const isRoot = nodeId === rootCauseId
        const isLast = i === chain.length - 1
        return (
          <div key={nodeId} className="flex items-center gap-2">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: i * 0.1 }}
              className={clsx(
                'px-3 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-widest border',
                isRoot
                  ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                  : isLast
                  ? 'bg-orange-500/15 text-orange-400 border-orange-500/30'
                  : 'bg-white/5 text-slate-400 border-white/10'
              )}
            >
              {isRoot && '🔴 ROOT: '}
              {isLast && !isRoot && '⚡ TARGET: '}
              {nodeId.substring(0, 20)}
              {nodeId.length > 20 ? '…' : ''}
            </motion.div>
            {i < chain.length - 1 && (
              <ArrowRight className="w-3 h-3 text-slate-600 flex-shrink-0" />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Affected node row ─────────────────────────────────────────────────────────
function AffectedNodeRow({ node }) {
  const riskColor =
    (node.risk_score || 0) >= 70 ? '#ef4444' :
    (node.risk_score || 0) >= 40 ? '#f59e0b' : '#10b981'

  return (
    <div className="flex items-center justify-between py-2.5 px-4 rounded-xl hover:bg-white/[0.02] transition-all">
      <div className="flex items-center gap-3">
        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: riskColor }} />
        <span className="text-xs font-bold text-white truncate max-w-[200px]">
          {node.name || node.resource_id?.substring(0, 24)}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-[9px] font-mono text-slate-400">{node.status}</span>
        <span className="text-[9px] font-black font-mono" style={{ color: riskColor }}>
          Risk: {(node.risk_score || 0).toFixed(0)}
        </span>
      </div>
    </div>
  )
}

// ── Main RCA page ─────────────────────────────────────────────────────────────
export default function RCAView() {
  const [searchParams] = useSearchParams()
  const [resourceId, setResourceId] = useState(searchParams.get('resource') || '')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleAnalyze = useCallback(async () => {
    if (!resourceId.trim()) {
      toast.error('Enter a resource ID to analyze')
      return
    }
    setLoading(true)
    setReport(null)
    try {
      const r = await analyzeRCA(resourceId.trim())
      setReport(r)
      if (r.root_cause_id) {
        toast.success('RCA complete — root cause identified', { icon: '🎯' })
      }
    } catch (e) {
      toast.error(`RCA failed: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [resourceId])

  const confidenceColor =
    !report ? '#64748b' :
    report.confidence_score >= 80 ? '#10b981' :
    report.confidence_score >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-8 pb-12"
    >
      {/* ── Header ── */}
      <div className="flex items-center gap-4 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter">Root Cause Analysis</h1>
          <p className="text-slate-500 text-sm mt-1 font-medium">
            Graph-traversal engine to identify true failure origins and suppress alert storms
          </p>
        </div>
      </div>

      {/* ── Input ── */}
      <div className="glass-premium rounded-3xl p-6 border border-white/5 space-y-4">
        <label className="block text-[10px] font-black uppercase tracking-widest text-slate-500">
          Target Resource ID
        </label>
        <div className="flex gap-3">
          <input
            id="rca-resource-input"
            type="text"
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
            placeholder="e.g. i-0abc123def456789 or /subscriptions/.../virtualMachines/my-vm"
            className="input-premium flex-1"
          />
          <button
            id="rca-analyze-btn"
            onClick={handleAnalyze}
            disabled={loading || !resourceId.trim()}
            className="btn-primary-glow px-8 flex items-center gap-2 flex-shrink-0"
          >
            {loading
              ? <RefreshCw className="w-4 h-4 animate-spin" />
              : <Brain className="w-4 h-4" />}
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
        <p className="text-[10px] text-slate-600 font-medium">
          📌 Tip: Click any node in the <strong className="text-slate-400">Topology Graph</strong> → "Root Cause Analysis" to pre-fill this field.
        </p>
      </div>

      {/* ── Results ── */}
      <AnimatePresence mode="wait">
        {loading && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="glass-premium rounded-3xl p-16 text-center border border-white/5"
          >
            <div className="w-14 h-14 border-4 border-orange-500/20 border-t-orange-500 rounded-full animate-spin mx-auto mb-5" />
            <p className="text-sm font-black uppercase tracking-[0.25em] text-slate-500">Traversing Dependency Graph...</p>
          </motion.div>
        )}

        {report && !loading && (
          <motion.div
            key="report"
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            {/* Root Cause Card */}
            <div className={clsx(
              'rounded-3xl p-8 border relative overflow-hidden',
              report.root_cause_id === report.target_resource_id
                ? 'glass-premium border-orange-500/20 bg-orange-500/[0.02]'
                : 'glass-premium border-rose-500/20 bg-rose-500/[0.02]'
            )}>
              <div className="absolute top-0 right-0 w-48 h-48 bg-rose-500/3 blur-3xl -mr-24 -mt-24 pointer-events-none" />

              <div className="flex items-start justify-between gap-6 relative z-10">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-4">
                    <Target className="w-5 h-5 text-rose-400" />
                    <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Root Cause Identified</span>
                  </div>
                  <h2 className="text-2xl font-black text-white tracking-tight mb-2">
                    {report.root_cause_name || 'Self-Originated Failure'}
                  </h2>
                  <p className="text-[10px] font-mono text-slate-500 bg-white/5 rounded-lg px-3 py-1.5 inline-block">
                    {report.root_cause_id}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  {/* Confidence meter */}
                  <div className="text-right">
                    <div className="text-2xl font-black font-mono" style={{ color: confidenceColor }}>
                      {report.confidence_score?.toFixed(0)}%
                    </div>
                    <div className="text-[9px] font-black uppercase tracking-widest text-slate-600">Confidence</div>
                  </div>
                  <div className="w-24 h-2 bg-white/5 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${report.confidence_score}%` }}
                      style={{ background: confidenceColor }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Recommendation */}
            <div className="glass-premium rounded-3xl p-6 border border-indigo-500/15 bg-indigo-500/[0.02]">
              <div className="flex items-start gap-3">
                <Brain className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-[10px] font-black uppercase tracking-widest text-indigo-400 mb-2">AI Recommendation</p>
                  <p className="text-sm text-slate-300 leading-relaxed">{report.recommendation}</p>
                </div>
              </div>
            </div>

            {/* Causal chain */}
            {report.causal_chain?.length > 0 && (
              <div className="glass-premium rounded-3xl p-6 border border-white/5 space-y-4">
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                  <GitBranch className="w-4 h-4" /> Causal Chain ({report.causal_chain.length} hops)
                </h3>
                <CausalChain chain={report.causal_chain} rootCauseId={report.root_cause_id} />
              </div>
            )}

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'Blast Radius', value: report.blast_radius?.length || 0, color: '#f59e0b', icon: RadioTower },
                { label: 'Causal Hops', value: report.causal_chain?.length || 1, color: '#0ea5e9', icon: ChevronRight },
                { label: 'Root Candidates', value: report.root_nodes?.length || 0, color: '#a855f7', icon: Zap },
              ].map((s) => (
                <div key={s.label} className="glass-premium rounded-2xl p-5 border border-white/5 text-center">
                  <s.icon className="w-5 h-5 mx-auto mb-2" style={{ color: s.color }} />
                  <div className="text-2xl font-black font-mono" style={{ color: s.color }}>{s.value}</div>
                  <div className="text-[9px] font-black uppercase tracking-widest text-slate-600 mt-1">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Blast radius nodes */}
            {report.affected_nodes?.length > 0 && (
              <div className="glass-premium rounded-3xl border border-white/5 overflow-hidden">
                <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    Blast Radius — {report.affected_nodes.length} Downstream Node(s)
                  </h3>
                </div>
                <div className="divide-y divide-white/[0.03]">
                  {report.affected_nodes.map((n) => (
                    <AffectedNodeRow key={n.resource_id} node={n} />
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {!report && !loading && (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass-premium rounded-3xl p-20 text-center border border-white/5"
          >
            <div className="w-20 h-20 rounded-3xl bg-white/[0.02] border border-white/5 flex items-center justify-center mx-auto mb-6">
              <Search className="w-10 h-10 text-slate-800" />
            </div>
            <h3 className="text-xl font-black text-white mb-3">Enter a Resource ID</h3>
            <p className="text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
              The RCA engine will traverse your dependency graph to find the true root cause and show you the full blast radius.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
