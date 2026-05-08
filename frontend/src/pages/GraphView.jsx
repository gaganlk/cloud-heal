import { useEffect, useState, useCallback, useRef } from 'react'
import {
  ReactFlow, Background, Controls, useNodesState, useEdgesState,
  MarkerType, Handle, Position, Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  RefreshCw, GitBranch, AlertTriangle, Globe, Activity,
  Settings2, MousePointer2, Maximize2, Shield, Zap, Database, Server,
} from 'lucide-react'
import { getCombinedGraph, getGraph } from '../api/graph'
import { listCredentials } from '../api/credentials'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'

// ── Type registry ─────────────────────────────────────────────────────────────
const TYPE_META = {
  ec2_instance:     { color: '#f59e0b', icon: '🖥️', label: 'EC2' },
  compute_instance: { color: '#0ea5e9', icon: '🖥️', label: 'Compute' },
  virtual_machine:  { color: '#0ea5e9', icon: '🖥️', label: 'VM' },
  azure_vm:         { color: '#00a4ef', icon: '🖥️', label: 'Azure VM' },
  rds_instance:     { color: '#a855f7', icon: '🗄️', label: 'RDS' },
  cloud_sql:        { color: '#a855f7', icon: '🗄️', label: 'SQL' },
  azure_sql:        { color: '#00a4ef', icon: '🗄️', label: 'Azure SQL' },
  azure_cosmos_db:  { color: '#00a4ef', icon: '⚛️', label: 'Cosmos' },
  load_balancer:    { color: '#f59e0b', icon: '⚖️', label: 'LB' },
  s3_bucket:        { color: '#f59e0b', icon: '🪣', label: 'S3' },
  gcs_bucket:       { color: '#0ea5e9', icon: '🪣', label: 'GCS' },
  azure_storage:    { color: '#00a4ef', icon: '🪣', label: 'Blob' },
  gke_cluster:      { color: '#06b6d4', icon: '☸️', label: 'GKE' },
  aks_cluster:      { color: '#06b6d4', icon: '☸️', label: 'AKS' },
  eks_cluster:      { color: '#f59e0b', icon: '☸️', label: 'EKS' },
  lambda_function:  { color: '#f59e0b', icon: 'λ', label: 'Lambda' },
  azure_function:   { color: '#00a4ef', icon: '⚡', label: 'Az Fn' },
  cloud_function:   { color: '#f97316', icon: '⚡', label: 'GCP Fn' },
  cloud_run:        { color: '#0ea5e9', icon: '🏃', label: 'Run' },
  azure_app_service:{ color: '#00a4ef', icon: '🌐', label: 'AppSvc' },
  sqs_queue:        { color: '#f59e0b', icon: '📥', label: 'SQS' },
  sns_topic:        { color: '#f59e0b', icon: '📢', label: 'SNS' },
  pubsub_topic:     { color: '#0ea5e9', icon: '📢', label: 'PubSub' },
  azure_service_bus:{ color: '#00a4ef', icon: '🚌', label: 'SvcBus' },
  ecs_cluster:      { color: '#f59e0b', icon: '📦', label: 'ECS' },

}

function getRiskColor(score) {
  if (score >= 80) return '#ef4444'
  if (score >= 60) return '#f59e0b'
  if (score >= 40) return '#0ea5e9'
  return '#10b981'
}

function getRiskLabel(score) {
  if (score >= 80) return 'CRITICAL'
  if (score >= 60) return 'WARNING'
  if (score >= 40) return 'ELEVATED'
  return 'NOMINAL'
}

// ── Enhanced Cloud Node ───────────────────────────────────────────────────────
function CloudNode({ data, selected }) {
  const meta = TYPE_META[data.resource_type] || { color: '#64748b', icon: '☁️', label: 'Resource' }
  const riskColor = getRiskColor(data.risk_score || 0)
  const isCritical = (data.risk_score || 0) >= 70
  const isWarning = (data.risk_score || 0) >= 50 && !isCritical
  const cpuHigh = (data.cpu_usage || 0) > 80

  return (
    <motion.div
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
      className={clsx(
        'rounded-2xl min-w-[170px] select-none transition-all duration-300 cursor-pointer relative',
        selected ? 'ring-2 ring-sky-400 shadow-[0_0_40px_rgba(14,165,233,0.4)]' : '',
        isCritical && !selected ? 'ring-1 ring-rose-500/60' : '',
        isWarning && !selected ? 'ring-1 ring-yellow-500/40' : '',
      )}
      style={{
        background: 'rgba(8, 8, 20, 0.95)',
        backdropFilter: 'blur(20px)',
        border: `1px solid ${selected ? meta.color + '60' : 'rgba(255,255,255,0.06)'}`,
        boxShadow: selected
          ? `0 0 30px ${meta.color}25, 0 8px 32px rgba(0,0,0,0.6)`
          : isCritical
          ? '0 0 20px rgba(239,68,68,0.15), 0 4px 16px rgba(0,0,0,0.5)'
          : '0 4px 16px rgba(0,0,0,0.5)',
      }}
    >
      {/* Color accent top bar */}
      <div
        className="absolute top-0 inset-x-0 h-[2px] rounded-t-2xl"
        style={{ background: `linear-gradient(90deg, ${meta.color}80, ${meta.color}20)` }}
      />

      {/* Health pulse ring (critical only) */}
      {isCritical && (
        <motion.div
          className="absolute -inset-1 rounded-2xl pointer-events-none"
          animate={{ opacity: [0.2, 0.5, 0.2] }}
          transition={{ repeat: Infinity, duration: 2 }}
          style={{ border: `1px solid ${riskColor}40`, borderRadius: '1rem' }}
        />
      )}

      <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-white/20 !border-none !rounded-full" />

      <div className="p-4">
        {/* Header row */}
        <div className="flex items-center gap-3 mb-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-base flex-shrink-0"
            style={{ background: `${meta.color}15`, border: `1px solid ${meta.color}30` }}
          >
            {meta.icon}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-black text-white truncate uppercase tracking-tight">
              {data.label}
            </p>
            <p className="text-[9px] font-bold uppercase tracking-widest mt-0.5" style={{ color: meta.color }}>
              {meta.label}
            </p>
          </div>
          {isCritical && (
            <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ repeat: Infinity, duration: 1.5 }}>
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500 flex-shrink-0" />
            </motion.div>
          )}
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 gap-2">
          {/* CPU */}
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[8px] font-black text-slate-600 uppercase">CPU</span>
              <span className="text-[9px] font-black font-mono" style={{ color: cpuHigh ? '#ef4444' : '#94a3b8' }}>
                {(data.cpu_usage || 0).toFixed(0)}%
              </span>
            </div>
            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(data.cpu_usage || 0, 100)}%` }}
                style={{ background: cpuHigh ? '#ef4444' : meta.color }}
              />
            </div>
          </div>

          {/* Risk */}
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[8px] font-black text-slate-600 uppercase">Risk</span>
              <span className="text-[9px] font-black font-mono" style={{ color: riskColor }}>
                {(data.risk_score || 0).toFixed(0)}
              </span>
            </div>
            <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min((data.risk_score || 0), 100)}%` }}
                style={{ background: riskColor }}
              />
            </div>
          </div>
        </div>

        {/* Status badge */}
        <div className="mt-3 flex items-center justify-between">
          <span className={clsx(
            'text-[7px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-md',
            data.status === 'running' || data.status === 'available' || data.status === 'active'
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-rose-500/10 text-rose-400'
          )}>
            {data.status || 'unknown'}
          </span>
          <span className="text-[7px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded-md"
            style={{ background: `${riskColor}15`, color: riskColor }}>
            {getRiskLabel(data.risk_score || 0)}
          </span>
        </div>
      </div>

      <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-white/20 !border-none !rounded-full" />
    </motion.div>
  )
}

const nodeTypes = { cloudNode: CloudNode }

function layoutNodes(nodes) {
  const COLS = 4
  const H_GAP = 260
  const V_GAP = 200
  return nodes.map((n, i) => ({
    ...n,
    position: { x: (i % COLS) * H_GAP + 60, y: Math.floor(i / COLS) * V_GAP + 60 },
  }))
}

// ── Data cards ────────────────────────────────────────────────────────────────
function DataCard({ label, value, color }) {
  const colorMap = {
    emerald: 'text-emerald-400 bg-emerald-400/5 border-emerald-400/20',
    rose:    'text-rose-400 bg-rose-400/5 border-rose-400/20',
    sky:     'text-sky-400 bg-sky-400/5 border-sky-400/20',
    purple:  'text-purple-400 bg-purple-400/5 border-purple-400/20',
    yellow:  'text-yellow-400 bg-yellow-400/5 border-yellow-400/20',
  }
  return (
    <div className={clsx('p-3 rounded-2xl border flex flex-col gap-1', colorMap[color])}>
      <span className="text-[8px] font-black uppercase tracking-widest opacity-60">{label}</span>
      <span className="text-xs font-black tracking-tight uppercase truncate">{value}</span>
    </div>
  )
}

function MetaField({ label, value }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] font-bold text-slate-600 uppercase tracking-tighter">{label}</span>
      <span className="text-[10px] font-black text-slate-300 font-mono truncate max-w-[120px]">{value}</span>
    </div>
  )
}

// ── Main GraphView ────────────────────────────────────────────────────────────
export default function GraphView() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(false)
  const [creds, setCreds] = useState([])
  const [selectedCred, setSelectedCred] = useState('all')
  const [selectedNode, setSelectedNode] = useState(null)

  useEffect(() => {
    listCredentials().then((r) => setCreds(r.data)).catch(() => {})
    loadGraph()
  }, [])

  const loadGraph = useCallback(async (credId = 'all') => {
    setLoading(true)
    try {
      const res = credId === 'all' ? await getCombinedGraph() : await getGraph(credId)
      const data = res.data || { nodes: [], edges: [] }
      const nodesData = data.nodes || []
      const edgesData = data.edges || []

      setNodes(layoutNodes(nodesData.map((n) => ({
        id: n.id,
        type: 'cloudNode',
        data: { ...n, risk_score: n.risk_score ?? (n.cpu_usage > 80 ? 85 : n.cpu_usage > 60 ? 55 : 20) },
        position: { x: 0, y: 0 },
      }))))

      setEdges(edgesData.map((e) => ({
        id: e.id || `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label: e.edge_type,
        labelStyle: { fill: '#475569', fontSize: 9, fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.08em' },
        labelBgPadding: [6, 10],
        labelBgBorderRadius: 6,
        labelBgStyle: { fill: 'rgba(5,5,15,0.9)', stroke: 'rgba(255,255,255,0.05)', strokeWidth: 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: 'rgba(56,189,248,0.5)', width: 14, height: 14 },
        style: {
          stroke: e.edge_type === 'routes_to' ? 'rgba(56,189,248,0.4)' : 'rgba(168,85,247,0.25)',
          strokeWidth: e.edge_type === 'routes_to' ? 2 : 1.5,
        },
        type: 'smoothstep',
        animated: e.edge_type === 'routes_to',
      })))
    } catch {
      toast.error('Run a cloud scan first to populate the topology graph')
      setNodes([])
      setEdges([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleNodeClick = useCallback((_, node) => {
    setSelectedNode(node.data)
  }, [])

  const meta = selectedNode ? (TYPE_META[selectedNode.resource_type] || { color: '#0ea5e9', icon: '☁️' }) : null
  const riskScore = selectedNode?.risk_score || 0
  const riskColor = getRiskColor(riskScore)

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-[calc(100vh-10rem)] flex gap-6"
    >
      {/* ── Graph Canvas ── */}
      <div className="flex-1 glass-premium rounded-[2.5rem] overflow-hidden relative shadow-2xl border border-white/5">
        {/* Top overlay controls */}
        <div className="absolute top-6 left-6 right-6 z-10 flex flex-wrap items-center gap-3">
          {/* Stats chip */}
          <div className="glass-dark rounded-2xl px-4 py-2.5 flex items-center gap-4 border border-white/5 shadow-2xl">
            <GitBranch className="w-4 h-4 text-sky-400" />
            <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Topology</span>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-black text-white">{nodes.length}</span>
                <span className="text-[9px] font-bold text-slate-600 uppercase">Nodes</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-black text-white">{edges.length}</span>
                <span className="text-[9px] font-bold text-slate-600 uppercase">Edges</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-black text-rose-400">
                  {nodes.filter((n) => (n.data.risk_score || 0) >= 70).length}
                </span>
                <span className="text-[9px] font-bold text-slate-600 uppercase">Critical</span>
              </div>
            </div>
          </div>

          {/* Provider filter */}
          <div className="flex items-center gap-2">
            <select
              id="graph-cred-select"
              value={selectedCred}
              onChange={(e) => {
                setSelectedCred(e.target.value)
                loadGraph(e.target.value === 'all' ? 'all' : parseInt(e.target.value))
              }}
              className="input-premium !py-2 !px-4 text-xs font-bold min-w-[200px] !bg-white/[0.03] backdrop-blur-xl !rounded-xl"
            >
              <option value="all">🌐 All Infrastructure</option>
              {creds.map((c) => (
                <option key={c.id} value={c.id}>{c.provider.toUpperCase()} — {c.name}</option>
              ))}
            </select>

            <button
              id="refresh-graph"
              onClick={() => loadGraph(selectedCred === 'all' ? 'all' : parseInt(selectedCred))}
              className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/[0.03] border border-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
            >
              <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* Hint */}
        <div className="absolute bottom-6 left-6 z-10 glass-dark px-4 py-2 rounded-xl border border-white/5 flex items-center gap-2 text-[9px] font-black text-slate-500 uppercase tracking-widest">
          <MousePointer2 className="w-3 h-3 text-sky-400" />
          Click any node to inspect telemetry
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-full bg-[#0d0d18]/60 backdrop-blur-sm">
            <div className="text-center">
              <div className="w-14 h-14 border-4 border-sky-500/20 border-t-sky-500 rounded-full animate-spin mx-auto mb-5" />
              <p className="text-[11px] font-black uppercase tracking-[0.3em] text-slate-500">Mapping Topology...</p>
            </div>
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-8">
            <div className="w-24 h-24 rounded-3xl bg-white/[0.02] border border-white/5 flex items-center justify-center mb-6">
              <GitBranch className="w-10 h-10 text-slate-800" />
            </div>
            <h3 className="text-xl font-black text-white mb-3">No Topology Data</h3>
            <p className="text-sm text-slate-500 max-w-xs leading-relaxed">
              Connect a cloud provider and run a scan to discover your infrastructure topology.
            </p>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.15}
            maxZoom={2}
            className="bg-[#03030a]"
          >
            <Background color="rgba(255,255,255,0.015)" gap={48} size={1.5} />
            <Controls className="!bg-[#0d0d18] !border-white/5 !rounded-2xl overflow-hidden shadow-2xl" showInteractive={false} />
            {/* Node count panel */}
            <Panel position="bottom-right">
              <div className="glass-dark rounded-xl px-3 py-2 border border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest mr-6 mb-2">
                {nodes.filter((n) => (n.data.risk_score || 0) < 40).length} nominal ·{' '}
                {nodes.filter((n) => (n.data.risk_score || 0) >= 40 && (n.data.risk_score || 0) < 70).length} elevated ·{' '}
                {nodes.filter((n) => (n.data.risk_score || 0) >= 70).length} critical
              </div>
            </Panel>
          </ReactFlow>
        )}
      </div>

      {/* ── Inspector Panel ── */}
      <div className="w-80 flex-shrink-0 flex flex-col gap-4">
        {/* Node Inspector */}
        <div className="glass-premium rounded-[2.5rem] p-6 flex-1 border border-white/5 overflow-y-auto relative">
          <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/4 blur-3xl -mr-16 -mt-16 pointer-events-none" />

          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-6 flex items-center gap-2">
            <Settings2 className="w-4 h-4" /> Asset Inspector
          </h3>

          <AnimatePresence mode="wait">
            {selectedNode ? (
              <motion.div
                key={selectedNode.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-6"
              >
                {/* Node header */}
                <div className="flex items-center gap-3">
                  <div
                    className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl border"
                    style={{ background: `${meta.color}10`, borderColor: `${meta.color}30` }}
                  >
                    {meta.icon}
                  </div>
                  <div className="min-w-0">
                    <h4 className="text-base font-black text-white tracking-tight truncate">{selectedNode.label}</h4>
                    <div
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest mt-1 border"
                      style={{ background: `${meta.color}10`, color: meta.color, borderColor: `${meta.color}25` }}
                    >
                      <Globe className="w-2.5 h-2.5" />
                      {selectedNode.provider?.toUpperCase() || 'UNKNOWN'}
                    </div>
                  </div>
                </div>

                {/* Metric cards */}
                <div className="grid grid-cols-2 gap-2">
                  <DataCard label="Status" value={selectedNode.status || 'active'} color="emerald" />
                  <DataCard label="Risk" value={`${riskScore.toFixed(0)} ${getRiskLabel(riskScore)}`} color="rose" />
                  <DataCard label="CPU" value={`${selectedNode.cpu_usage?.toFixed(1) || '0'}%`} color="sky" />
                  <DataCard label="Memory" value={`${selectedNode.memory_usage?.toFixed(1) || '0'}%`} color="purple" />
                </div>

                {/* Risk bar */}
                <div className="space-y-2">
                  <div className="flex justify-between text-[9px] font-black uppercase tracking-widest">
                    <span className="text-slate-600">Risk Score</span>
                    <span style={{ color: riskColor }}>{riskScore.toFixed(0)}/100</span>
                  </div>
                  <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${riskScore}%` }}
                      style={{ background: `linear-gradient(90deg, ${riskColor}80, ${riskColor})` }}
                    />
                  </div>
                </div>

                {/* Metadata */}
                <div className="space-y-3">
                  <h5 className="text-[9px] font-black text-slate-600 uppercase tracking-widest border-b border-white/5 pb-2">
                    Technical Metadata
                  </h5>
                  <MetaField label="Type" value={selectedNode.resource_type} />
                  <MetaField label="Region" value={selectedNode.region || 'us-east-1'} />
                  <MetaField label="ID" value={selectedNode.id?.substring(0, 18) + (selectedNode.id?.length > 18 ? '…' : '')} />
                </div>

                {/* Action buttons */}
                <div className="space-y-2">
                  <Link
                    to={`/prediction?node=${selectedNode.id}`}
                    className="btn-primary-glow w-full !py-2.5 !text-[9px] uppercase font-black tracking-widest"
                  >
                    Analyze Risk Matrix
                  </Link>
                  <Link
                    to={`/rca?resource=${selectedNode.id}`}
                    className="btn-secondary-glass w-full !py-2.5 !text-[9px] uppercase font-black tracking-widest"
                  >
                    Root Cause Analysis
                  </Link>
                </div>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-20 text-center"
              >
                <div className="w-16 h-16 rounded-3xl bg-white/[0.02] border border-white/5 flex items-center justify-center mb-4">
                  <Activity className="w-8 h-8 text-slate-800 animate-pulse" />
                </div>
                <p className="text-xs font-black uppercase tracking-widest text-slate-600">Select a Node</p>
                <p className="text-[10px] text-slate-700 font-medium mt-1.5">Click any node to inspect its telemetry and risk profile</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Legend */}
        <div className="glass-premium rounded-3xl p-5 border border-white/5">
          <h4 className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-3">Risk Legend</h4>
          <div className="grid grid-cols-2 gap-2">
            {[
              { color: '#10b981', label: 'Nominal (0-39)' },
              { color: '#0ea5e9', label: 'Elevated (40-59)' },
              { color: '#f59e0b', label: 'Warning (60-79)' },
              { color: '#ef4444', label: 'Critical (80+)' },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: l.color }} />
                <span className="text-[9px] font-bold text-slate-500">{l.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  )
}
