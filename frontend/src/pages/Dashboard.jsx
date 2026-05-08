import { useEffect, useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Server, Database, Cloud, AlertTriangle, HeartPulse, Activity,
  TrendingUp, TrendingDown, Minus, RefreshCw, ChevronRight, Zap,
  Cpu, HardDrive, ShieldAlert, CheckCircle2, Globe,
} from 'lucide-react'
import { CardSkeleton, TableSkeleton } from '../components/common/Skeleton'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Legend,
} from 'recharts'
import { getStats, getMetrics } from '../api/healing'
import { listCredentials } from '../api/credentials'
import { useWebSocket } from '../hooks/useWebSocket'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'

const PROVIDER_COLORS = { aws: '#f59e0b', gcp: '#4285f4', azure: '#00a4ef' }
const PROVIDER_ICONS = { aws: '🟡', gcp: '🔵', azure: '🔷' }

function StatCard({ icon: Icon, label, value, sub, color, trend, delay = 0 }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass-premium rounded-3xl p-6 relative overflow-hidden group hover-glow"
    >
      <div className="absolute top-0 right-0 w-24 h-24 bg-white/[0.02] blur-2xl -mr-12 -mt-12 group-hover:bg-white/[0.05] transition-colors" />
      
      <div className="flex items-start justify-between mb-6">
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center border border-white/5 shadow-lg"
          style={{ background: `${color}10`, boxShadow: `0 0 20px ${color}15` }}>
          <Icon className="w-6 h-6" style={{ color }} />
        </div>
        {trend !== undefined && (
          <div className={clsx(
            'px-2 py-1 rounded-lg text-[10px] font-black flex items-center gap-1 border',
            trend > 0 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 
            trend < 0 ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
            'bg-slate-500/10 text-slate-500 border-white/5'
          )}>
            {trend > 0 ? <TrendingUp className="w-3 h-3" /> : trend < 0 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      
      <div className="space-y-1">
        <div className="text-3xl font-black text-white tracking-tighter">{value}</div>
        <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</div>
        {sub && <div className="text-[10px] text-slate-600 font-bold mt-1.5">{sub}</div>}
      </div>
    </motion.div>
  )
}

function ResourceRow({ r }) {
  const risk = r.cpu_usage > 80 || r.memory_usage > 85
  const cpuColor = r.cpu_usage > 80 ? '#ef4444' : r.cpu_usage > 60 ? '#f59e0b' : '#34d399'
  const memColor = r.memory_usage > 85 ? '#ef4444' : r.memory_usage > 65 ? '#f59e0b' : '#a855f7'

  return (
    <tr className="group hover:bg-white/[0.03] transition-all duration-300">
      <td className="px-6 py-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-white/[0.03] border border-white/5 flex items-center justify-center text-xl shadow-inner group-hover:scale-110 transition-transform">
            {PROVIDER_ICONS[r.provider] || '☁️'}
          </div>
          <div>
            <div className="text-sm font-bold text-white tracking-tight">{r.name}</div>
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest mt-0.5">{r.resource_type}</div>
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className={clsx(
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border',
          r.status === 'running' || r.status === 'available' || r.status === 'active' 
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
            : 'bg-red-500/10 text-red-400 border-red-500/20'
        )}>
          <span className={clsx('w-1.5 h-1.5 rounded-full', r.status === 'running' ? 'bg-emerald-400' : 'bg-red-500')} />
          {r.status}
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="space-y-1.5">
          <div className="flex justify-between items-center pr-2">
             <span className="text-[9px] font-black text-slate-500 uppercase">CPU</span>
             <span className="text-xs font-black font-mono" style={{ color: cpuColor }}>{r.cpu_usage?.toFixed(1)}%</span>
          </div>
          <div className="h-1.5 w-24 bg-white/5 rounded-full overflow-hidden">
             <motion.div 
               initial={{ width: 0 }}
               animate={{ width: `${r.cpu_usage}%` }}
               className="h-full rounded-full" 
               style={{ background: cpuColor }} 
             />
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="space-y-1.5">
          <div className="flex justify-between items-center pr-2">
             <span className="text-[9px] font-black text-slate-500 uppercase">MEM</span>
             <span className="text-xs font-black font-mono" style={{ color: memColor }}>{r.memory_usage?.toFixed(1)}%</span>
          </div>
          <div className="h-1.5 w-24 bg-white/5 rounded-full overflow-hidden">
             <motion.div 
               initial={{ width: 0 }}
               animate={{ width: `${r.memory_usage}%` }}
               className="h-full rounded-full" 
               style={{ background: memColor }} 
             />
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center gap-1.5">
          <Globe className="w-3 h-3 text-slate-600" />
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{r.region || 'GLOBAL'}</span>
        </div>
      </td>
      <td className="px-6 py-4">
        {risk ? (
           <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center animate-pulse">
             <AlertTriangle className="w-4 h-4 text-red-500" />
           </div>
        ) : (
           <div className="w-8 h-8 rounded-lg bg-emerald-500/5 flex items-center justify-center">
             <CheckCircle2 className="w-4 h-4 text-emerald-500/20" />
           </div>
        )}
      </td>
    </tr>
  )
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const [stats, setStats] = useState(null)
  const [resources, setResources] = useState([])
  const [creds, setCreds] = useState([])
  const [loading, setLoading] = useState(true)
  const [chartData, setChartData] = useState([])
  const [liveMetrics, setLiveMetrics] = useState({ cpu: 0, memory: 0, network: 0 })
  const { lastMessage, connected } = useWebSocket()

  useEffect(() => {
    if (!lastMessage) return

    if (lastMessage.type === 'metrics_update') {
      const d = lastMessage.data
      setLiveMetrics(d)
      setChartData((prev) => [
        ...prev.slice(-19),
        {
          time: new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          cpu: d.cpu,
          memory: d.memory,
          network: d.network,
        },
      ])
    } else if (lastMessage.type === 'resource_state_change') {
      const { resource_id, status } = lastMessage.data
      setResources(prev => prev.map(r => 
        r.resource_id === resource_id ? { ...r, status } : r
      ))
    } else if (lastMessage.type === 'resource_metrics_update') {
      const { resource_id, cpu, memory, network } = lastMessage.data
      setResources(prev => prev.map(r => 
        r.resource_id === resource_id 
          ? { ...r, cpu_usage: cpu, memory_usage: memory, network_usage: network } 
          : r
      ))
    } else if (lastMessage.type === 'resource_discovered') {
      const newResource = lastMessage.data
      setResources(prev => {
        // Prevent duplicates
        if (prev.some(r => r.resource_id === newResource.resource_id)) return prev
        return [newResource, ...prev]
      })
    } else if (lastMessage.type === 'scan_completed') {
      load()
      setLoading(false)
      const count = lastMessage.data?.count ?? 0
      const provider = lastMessage.data?.provider?.toUpperCase() ?? 'Cloud'
      toast.success(`${provider} scan complete — ${count} resources discovered`)
    }

  }, [lastMessage])

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const [statsRes, metricsRes, credsRes] = await Promise.all([
        getStats(), getMetrics(), listCredentials(),
      ])
      setStats(statsRes.data)
      setResources(metricsRes.data)
      setCreds(credsRes.data)
    } catch (e) {
      console.error(e)
      toast.error('Failed to load dashboard data. Retrying...')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const [statsRes, metricsRes] = await Promise.all([getStats(), getMetrics()])
        setStats(statsRes.data)
        setResources(metricsRes.data)
      } catch {}
    }, 15000)
    return () => clearInterval(timer)
  }, [])

  const triggerManualScan = async () => {
    if (!creds.length) {
      toast.error('No cloud accounts connected. Add credentials first.')
      return
    }
    const count = creds.length
    const loadingToast = toast.loading(`Scanning ${count} cloud account${count > 1 ? 's' : ''}...`)
    try {
      setLoading(true)
      const { triggerScan } = await import('../api/scanner')
      await Promise.all(creds.map(c => triggerScan(c.id)))
      toast.dismiss(loadingToast)
      toast('Discovery running — resources will stream in live ✨', { icon: '🔍' })
    } catch (err) {
      console.error('Manual scan trigger failed:', err)
      toast.error('Failed to trigger scan. Check backend connectivity.')
      toast.dismiss(loadingToast)
      setLoading(false)
    }
  }

  const critical = resources.filter((r) => r.cpu_usage > 80 || r.memory_usage > 85)

  if (loading && !resources.length) {
    return (
      <div className="space-y-8 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[1,2,3,4].map(i => <div key={i} className="h-40 glass-premium rounded-3xl" />)}
        </div>
        <div className="h-96 glass-premium rounded-3xl" />
      </div>
    )
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8 pb-12"
    >
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter">
            System Overview, <span className="text-sky-400">{user?.username}</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium">
            Monitoring {stats?.total_resources || 0} active resources across {stats?.total_credentials || 0} secure cloud connections.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="hidden lg:flex flex-col items-end">
            <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Scanner Fleet</span>
            <div className="flex gap-1 mt-1">
              {creds.map(c => (
                <div key={c.id} className={clsx(
                  "w-2 h-2 rounded-full",
                  c.scan_status === 'success' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.4)]' :
                  c.scan_status === 'error' ? 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.4)]' : 'bg-slate-600'
                )} title={`${c.provider}: ${c.scan_status || 'idle'}`} />
              ))}
            </div>
          </div>
          <button id="refresh-dashboard" onClick={triggerManualScan}
            className="btn-secondary-glass flex items-center gap-2 px-6">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Sync Metrics
          </button>
        </div>
      </div>

      {/* Connectivity & Error Banner */}
      <AnimatePresence>
        {(creds.length > 0 && stats?.total_resources === 0) && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-premium rounded-3xl p-6 border-rose-500/20 bg-rose-500/[0.02] flex items-center justify-between overflow-hidden"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-rose-500/10 flex items-center justify-center">
                <ShieldAlert className="w-6 h-6 text-rose-400" />
              </div>
              <div>
                <p className="text-sm font-black text-white uppercase tracking-tight">Ecosystem Status: Idle</p>
                <p className="text-xs text-slate-500 font-medium">Connected accounts are returning 0 resources. Verify IAM permissions ('ec2:DescribeInstances', etc.) or trigger a manual sync.</p>
              </div>
            </div>
            <Link to="/connect" className="btn-secondary-glass !px-6 text-[10px] uppercase font-black tracking-widest border-white/10">
              Manage Credentials
            </Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* No credentials warning */}
      {creds.length === 0 && (
        <motion.div 
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="glass-premium rounded-3xl p-6 border-yellow-500/20 bg-yellow-500/[0.02] flex items-center justify-between"
        >
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-yellow-500/10 flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-yellow-400" />
            </div>
            <div>
              <p className="text-sm font-black text-white uppercase tracking-tight">Ecosystem Not Connected</p>
              <p className="text-xs text-slate-500 font-medium">Connect your first provider to enable autonomous scanning.</p>
            </div>
          </div>
          <Link to="/connect" id="connect-cloud-cta" className="btn-primary-glow !px-6 text-xs uppercase font-black tracking-widest">
            Setup Cloud <ChevronRight className="w-4 h-4 ml-1" />
          </Link>
        </motion.div>
      )}

      {/* Stat cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard icon={Server} label="Infrastructure Units" value={stats?.total_resources || 0}
          sub={`${Object.keys(stats?.providers || {}).length} Active Providers`}
          color="#0ea5e9" trend={2} delay={0.1} />
        <StatCard icon={ShieldAlert} label="Risk Anomalies" value={critical.length}
          sub="Requires Human Attention"
          color={critical.length > 0 ? '#f43f5e' : '#10b981'} delay={0.2} />
        <StatCard icon={Activity} label="Health Index" value={`${stats?.health_score || 0}%`}
          sub={stats?.health_score > 80 ? 'Optimal Status' : 'Degraded State'}
          color="#34d399" trend={1} delay={0.3} />
        <StatCard icon={HeartPulse} label="Autonomous Fixes" value={stats?.healing_total || 0}
          sub={`${stats?.healing_success || 0} Resolved via AI`}
          color="#a855f7" delay={0.4} />
      </div>

      {/* Analytics Hub */}
      <div className="grid lg:grid-cols-3 gap-8">
        {/* Live Area Chart */}
        <div className="lg:col-span-2 glass-premium rounded-[2.5rem] p-8 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-64 h-64 bg-sky-500/5 blur-[100px] -ml-32 -mt-32" />
          
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 relative z-10">
            <div>
              <h3 className="text-lg font-black text-white tracking-tight flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-sky-400" /> Real-time Performance Pulse
              </h3>
              <p className="text-[10px] text-slate-600 font-black uppercase tracking-[0.2em] mt-1">Global compute telemetry</p>
            </div>
            <div className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest border transition-all duration-500',
              connected ? 'bg-emerald-500/5 text-emerald-400 border-emerald-500/20' : 'bg-white/5 text-slate-500 border-white/5'
            )}>
              <span className={clsx('w-2 h-2 rounded-full', connected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600')} />
              {connected ? 'Sync Live' : 'Reconnecting...'}
            </div>
          </div>
          
          <div className="h-[300px] w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gCpu" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gMem" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#a855f7" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                <XAxis dataKey="time" tick={{ fill: '#475569', fontSize: 10, fontWeight: 700 }} tickLine={false} axisLine={false} dy={10} />
                <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 10, fontWeight: 700 }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: '#0d0d18', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, fontSize: 11, fontWeight: 700, padding: '12px 16px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }}
                  itemStyle={{ padding: '2px 0' }}
                  cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }}
                />
                <Area type="monotone" dataKey="cpu" name="CPU LOAD" stroke="#0ea5e9" fill="url(#gCpu)" strokeWidth={3} dot={false} animationDuration={1000} />
                <Area type="monotone" dataKey="memory" name="MEMORY USAGE" stroke="#a855f7" fill="url(#gMem)" strokeWidth={3} dot={false} animationDuration={1000} />
                <Legend 
                  verticalAlign="top" 
                  align="right" 
                  iconType="circle" 
                  iconSize={6} 
                  wrapperStyle={{ fontSize: 9, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.1em', paddingTop: '0px', paddingRight: '10px' }} 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Ecosystem Distribution */}
        <div className="glass-premium rounded-[2.5rem] p-8 relative overflow-hidden">
          <div className="absolute bottom-0 right-0 w-64 h-64 bg-purple-500/5 blur-[100px] -mr-32 -mb-32" />
          
          <h3 className="text-lg font-black text-white tracking-tight mb-8">Ecosystem Mix</h3>
          <div className="space-y-6 relative z-10">
            {Object.entries(stats?.providers || {}).map(([provider, count]) => (
              <div key={provider} className="group">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
                    <span className="text-xl group-hover:scale-125 transition-transform duration-300">
                      {PROVIDER_ICONS[provider]}
                    </span> 
                    {provider}
                  </span>
                  <span className="text-xs font-black font-mono text-white bg-white/5 px-2 py-0.5 rounded-md">{count} Units</span>
                </div>
                <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${stats?.total_resources ? (count / stats.total_resources) * 100 : 0}%` }}
                    className="h-full rounded-full"
                    style={{ background: PROVIDER_COLORS[provider] || '#0ea5e9', boxShadow: `0 0 10px ${PROVIDER_COLORS[provider]}30` }} 
                  />
                </div>
              </div>
            ))}
            {Object.keys(stats?.providers || {}).length === 0 && (
              <div className="flex flex-col items-center py-12 text-center">
                 <Cloud className="w-10 h-10 text-slate-800 mb-2" />
                 <p className="text-xs text-slate-600 font-bold uppercase tracking-widest">No Active Nodes</p>
              </div>
            )}
          </div>

          <div className="mt-10 pt-8 border-t border-white/5 space-y-4 relative z-10">
            <MetricRow label="Aggregate CPU" value={`${stats?.avg_cpu?.toFixed(1) || 0}%`} color="text-sky-400" />
            <MetricRow label="Aggregate RAM" value={`${stats?.avg_memory?.toFixed(1) || 0}%`} color="text-purple-400" />
            <MetricRow label="Critical Assets" value={stats?.critical_resources || 0} color="text-rose-500" />
          </div>
        </div>
      </div>

      {/* Resource Inventory Table */}
      <div className="glass-premium rounded-[2.5rem] overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 px-8 py-6 border-b border-white/5 bg-white/[0.01]">
          <div>
            <h3 className="text-lg font-black text-white tracking-tight">Node Inventory</h3>
            <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest mt-1">{resources.length} active nodes tracked</p>
          </div>
          <Link to="/prediction" className="btn-secondary-glass !py-1.5 !px-4 text-[10px] uppercase font-black tracking-widest flex items-center gap-2">
            AI Predictions <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {resources.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Resource Node</th>
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Runtime Status</th>
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Compute Load</th>
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Memory Commit</th>
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Deployment Region</th>
                  <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                <AnimatePresence>
                  {resources.map((r, idx) => (
                    <ResourceRow key={r.resource_id} r={r} />
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-24">
            <div className="w-20 h-20 rounded-3xl bg-white/[0.02] border border-white/5 flex items-center justify-center mx-auto mb-6">
              <Activity className="w-10 h-10 text-slate-800" />
            </div>
            <p className="text-sm text-slate-500 font-bold uppercase tracking-widest">Discovery Engine Ready</p>
            <Link to="/connect" id="connect-cloud-empty" className="btn-primary-glow mt-8 inline-flex">
              Initial Connection
            </Link>
          </div>
        )}
      </div>

      {/* Quick Launchpad */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { to: '/connect', label: 'Ecosystem', icon: Globe, color: '#00d4ff', sub: 'Add cloud nodes' },
          { to: '/graph', label: 'Graph Map', icon: Activity, color: '#a855f7', sub: 'Service dependencies' },
          { to: '/propagation', label: 'Failure Sim', icon: Zap, color: '#f59e0b', sub: 'Cascade stress test' },
          { to: '/healing', label: 'Auto-Remedy', icon: HeartPulse, color: '#34d399', sub: 'AI fix engine' },
        ].map((a) => (
          <Link key={a.to} to={a.to}
            className="glass-premium rounded-2xl p-5 flex items-center gap-4 hover:bg-white/[0.05] transition-all group overflow-hidden relative">
            <div className="absolute top-0 right-0 w-16 h-16 bg-white/[0.01] blur-xl -mr-8 -mt-8 group-hover:bg-white/[0.04] transition-colors" />
            <div className="w-10 h-10 rounded-xl flex items-center justify-center border border-white/10 shadow-inner group-hover:scale-110 transition-transform duration-300"
              style={{ background: `${a.color}08` }}>
              <a.icon className="w-5 h-5" style={{ color: a.color }} />
            </div>
            <div className="relative z-10">
              <div className="text-xs font-black text-white uppercase tracking-tight">{a.label}</div>
              <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mt-0.5">{a.sub}</div>
            </div>
          </Link>
        ))}
      </div>
    </motion.div>
  )
}

function MetricRow({ label, value, color }) {
  return (
    <div className="flex justify-between items-center group">
      <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest">{label}</span>
      <span className={clsx('text-xs font-black font-mono transition-transform duration-300 group-hover:translate-x-[-2px]', color)}>{value}</span>
    </div>
  )
}
