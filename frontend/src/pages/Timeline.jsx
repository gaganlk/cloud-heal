import { useEffect, useState, useCallback } from 'react'
import { 
  Clock, RefreshCw, Filter, AlertTriangle, Info, 
  CheckCircle2, XCircle, User, Scan, Plus,
  Activity, Calendar, ChevronRight, Hash, Database
} from 'lucide-react'
import { getTimeline } from '../api/healing'
import { formatDistanceToNow, format } from 'date-fns'
import { clsx } from 'clsx'
import toast from 'react-hot-toast'
import { motion, AnimatePresence } from 'framer-motion'
import { TableSkeleton } from '../components/common/Skeleton'

const SEVERITY_STYLES = {
  info: { icon: Info, color: 'text-sky-400', bg: 'bg-sky-400/10', dot: 'bg-sky-400', border: 'border-sky-400/20' },
  warning: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-400/10', dot: 'bg-orange-400', border: 'border-orange-400/20' },
  error: { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-400/10', dot: 'bg-rose-400', border: 'border-rose-500/20' },
  critical: { icon: AlertTriangle, color: 'text-rose-500', bg: 'bg-rose-500/15', dot: 'bg-rose-500', border: 'border-rose-500/30' },
  success: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-400/10', dot: 'bg-emerald-400', border: 'border-emerald-500/20' },
}

const ETYPE_LABELS = {
  user_registered: 'Security / Profile Init',
  user_login: 'Security / Access Grant',
  credential_added: 'Nexus / Cloud Connect',
  scan_completed: 'Engine / Discovery',
  scan_failed: 'Engine / Interference',
  healing_triggered: 'Autonomous / Override',
  healing_completed: 'Autonomous / Restored',
}

function TimelineItem({ event, isLast }) {
  const style = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.info
  const SIcon = style.icon

  return (
    <div className="flex gap-6 group">
      {/* Visual Line Path */}
      <div className="flex flex-col items-center">
        <div className={clsx(
          'w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 border transition-all duration-500 group-hover:scale-110 shadow-lg',
          style.bg, style.border
        )}>
          <SIcon className={clsx('w-4 h-4', style.color)} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-gradient-to-b from-white/10 to-transparent my-2" />}
      </div>

      {/* Entry Card */}
      <div className="flex-1 pb-10">
        <motion.div 
          whileHover={{ x: 5 }}
          className="glass-premium rounded-3xl p-6 border-white/5 hover:border-white/10 transition-all relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-24 h-24 bg-white/[0.01] blur-2xl -mr-12 -mt-12" />
          
          <div className="flex items-center justify-between gap-4 mb-4">
            <div className="flex items-center gap-3">
               <span className={clsx('px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border', style.bg, style.color, style.border)}>
                {ETYPE_LABELS[event.event_type] || event.event_type.replace(/_/g, ' ')}
               </span>
            </div>
            <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-tighter">
               <Clock className="w-3 h-3" />
               <time title={event.created_at}>
                 {event.created_at ? formatDistanceToNow(new Date(event.created_at), { addSuffix: true }) : '—'}
               </time>
            </div>
          </div>

          <p className="text-sm font-bold text-white leading-relaxed tracking-tight">{event.description}</p>
          
          {event.resource_id && (
            <div className="mt-4 pt-4 border-t border-white/5 flex items-center gap-2">
               <Database className="w-3 h-3 text-slate-600" />
               <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Target UUID:</span>
               <span className="text-[9px] font-black text-sky-400 font-mono bg-sky-500/5 px-2 py-0.5 rounded-md">{event.resource_id}</span>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}

export default function Timeline() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [limit, setLimit] = useState(50)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await getTimeline(limit)
      setEvents(res.data)
    } catch {
      toast.error('Uplink to audit log failed')
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => { load() }, [load])

  const filtered = filter === 'all' ? events : events.filter((e) => e.severity === filter)
  const counts = { info: 0, warning: 0, error: 0, critical: 0 }
  events.forEach((e) => { counts[e.severity] = (counts[e.severity] || 0) + 1 })

  const grouped = filtered.reduce((acc, event) => {
    const date = event.created_at ? format(new Date(event.created_at), 'MMMM do, yyyy') : 'Indeterminate Time'
    if (!acc[date]) acc[date] = []
    acc[date].push(event)
    return acc
  }, {})

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-10 pb-20"
    >
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <Activity className="w-8 h-8 text-pink-400" />
            Audit Protocol
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium max-w-sm">
            immutable chronostreams documenting every neural decision and system mutation.
          </p>
        </div>
        <button id="refresh-timeline" onClick={load} disabled={loading} className="btn-secondary-glass flex items-center gap-2 px-6">
          <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} /> Synchronize Log
        </button>
      </div>

      {/* Intelligence Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Global Logs', value: events.length, color: 'text-white' },
          { label: 'Threat Warnings', value: counts.warning, color: 'text-orange-400' },
          { label: 'Critical Errors', value: counts.error + counts.critical, color: 'text-rose-500' },
          { label: 'System Signals', value: counts.info, color: 'text-sky-400' },
        ].map((s) => (
          <div key={s.label} className="glass-premium rounded-3xl p-6 border border-white/5 relative overflow-hidden group">
            <div className="absolute top-0 left-0 w-16 h-16 bg-white/[0.01] group-hover:bg-white/[0.03] transition-colors -z-10" />
            <div className={clsx('text-3xl font-black font-mono leading-none mb-2', s.color)}>{s.value}</div>
            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filter Matrix */}
      <div className="flex items-center gap-4 py-2 border-y border-white/5">
        <span className="text-[10px] font-black text-slate-600 uppercase tracking-[0.3em] flex items-center gap-2">
           <Filter className="w-3 h-3" /> Core Filter
        </span>
        <div className="flex flex-wrap gap-2">
          {['all', 'info', 'warning', 'error', 'critical'].map((f) => {
            const active = filter === f
            const style = f === 'all' ? { color: 'text-white', bg: 'bg-white/10' } : SEVERITY_STYLES[f]
            return (
              <button
                key={f}
                id={`timeline-filter-${f}`}
                onClick={() => setFilter(f)}
                className={clsx(
                  'px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest transition-all duration-300',
                  active ? `${style.bg} ${style.color} shadow-lg ring-1 ${style.border}` : 'text-slate-500 hover:text-slate-300'
                )}
              >
                {active ? f : f[0]}
              </button>
            )
          })}
        </div>
      </div>

      {/* Timeline Stream */}
      {loading ? (
        <div className="space-y-8 animate-pulse">
           {[1,2,3].map(i => <div key={i} className="h-32 glass-premium rounded-[2.5rem]" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-premium rounded-[3rem] p-24 text-center border border-white/5">
          <Calendar className="w-16 h-16 mx-auto mb-6 text-slate-800" />
          <h3 className="text-xl font-black text-white tracking-tight">Zero Events Logged</h3>
          <p className="text-sm text-slate-600 font-medium max-w-xs mx-auto">
             No chronostreams matching current filter topology were found in the audit vault.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([date, dayEvents]) => (
            <div key={date}>
              <div className="flex items-center gap-6 mb-10">
                <span className="text-[11px] font-black text-slate-500 uppercase tracking-[0.4em] whitespace-nowrap">{date}</span>
                <div className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
              </div>
              {dayEvents.map((event, i) => (
                <TimelineItem
                  key={event.id}
                  event={event}
                  isLast={i === dayEvents.length - 1 && date === Object.keys(grouped).at(-1)}
                />
              ))}
            </div>
          ))}

          {events.length >= limit && (
            <div className="text-center pt-8">
              <button
                id="load-more-timeline"
                onClick={() => setLimit((l) => l + 50)}
                className="btn-secondary-glass !px-10 !py-4 text-xs font-black uppercase tracking-[0.2em]"
              >
                Recall Older Streams
              </button>
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
}
