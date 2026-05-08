import { useState, useCallback, useEffect } from 'react'
import {
  Zap, Play, AlertTriangle, ChevronRight, Server,
  ArrowDown, Shield, RefreshCw, Layers, Activity,
  Globe, Cpu, Database, Skull, Sparkles
} from 'lucide-react'
import { simulatePropagation, getPropagationResources } from '../api/graph'
import { listCredentials } from '../api/credentials'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'

const SEVERITY_STYLES = {
  critical: { color: '#f43f5e', bg: 'bg-rose-500/10', border: 'border-rose-500/30', badge: 'bg-rose-500 text-white' },
  high: { color: '#f97316', bg: 'bg-orange-500/10', border: 'border-orange-500/30', badge: 'bg-orange-500 text-white' },
  medium: { color: '#0ea5e9', bg: 'bg-sky-500/10', border: 'border-sky-500/30', badge: 'bg-sky-500 text-white' },
  low: { color: '#10b981', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', badge: 'bg-emerald-500 text-white' },
}

const ACTION_ICONS = {
  restart: '🔄', scale_up: '📈', reroute: '↩️', isolate: '🔒', failover: '⚡', rollback: '⏪',
}

export default function Propagation() {
  const [creds, setCreds] = useState([])
  const [selectedCred, setSelectedCred] = useState('')
  const [resources, setResources] = useState([])
  const [selectedNode, setSelectedNode] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingResources, setLoadingResources] = useState(false)

  useEffect(() => {
    listCredentials().then((r) => {
      setCreds(r.data)
      if (r.data.length > 0) {
        setSelectedCred(String(r.data[0].id))
        loadResources(r.data[0].id)
      }
    }).catch(() => {})
  }, [])

  const loadResources = useCallback(async (credId) => {
    if (!credId) return
    setLoadingResources(true)
    try {
      const res = await getPropagationResources(credId)
      setResources(res.data || [])
      if (res.data?.length > 0) setSelectedNode(res.data[0].resource_id)
    } catch {
      setResources([])
    } finally {
      setLoadingResources(false)
    }
  }, [])

  const handleSimulate = async () => {
    if (!selectedCred || !selectedNode) {
      toast.error('Select target node for stress simulation')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await simulatePropagation({
        failed_node_id: selectedNode,
        credential_id: parseInt(selectedCred),
        max_depth: 10,
      })
      setResult(res.data)
      toast.success(`Cascade Analysis Complete: ${res.data.total_affected} nodes impacted`)
    } catch (err) {
      toast.error('Simulation calibration failed')
    } finally {
      setLoading(false)
    }
  }

  const failedRes = resources.find((r) => r.resource_id === selectedNode)
  const style = result ? SEVERITY_STYLES[result.severity] || SEVERITY_STYLES.low : null

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-6xl mx-auto space-y-8 pb-20"
    >
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <Zap className="w-8 h-8 text-orange-400" />
            Propagation Lab
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium max-w-sm">
            Stress-test your architecture by injecting synthetic failures and analyzing cascade vectors.
          </p>
        </div>
      </div>

      {/* Main split */}
      <div className="grid lg:grid-cols-5 gap-8">
         {/* Sidebar Controls */}
         <div className="lg:col-span-2 space-y-6">
            <div className="glass-premium rounded-[2rem] p-8 border border-white/5 relative overflow-hidden">
               <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/5 blur-3xl -mr-16 -mt-16" />
               <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-8 flex items-center gap-2">
                  <Activity className="w-4 h-4" /> Lab Configuration
               </h3>

               <div className="space-y-6 mb-8 relative z-10">
                  <div>
                    <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest block mb-2 px-1">Target Account</label>
                    <select
                      id="prop-cred"
                      value={selectedCred}
                      onChange={(e) => {
                        setSelectedCred(e.target.value)
                        loadResources(e.target.value)
                      }}
                      className="input-premium py-3 px-4 text-xs font-bold"
                      disabled={creds.length === 0}
                    >
                      {creds.length === 0 ? <option>Connect Cloud First</option> : creds.map(c => <option key={c.id} value={c.id}>{c.provider.toUpperCase()} · {c.name}</option>)}
                    </select>
                  </div>

                  <div>
                    <label className="text-[10px] font-black text-slate-600 uppercase tracking-widest block mb-2 px-1">Injected Failure Node</label>
                    <select
                      id="prop-node"
                      value={selectedNode}
                      onChange={(e) => setSelectedNode(e.target.value)}
                      className="input-premium py-3 px-4 text-xs font-bold"
                      disabled={resources.length === 0 || loadingResources}
                    >
                      {loadingResources ? <option>Initializing Nodes...</option> : resources.map(r => <option key={r.resource_id} value={r.resource_id}>[{r.provider.toUpperCase()}] {r.name}</option>)}
                    </select>
                  </div>
               </div>

               {failedRes && (
                 <motion.div 
                   initial={{ opacity: 0, scale: 0.95 }}
                   animate={{ opacity: 1, scale: 1 }}
                   className="p-5 rounded-2xl bg-rose-500/5 border border-rose-500/20 mb-8 flex items-center gap-4 group"
                 >
                    <div className="w-12 h-12 rounded-xl bg-rose-500/10 flex items-center justify-center border border-rose-500/20 shadow-inner group-hover:scale-110 transition-transform">
                       <Skull className="w-6 h-6 text-rose-500" />
                    </div>
                    <div className="min-w-0">
                       <p className="text-xs font-black text-white truncate">{failedRes.name}</p>
                       <p className="text-[9px] font-bold text-rose-500/70 uppercase tracking-widest mt-0.5">Primary Target</p>
                    </div>
                 </motion.div>
               )}

               <button
                 id="run-simulation"
                 onClick={handleSimulate}
                 disabled={loading || !selectedNode}
                 className="btn-primary-glow !bg-gradient-to-r from-orange-500 to-rose-600 w-full !py-4 font-black uppercase tracking-[0.2em] text-xs shadow-2xl"
               >
                 {loading ? <RefreshCw className="w-4 h-4 animate-spin mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                 {loading ? 'Crunching Propagation...' : 'Trigger Simulation'}
               </button>
            </div>
         </div>

         {/* Results Display Area */}
         <div className="lg:col-span-3">
            <AnimatePresence mode="wait">
               {result ? (
                 <motion.div 
                    key="results"
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="space-y-6"
                 >
                    {/* Impact Summary Card */}
                    <div className={clsx('glass-premium rounded-[2rem] p-8 border-white/5 relative overflow-hidden', style.border)}>
                       <div className={clsx('absolute inset-0 opacity-5', style.bg)} />
                       <div className="relative z-10">
                          <div className="flex items-center justify-between mb-8">
                             <div>
                                <span className={clsx('px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest inline-block mb-3 shadow-lg', style.badge)}>
                                   {result.severity} Magnitude
                                </span>
                                <h3 className="text-2xl font-black text-white tracking-tight">Cascade Impact Profile</h3>
                             </div>
                             <div className="text-right">
                                <div className={clsx('text-5xl font-black font-mono leading-none', style.text)}>
                                   {result.total_affected}
                                </div>
                                <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mt-2">Corrupted Nodes</div>
                             </div>
                          </div>

                          <div className="space-y-2">
                             <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-widest">
                                <span className="text-slate-500">Global Structural Harm</span>
                                <span className={style.text}>{result.impact_score?.toFixed(1)}%</span>
                             </div>
                             <div className="h-3 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
                                <motion.div 
                                   initial={{ width: 0 }}
                                   animate={{ width: `${result.impact_score}%` }}
                                   transition={{ duration: 1 }}
                                   className={clsx('h-full rounded-full', style.badge.split(' ')[0])} 
                                   style={{ boxShadow: `0 0 20px ${style.color}40` }}
                                />
                             </div>
                          </div>
                       </div>
                    </div>

                    {/* Cascade Breakdown */}
                    <div className="grid md:grid-cols-2 gap-6">
                       <div className="glass-premium rounded-[2rem] p-6 border border-white/5">
                          <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6 flex items-center gap-2">
                             <Layers className="w-4 h-4" /> Propagation Chain
                          </h4>
                          <div className="space-y-4">
                             <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-500/5 border border-rose-500/10">
                                <Skull className="w-4 h-4 text-rose-500" />
                                <div className="min-w-0">
                                   <p className="text-xs font-black text-white truncate uppercase tracking-tight">{result.failed_node_name}</p>
                                   <p className="text-[9px] font-bold text-rose-500/50 uppercase tracking-widest">Level 0 Origin</p>
                                </div>
                             </div>

                             {Object.entries(result.cascade_levels || {}).sort((a,b) => Number(a[0]) - Number(b[0])).map(([depth, ids]) => (
                               <div key={depth} className="relative pl-6 space-y-3">
                                  <div className="absolute left-2 inset-y-0 w-px bg-white/10" />
                                  <div className="flex items-center gap-2 text-[9px] font-black text-slate-600 uppercase tracking-widest">
                                     <ArrowDown className="w-3 h-3" /> Vector Path {depth}
                                  </div>
                                  {(result.affected_node_details || []).filter(n => ids.includes(n.id)).map(node => (
                                    <div key={node.id} className="p-3 rounded-xl bg-white/[0.02] border border-white/5 flex items-center gap-3 group hover:bg-white/[0.05] transition-colors">
                                       <Zap className="w-3.5 h-3.5 text-orange-400 opacity-50 group-hover:opacity-100 transition-opacity" />
                                       <div className="min-w-0">
                                          <p className="text-[11px] font-bold text-slate-300 truncate">{node.name}</p>
                                          <p className="text-[8px] font-black text-slate-600 uppercase tracking-tighter">{node.resource_type}</p>
                                       </div>
                                    </div>
                                  ))}
                               </div>
                             ))}
                          </div>
                       </div>

                       <div className="glass-premium rounded-[2rem] p-6 border border-white/5">
                          <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6 flex items-center gap-2">
                             <Shield className="w-4 h-4 text-emerald-400" /> Strategic Immunity
                          </h4>
                          <div className="space-y-4">
                             {(result.healing_suggestions || []).map((s, i) => (
                               <div key={i} className="p-5 rounded-2xl bg-white/[0.02] border border-white/10 relative group overflow-hidden">
                                  <div className="absolute top-0 right-0 p-2 opacity-5 scale-150 rotate-12 group-hover:opacity-10 transition-opacity">
                                     <Sparkles className="w-12 h-12" />
                                  </div>
                                  <div className="flex items-start gap-4 relative z-10">
                                     <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-lg border border-emerald-500/20">
                                        {ACTION_ICONS[s.action] || '🔧'}
                                     </div>
                                     <div className="min-w-0 flex-1">
                                        <div className="flex items-center justify-between gap-2 mb-1">
                                           <span className="text-xs font-black text-white uppercase tracking-tight">{s.action?.replace(/_/g, ' ')}</span>
                                           <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[8px] font-black">P{s.priority}</span>
                                        </div>
                                        <p className="text-[11px] text-slate-500 font-medium leading-relaxed mb-3">{s.description}</p>
                                        <div className="flex items-center gap-4 text-[9px] font-black uppercase tracking-widest text-slate-600">
                                           <span className="flex items-center gap-1"><Server className="w-3 h-3" /> {s.target_name}</span>
                                           <span className="text-emerald-500 font-mono">{s.estimated_time}</span>
                                        </div>
                                     </div>
                                  </div>
                               </div>
                             ))}
                             {(!result.healing_suggestions || result.healing_suggestions.length === 0) && (
                                <p className="text-xs text-slate-600 font-bold text-center py-10 italic">No automated immunity scripts available for this vector.</p>
                             )}
                          </div>
                       </div>
                    </div>
                 </motion.div>
               ) : (
                 <motion.div 
                    key="placeholder"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="glass-premium rounded-[3rem] p-20 flex flex-col items-center justify-center text-center h-full border border-white/5 bg-white/[0.01]"
                 >
                    <div className="w-24 h-24 rounded-[2.5rem] bg-white/[0.02] border border-white/5 flex items-center justify-center mb-8 relative">
                       <Zap className="w-12 h-12 text-slate-800" />
                       <div className="absolute inset-x-0 bottom-[-10px] flex justify-center">
                          <div className="px-3 py-1 rounded-full bg-slate-800 text-[9px] font-black uppercase tracking-widest text-slate-500">Standby</div>
                       </div>
                    </div>
                    <h3 className="text-xl font-black text-white tracking-tight mb-2">Simulation Engine Idle</h3>
                    <p className="text-sm text-slate-600 font-medium max-w-xs mx-auto">
                       Calibrate a target failure node to begin real-time cascade propagation analysis.
                    </p>
                 </motion.div>
               )}
            </AnimatePresence>
         </div>
      </div>
    </motion.div>
  )
}
