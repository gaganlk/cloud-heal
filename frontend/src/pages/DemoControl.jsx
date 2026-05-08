import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, Zap, Shield, HeartPulse, Activity, DollarSign,
  RotateCcw, CheckCircle2, Loader2, AlertTriangle, Info,
  Radio, Trash2, ChevronRight, Terminal
} from 'lucide-react'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { useWebSocket } from '../hooks/useWebSocket'

const API_BASE = '/api/demo'

async function callScenario(path, method = 'POST') {
  const token = JSON.parse(localStorage.getItem('cloud-heal-auth') || '{}')?.state?.token
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

const SCENARIOS = [
  {
    id: 'cpu-spike',
    label: 'CPU Spike + Drift Alert',
    icon: Activity,
    color: '#ef4444',
    glow: 'rgba(239,68,68,0.15)',
    tag: 'DRIFT',
    tagColor: 'bg-rose-500/15 text-rose-400 border-rose-500/20',
    description: 'Injects a critical CPU spike (88–96%) on a live resource. Triggers drift detection, updates the Dashboard realtime chart, and fires a WarRoom alert. Auto-reverts in 90 seconds.',
    impact: ['Dashboard metric chart spikes live', 'WarRoom shows CPU alert banner', 'Drift Detection page shows new report', 'Event Timeline logs a critical entry'],
    endpoint: '/scenario/cpu-spike',
  },
  {
    id: 'security-alert',
    label: 'Security Group Exposure',
    icon: Shield,
    color: '#f59e0b',
    glow: 'rgba(245,158,11,0.15)',
    tag: 'SECURITY',
    tagColor: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    description: 'Simulates an open security group with SSH port 22 exposed to 0.0.0.0/0. Fires a critical WebSocket alert visible in WarRoom, Security page, and Event Timeline immediately.',
    impact: ['Security page shows new critical finding', 'WarRoom terminal logs security event', 'Event Timeline gets critical entry', 'Notification bell increments'],
    endpoint: '/scenario/security-alert',
  },
  {
    id: 'trigger-healing',
    label: 'AI Healing Suggestion',
    icon: HeartPulse,
    color: '#10b981',
    glow: 'rgba(16,185,129,0.15)',
    tag: 'HEALING',
    tagColor: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    description: 'AI engine detects memory pressure and creates a healing action requiring human approval. Appears instantly in the WarRoom approval queue and Healing page ledger.',
    impact: ['WarRoom shows approval card', 'Healing page shows pending action', 'WarRoom terminal logs AI decision', 'Approve/Reject buttons are functional'],
    endpoint: '/scenario/trigger-healing',
  },
  {
    id: 'activity-burst',
    label: 'Live Dashboard Activity',
    icon: Radio,
    color: '#0ea5e9',
    glow: 'rgba(14,165,233,0.15)',
    tag: 'REALTIME',
    tagColor: 'bg-sky-500/15 text-sky-400 border-sky-500/20',
    description: 'Fires 10 seconds of live metric broadcasts — CPU, memory, health score fluctuating in real time. Best demo for screen recording: shows the Dashboard chart animating live.',
    impact: ['Dashboard realtime chart animates', 'WarRoom sparklines update live', 'TopBar metric pills change', 'WebSocket LIVE indicator pulses'],
    endpoint: '/scenario/activity-burst',
  },
  {
    id: 'cost-spike',
    label: 'FinOps Cost Anomaly',
    icon: DollarSign,
    color: '#a855f7',
    glow: 'rgba(168,85,247,0.15)',
    tag: 'FINOPS',
    tagColor: 'bg-purple-500/15 text-purple-400 border-purple-500/20',
    description: 'Injects a $340–890 spending anomaly (4.2× above 30-day baseline) into the event log. Triggers FinOps alert broadcast and appears in the Timeline audit stream.',
    impact: ['WarRoom terminal logs FinOps warning', 'Event Timeline shows cost anomaly', 'Notification panel updates', 'FinOps page reflects new event'],
    endpoint: '/scenario/cost-spike',
  },
]

function ScenarioCard({ scenario, onRun, running, lastResult }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = scenario.icon
  const isRunning = running === scenario.id

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'glass-premium rounded-2xl border overflow-hidden transition-all duration-300',
        isRunning ? 'border-white/20 ring-1' : 'border-white/5 hover:border-white/10',
      )}
      style={isRunning ? { ringColor: scenario.color } : {}}
    >
      <div
        className="flex items-center justify-between p-5 cursor-pointer hover:bg-white/[0.02] transition-all"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 border border-white/10"
            style={{ background: scenario.glow }}
          >
            <Icon className="w-5 h-5" style={{ color: scenario.color }} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <h3 className="text-sm font-black text-white tracking-tight">{scenario.label}</h3>
              <span className={clsx('text-[8px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border', scenario.tagColor)}>
                {scenario.tag}
              </span>
            </div>
            <p className="text-[10px] text-slate-500 font-medium leading-relaxed line-clamp-1">{scenario.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 ml-4 flex-shrink-0">
          {lastResult?.id === scenario.id && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className={clsx(
                'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[9px] font-black uppercase border',
                lastResult.ok
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              )}
            >
              {lastResult.ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
              {lastResult.ok ? 'Injected' : 'Failed'}
            </motion.div>
          )}
          <button
            id={`demo-run-${scenario.id}`}
            onClick={(e) => { e.stopPropagation(); onRun(scenario) }}
            disabled={!!running}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all duration-200',
              isRunning
                ? 'bg-white/5 text-slate-400 border-white/10 cursor-not-allowed'
                : 'border-white/10 text-white hover:border-white/20 hover:bg-white/5'
            )}
            style={!running && !isRunning ? { boxShadow: `0 0 20px ${scenario.glow}` } : {}}
          >
            {isRunning
              ? <><Loader2 className="w-3 h-3 animate-spin" /> Running</>
              : <><Play className="w-3 h-3" style={{ color: scenario.color }} /> Fire</>
            }
          </button>
          <ChevronRight className={clsx('w-4 h-4 text-slate-600 transition-transform duration-200', expanded && 'rotate-90')} />
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/5"
          >
            <div className="p-5 grid sm:grid-cols-2 gap-4">
              <div>
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">What happens</p>
                <p className="text-xs text-slate-300 leading-relaxed">{scenario.description}</p>
              </div>
              <div>
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Observable effects</p>
                <ul className="space-y-1">
                  {scenario.impact.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-[10px] text-slate-400">
                      <span className="w-1 h-1 rounded-full mt-1.5 flex-shrink-0" style={{ background: scenario.color }} />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function DemoControl() {
  const [running, setRunning] = useState(null)
  const [results, setResults] = useState([])
  const [lastResult, setLastResult] = useState(null)
  const [resetting, setResetting] = useState(false)
  const { connected } = useWebSocket()

  const runScenario = async (scenario) => {
    setRunning(scenario.id)
    const toastId = toast.loading(`Firing: ${scenario.label}...`)
    try {
      const data = await callScenario(scenario.endpoint)
      toast.dismiss(toastId)
      toast.success(`✅ ${scenario.label} — scenario active`, { duration: 5000 })
      const result = { id: scenario.id, ok: true, data, ts: new Date() }
      setLastResult(result)
      setResults(prev => [result, ...prev.slice(0, 19)])
    } catch (err) {
      toast.dismiss(toastId)
      toast.error(`${scenario.label} failed: ${err.message}`)
      const result = { id: scenario.id, ok: false, error: err.message, ts: new Date() }
      setLastResult(result)
      setResults(prev => [result, ...prev.slice(0, 19)])
    } finally {
      setRunning(null)
    }
  }

  const resetDemo = async () => {
    setResetting(true)
    try {
      await callScenario('/reset', 'DELETE')
      toast.success('Demo data cleared — platform reset to clean state')
      setResults([])
      setLastResult(null)
    } catch (err) {
      toast.error(`Reset failed: ${err.message}`)
    } finally {
      setResetting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-8 pb-20"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <Zap className="w-8 h-8 text-yellow-400" />
            Demo Control Panel
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium max-w-md">
            Fire controlled, real-architecture scenarios for live demos and portfolio walkthroughs. All scenarios inject real data through the actual backend — no UI mocking.
          </p>
        </div>
        <button
          id="demo-reset"
          onClick={resetDemo}
          disabled={resetting || !!running}
          className="btn-secondary-glass flex items-center gap-2 !border-rose-500/20 !text-rose-400 hover:!bg-rose-500/10"
        >
          {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          Reset Demo Data
        </button>
      </div>

      {/* WS Connection Warning */}
      {!connected && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-3 px-5 py-4 rounded-2xl bg-amber-500/10 border border-amber-500/20"
        >
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
          <div>
            <p className="text-sm font-black text-white">WebSocket not connected</p>
            <p className="text-[10px] text-slate-400 font-medium mt-0.5">Scenarios will still inject data, but realtime UI effects won't be visible until connection is restored.</p>
          </div>
        </motion.div>
      )}

      {/* How to demo guide */}
      <div className="glass-premium rounded-3xl p-6 border border-indigo-500/10 bg-indigo-500/[0.02]">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-black text-white mb-2">Recommended Demo Sequence</p>
            <div className="grid sm:grid-cols-2 gap-x-8 gap-y-1">
              {[
                '1. Open War Room and Dashboard side-by-side',
                '2. Fire "Live Dashboard Activity" — show realtime chart',
                '3. Fire "CPU Spike" — show drift detection + alert banner',
                '4. Fire "AI Healing Suggestion" — approve in War Room',
                '5. Fire "Security Alert" — show Security page update',
                '6. Click Reset to clean state before next walkthrough',
              ].map((step, i) => (
                <p key={i} className="text-[11px] text-slate-400 font-medium py-0.5">{step}</p>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Scenario Cards */}
      <div className="space-y-3">
        <h2 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Available Scenarios</h2>
        {SCENARIOS.map((scenario) => (
          <ScenarioCard
            key={scenario.id}
            scenario={scenario}
            onRun={runScenario}
            running={running}
            lastResult={lastResult}
          />
        ))}
      </div>

      {/* Execution Log */}
      {results.length > 0 && (
        <div className="glass-premium rounded-2xl overflow-hidden border border-white/5">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-white/5 bg-white/[0.01]">
            <Terminal className="w-4 h-4 text-slate-500" />
            <h3 className="text-xs font-black text-white uppercase tracking-widest">Execution Log</h3>
          </div>
          <div className="p-4 space-y-2 max-h-60 overflow-y-auto custom-scrollbar font-mono">
            {results.map((r, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex items-center gap-3 text-[10px]"
              >
                <span className="text-slate-600">{r.ts.toLocaleTimeString('en', { hour12: false })}</span>
                {r.ok
                  ? <span className="text-emerald-400">[OK]</span>
                  : <span className="text-rose-400">[FAIL]</span>
                }
                <span className="text-slate-400">
                  {SCENARIOS.find(s => s.id === r.id)?.label}
                  {r.data?.resource && <span className="text-slate-600"> → {r.data.resource}</span>}
                  {r.error && <span className="text-rose-400"> — {r.error}</span>}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  )
}
