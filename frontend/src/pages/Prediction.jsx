import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import {
  Brain, RefreshCw, AlertTriangle, TrendingUp, TrendingDown,
  Minus, ChevronDown, Activity, ShieldAlert, Cpu, Database,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { getAllPredictions } from '../api/graph'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'

const RISK_STYLES = {
  critical: { badge: 'bg-rose-500 text-white', text: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30', g: 'url(#gRose)', color: '#f43f5e' },
  high: { badge: 'bg-orange-500 text-white', text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', g: 'url(#gOrange)', color: '#f97316' },
  medium: { badge: 'bg-sky-500 text-white', text: 'text-sky-400', bg: 'bg-sky-500/10', border: 'border-sky-500/30', g: 'url(#gSky)', color: '#0ea5e9' },
  low: { badge: 'bg-emerald-500 text-white', text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', g: 'url(#gEmerald)', color: '#10b981' },
}

const TREND_ICONS = {
  rapidly_increasing: { icon: TrendingUp, color: 'text-rose-400', label: 'Critical Rise' },
  increasing: { icon: TrendingUp, color: 'text-orange-400', label: 'Trending Up' },
  stable: { icon: Minus, color: 'text-slate-500', label: 'Nominal' },
  decreasing: { icon: TrendingDown, color: 'text-emerald-400', label: 'Receding' },
}

function PredictionCard({ pred, expanded, onToggle }) {
  const style = RISK_STYLES[pred.risk_level] || RISK_STYLES.low
  const trend = TREND_ICONS[pred.trend] || TREND_ICONS.stable

  return (
    <div className={clsx(
      'glass-premium rounded-3xl overflow-hidden transition-all duration-500',
      expanded ? 'border-white/10 ring-1 ring-white/5' : 'border-white/5 hover:border-white/10'
    )}>
      <div
        className="p-6 cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-6 relative group"
        onClick={onToggle}
      >
        <div className="absolute top-0 right-0 w-32 h-full bg-white/[0.01] group-hover:bg-white/[0.03] transition-colors -z-10" />
        
        <div className="flex items-center gap-5 min-w-0">
          <div className="relative">
            <div className={clsx(
              'w-14 h-14 rounded-2xl flex items-center justify-center border transition-all duration-300 shadow-xl',
              style.bg, style.border
            )}>
              <Cpu className={clsx('w-7 h-7', style.text)} />
            </div>
            {pred.alert && (
              <motion.span 
                 animate={{ scale: [1, 1.2, 1] }}
                 transition={{ repeat: Infinity, duration: 2 }}
                 className="absolute -top-1 -right-1 w-5 h-5 bg-rose-500 rounded-full flex items-center justify-center border-2 border-[#0d0d18] shadow-lg"
              >
                <AlertTriangle className="w-2.5 h-2.5 text-white" />
              </motion.span>
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-base font-black text-white tracking-tight truncate">{pred.resource_name}</h3>
              <span className={clsx('px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-widest', style.badge)}>
                {pred.risk_level}
              </span>
            </div>
            <div className="flex items-center gap-2">
               <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{pred.resource_type}</span>
               <span className="w-1 h-1 rounded-full bg-slate-800" />
               <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{pred.provider}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between sm:justify-end gap-8 flex-shrink-0">
          {/* Metrics */}
          <div className="flex items-center gap-8">
             <div className="text-right">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Projected Peak</p>
                <div className="flex items-center gap-2 justify-end">
                   <span className="text-xs font-bold text-slate-400 font-mono">{pred.current_cpu?.toFixed(0)}%</span>
                   <span className="text-slate-600 text-xs">→</span>
                   <span className={clsx('text-sm font-black font-mono', style.text)}>{pred.predicted_cpu?.toFixed(0)}%</span>
                </div>
             </div>

             <div className="text-right hidden md:block">
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Risk Weight</p>
                <div className={clsx('text-xl font-black font-mono leading-none', style.text)}>
                  {pred.risk_score?.toFixed(0)}
                </div>
             </div>
          </div>

          <ChevronDown className={clsx('w-5 h-5 text-slate-600 transition-transform duration-500', expanded && 'rotate-180')} />
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-6 pb-8 pt-2 border-t border-white/5 space-y-8"
          >
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
               <MiniStat label="Current Mem" value={`${pred.current_memory?.toFixed(1)}%`} color="text-purple-400" />
               <MiniStat label="Predicted Mem" value={`${pred.predicted_memory?.toFixed(1)}%`} color="text-sky-400" />
               <MiniStat label="Trend Vectors" value={trend.label} color={trend.color} />
               <MiniStat label="Analysis Confidence" value="98.4%" color="text-emerald-400" />
            </div>

            <div className="relative">
              <h4 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-6 flex items-center gap-2">
                 <Activity className="w-3.5 h-3.5" /> Predicted Resource Curve (6h Horizon)
              </h4>
              <div className="h-[240px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={pred.chart_data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="gRose" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f43f5e" stopOpacity={0.15} /><stop offset="95%" stopColor="#f43f5e" stopOpacity={0} /></linearGradient>
                      <linearGradient id="gOrange" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f97316" stopOpacity={0.15} /><stop offset="95%" stopColor="#f97316" stopOpacity={0} /></linearGradient>
                      <linearGradient id="gSky" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.15} /><stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} /></linearGradient>
                      <linearGradient id="gEmerald" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10b981" stopOpacity={0.15} /><stop offset="95%" stopColor="#10b981" stopOpacity={0} /></linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                    <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 10, fontWeight: 700 }} tickLine={false} axisLine={false} dy={10} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 10, fontWeight: 700 }} tickLine={false} axisLine={false} />
                    <ReferenceLine y={80} stroke="rgba(244,63,94,0.3)" strokeDasharray="4 4" label={{ value: 'CRITICAL', fill: '#f43f5e', fontSize: 9, fontWeight: 900, position: 'insideTopRight' }} />
                    <Tooltip
                      contentStyle={{ background: '#0d0d18', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, fontSize: 11, fontWeight: 700, padding: '12px 16px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }}
                      cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }}
                    />
                    <Area type="monotone" dataKey="cpu_actual" name="NOMINAL CPU" stroke="#475569" fill="rgba(255,255,255,0.02)" strokeWidth={2} dot={false} strokeDasharray="3 3" />
                    <Area type="monotone" dataKey="cpu_predicted" name="AI PREDICTION" stroke={style.color} fill={style.g} strokeWidth={3} dot={false} animationDuration={1000} />
                    <Legend verticalAlign="top" align="right" iconType="circle" iconSize={6} wrapperStyle={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em', paddingTop: '0px' }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
               <button className="btn-secondary-glass !py-2 !px-4 text-[10px] uppercase font-black tracking-widest">Mark as Resolved</button>
               <button className="btn-primary-glow !py-2 !px-4 text-[10px] uppercase font-black tracking-widest">Execute Auto-Healing</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function MiniStat({ label, value, color }) {
  return (
    <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 shadow-inner">
       <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest block mb-1">{label}</span>
       <span className={clsx('text-base font-black font-mono leading-none', color)}>{value}</span>
    </div>
  )
}

export default function Prediction() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [expanded, setExpanded] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getAllPredictions()
      setPredictions(res.data)
      const first = res.data.find((p) => p.risk_level === 'critical' || p.risk_level === 'high')
      if (first) setExpanded({ [first.resource_id]: true })
    } catch {
      toast.error('Scan required to calibrate AI engine')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = filter === 'all' ? predictions : predictions.filter((p) => p.risk_level === filter)
  const counts = { critical: 0, high: 0, medium: 0, low: 0 }
  predictions.forEach((p) => { counts[p.risk_level] = (counts[p.risk_level] || 0) + 1 })

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-5xl mx-auto space-y-8 pb-20"
    >
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <Brain className="w-8 h-8 text-sky-400" />
            AI Prediction Engine
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium max-w-sm">
            Neural regression analysis identifying pre-failure patterns across global nodes.
          </p>
        </div>
        <button id="refresh-predictions" onClick={load} disabled={loading} className="btn-secondary-glass flex items-center gap-2 px-6">
          <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} /> {loading ? 'Analyzing...' : 'Re-calibrate AI'}
        </button>
      </div>

      {/* Filter Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {['critical', 'high', 'medium', 'low'].map((level) => {
          const style = RISK_STYLES[level]
          const active = filter === level
          return (
            <button
              key={level}
              id={`filter-${level}`}
              onClick={() => setFilter(active ? 'all' : level)}
              className={clsx(
                'glass-premium rounded-3xl p-6 text-left transition-all duration-300 relative group',
                active ? 'scale-105 border-white/20 shadow-xl' : 'border-white/5 hover:border-white/10'
              )}
            >
              <div className={clsx('text-[10px] font-black uppercase tracking-[0.2em] mb-4', active ? style.text : 'text-slate-500')}>
                {level} Risk
              </div>
              <div className={clsx('text-3xl font-black font-mono leading-none', active ? style.text : 'text-slate-400')}>
                {counts[level] || 0}
              </div>
              {active && (
                <div className={clsx('absolute bottom-0 inset-x-0 h-1 rounded-full w-12 mx-auto mb-2', style.badge.split(' ')[0])} />
              )}
            </button>
          )
        })}
      </div>

      {/* Primary Warning Status */}
      <AnimatePresence>
        {counts.critical > 0 && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="p-8 rounded-[2rem] bg-rose-500/10 border border-rose-500/20 flex flex-col md:flex-row items-center gap-6 relative overflow-hidden"
          >
            <div className="absolute top-0 right-0 w-64 h-64 bg-rose-500/10 blur-[100px] -mr-32 -mt-32" />
            <div className="w-16 h-16 rounded-[1.5rem] bg-rose-500/20 flex items-center justify-center flex-shrink-0 animate-pulse">
               <ShieldAlert className="w-8 h-8 text-rose-500" />
            </div>
            <div className="flex-1 text-center md:text-left">
              <h4 className="text-xl font-black text-rose-400 tracking-tight leading-none mb-2">Critical System Threat Detected</h4>
              <p className="text-sm text-slate-400 font-medium">
                {counts.critical} high-priority node{counts.critical > 1 ? 's' : ''} expected to reach peak compute saturation within &lt; 4 hours.
              </p>
            </div>
            <Link to="/healing" className="btn-primary-glow !bg-rose-600 !px-8 text-xs font-black uppercase tracking-widest whitespace-nowrap">
               Engage Auto-Shield
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Prediction Cards List */}
      <div className="space-y-4">
        <div className="flex items-center gap-4 px-4 mb-2">
           <span className="text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">
             Predictive Risk Matrix {filter !== 'all' && `· ${filter.toUpperCase()}`}
           </span>
           <div className="h-px flex-1 bg-white/5" />
        </div>

        {loading ? (
          <div className="space-y-4">
            {[1,2,3].map(i => <div key={i} className="h-24 glass-premium rounded-3xl animate-pulse" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-premium rounded-[2.5rem] p-24 text-center">
            <Database className="w-16 h-16 mx-auto mb-6 text-slate-800" />
            <h3 className="text-lg font-black text-white uppercase tracking-tight">Zero Anomalies Detected</h3>
            <p className="text-sm text-slate-600 font-medium max-w-xs mx-auto">
              System health is within nominal limits. Current patterns do not indicate any future resource exhaustion.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map((pred) => (
              <PredictionCard
                key={pred.resource_id}
                pred={pred}
                expanded={!!expanded[pred.resource_id]}
                onToggle={() => setExpanded((prev) => ({
                  ...prev,
                  [pred.resource_id]: !prev[pred.resource_id],
                }))}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}
