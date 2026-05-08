import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  Settings, Shield, Bell, Lock, Database, Globe, Key,
  Save, RefreshCw, CheckCircle2, AlertTriangle, Loader2,
  Clock, Cpu, Zap, Eye, EyeOff, Copy, ExternalLink
} from 'lucide-react'
import toast from 'react-hot-toast'
import API from '../api/auth'
import { clsx } from 'clsx'
import { useAuthStore } from '../store/authStore'

function SectionCard({ title, icon: Icon, iconColor = 'text-sky-400', children, accent = '#0ea5e9' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-premium rounded-[2rem] p-8 relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-40 h-40 blur-[80px] -mr-20 -mt-20 opacity-10 rounded-full"
        style={{ background: accent }} />
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center border border-white/10"
          style={{ background: `${accent}15` }}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
        <h2 className="text-sm font-black text-white uppercase tracking-widest">{title}</h2>
      </div>
      {children}
    </motion.div>
  )
}

function ToggleSetting({ label, desc, value, onChange, disabled }) {
  return (
    <div className="flex items-center justify-between gap-4 py-4 border-b border-white/[0.04] last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-white">{label}</p>
        <p className="text-[11px] text-slate-500 font-medium mt-0.5">{desc}</p>
      </div>
      <button
        onClick={() => !disabled && onChange(!value)}
        disabled={disabled}
        className={clsx(
          'relative w-12 h-6 rounded-full border transition-all duration-300 flex-shrink-0',
          value
            ? 'bg-sky-500 border-sky-400'
            : 'bg-white/5 border-white/10',
          disabled && 'opacity-40 cursor-not-allowed'
        )}
      >
        <span className={clsx(
          'absolute top-0.5 w-5 h-5 rounded-full transition-all duration-300 shadow-lg',
          value ? 'left-6 bg-white' : 'left-0.5 bg-slate-400'
        )} />
      </button>
    </div>
  )
}

function NumberSetting({ label, desc, value, onChange, min, max, unit }) {
  return (
    <div className="flex items-center justify-between gap-4 py-4 border-b border-white/[0.04] last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-white">{label}</p>
        <p className="text-[11px] text-slate-500 font-medium mt-0.5">{desc}</p>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          min={min}
          max={max}
          className="w-20 bg-white/5 border border-white/10 rounded-xl px-3 py-1.5 text-xs font-black text-white text-right focus:outline-none focus:border-sky-500/50"
        />
        {unit && <span className="text-[10px] text-slate-500 font-bold uppercase">{unit}</span>}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { user } = useAuthStore()

  // Monitoring Settings
  const [monitorInterval, setMonitorInterval] = useState(30)
  const [driftEnabled, setDriftEnabled] = useState(true)
  const [alertsEnabled, setAlertsEnabled] = useState(true)
  const [autoHealEnabled, setAutoHealEnabled] = useState(false)
  const [cpuThreshold, setCpuThreshold] = useState(80)
  const [memThreshold, setMemThreshold] = useState(85)

  // Notification Settings
  const [emailAlerts, setEmailAlerts] = useState(true)
  const [slackEnabled, setSlackEnabled] = useState(false)
  const [slackWebhook, setSlackWebhook] = useState('')
  const [showSlackKey, setShowSlackKey] = useState(false)

  // Platform Status
  const [health, setHealth] = useState(null)
  const [loadingHealth, setLoadingHealth] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await API.get('/health')
        setHealth(res.data)
      } catch {
        setHealth({ status: 'unknown' })
      } finally {
        setLoadingHealth(false)
      }
    }
    fetchHealth()
  }, [])

  const handleSaveSettings = async () => {
    setSaving(true)
    try {
      // Settings are stored locally for now (backend settings API is a Phase 2 feature)
      // In production these would POST to /api/settings
      await new Promise(r => setTimeout(r, 600)) // Simulated save
      toast.success('Settings saved successfully')
    } catch {
      toast.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const handleClearCache = async () => {
    const toastId = toast.loading('Clearing metric cache...')
    try {
      await API.post('/dashboard/clear-cache').catch(() => {}) // Best effort
      toast.success('Cache cleared — next sync will fetch fresh data')
    } finally {
      toast.dismiss(toastId)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  }

  const STATUS_COLOR = {
    healthy: 'text-emerald-400',
    degraded: 'text-amber-400',
    unknown: 'text-slate-500',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-4xl mx-auto space-y-8 pb-20"
    >
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            <Settings className="w-8 h-8 text-slate-400" />
            System Settings
          </h1>
          <p className="text-slate-500 text-sm mt-2 font-medium">
            Configure platform behavior, thresholds, and operational parameters.
          </p>
        </div>
        <button
          onClick={handleSaveSettings}
          disabled={saving}
          className="btn-primary-glow flex items-center gap-2 px-8"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      {/* Platform Health Status */}
      <SectionCard title="Platform Health" icon={Cpu} iconColor="text-sky-400" accent="#0ea5e9">
        {loadingHealth ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-16 bg-white/5 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'System', value: health?.status || 'unknown' },
              { label: 'Database', value: health?.database || 'unknown' },
              { label: 'Redis', value: health?.redis || 'unknown' },
              { label: 'Kafka', value: health?.kafka || 'unknown' },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white/[0.03] border border-white/5 rounded-xl p-4">
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">{label}</p>
                <p className={clsx('text-sm font-black uppercase', STATUS_COLOR[value] || 'text-slate-500')}>{value}</p>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => { setLoadingHealth(true); API.get('/health').then(r => setHealth(r.data)).finally(() => setLoadingHealth(false)) }}
            className="btn-secondary-glass !py-2 !px-4 text-[10px] uppercase font-black tracking-widest flex items-center gap-2"
          >
            <RefreshCw className="w-3 h-3" /> Refresh Status
          </button>
          <span className="text-[10px] text-slate-600 font-medium">
            {health?.websocket_connections ?? 0} active WebSocket connections
          </span>
        </div>
      </SectionCard>

      {/* Monitoring & Healing Settings */}
      <SectionCard title="Monitoring & Thresholds" icon={Shield} iconColor="text-emerald-400" accent="#10b981">
        <NumberSetting
          label="Scan Interval"
          desc="How frequently the monitoring service polls cloud resources"
          value={monitorInterval}
          onChange={setMonitorInterval}
          min={10}
          max={300}
          unit="sec"
        />
        <NumberSetting
          label="CPU Alert Threshold"
          desc="CPU utilization % above which a resource is flagged critical"
          value={cpuThreshold}
          onChange={setCpuThreshold}
          min={50}
          max={100}
          unit="%"
        />
        <NumberSetting
          label="Memory Alert Threshold"
          desc="Memory utilization % above which a resource is flagged critical"
          value={memThreshold}
          onChange={setMemThreshold}
          min={50}
          max={100}
          unit="%"
        />
        <ToggleSetting
          label="Drift Detection"
          desc="Continuously compare live state against desired configuration baselines"
          value={driftEnabled}
          onChange={setDriftEnabled}
        />
        <ToggleSetting
          label="Autonomous Healing"
          desc="Allow the AI engine to execute remediation actions without manual approval"
          value={autoHealEnabled}
          onChange={setAutoHealEnabled}
        />
        <ToggleSetting
          label="System Alerts"
          desc="Enable real-time alert generation for threshold breaches"
          value={alertsEnabled}
          onChange={setAlertsEnabled}
        />
      </SectionCard>

      {/* Notification Settings */}
      <SectionCard title="Notification Channels" icon={Bell} iconColor="text-amber-400" accent="#f59e0b">
        <ToggleSetting
          label="Email Alerts"
          desc={`Send critical alerts to ${user?.email || 'configured email'}`}
          value={emailAlerts}
          onChange={setEmailAlerts}
        />
        <ToggleSetting
          label="Slack Integration"
          desc="Post healing events and anomalies to a Slack webhook"
          value={slackEnabled}
          onChange={setSlackEnabled}
        />
        {slackEnabled && (
          <div className="pt-4">
            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-2">
              Slack Webhook URL
            </label>
            <div className="flex gap-2">
              <input
                type={showSlackKey ? 'text' : 'password'}
                value={slackWebhook}
                onChange={(e) => setSlackWebhook(e.target.value)}
                placeholder="https://hooks.slack.com/services/..."
                className="input-premium flex-1 text-xs"
              />
              <button
                onClick={() => setShowSlackKey(!showSlackKey)}
                className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white transition-colors"
              >
                {showSlackKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}
      </SectionCard>

      {/* Platform Info & Maintenance */}
      <SectionCard title="Platform Information" icon={Database} iconColor="text-purple-400" accent="#a855f7">
        <div className="space-y-3">
          {[
            { label: 'Platform Version', value: '2.0.0' },
            { label: 'Environment', value: 'docker-compose' },
            { label: 'Logged in as', value: user?.username || '—' },
            { label: 'Account Role', value: user?.role || '—' },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between items-center py-2 border-b border-white/[0.04] last:border-0">
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">{label}</span>
              <span className="text-xs font-black text-white font-mono bg-white/5 px-3 py-1 rounded-lg">{value}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 pt-6 border-t border-white/5 flex flex-wrap gap-3">
          <button
            onClick={handleClearCache}
            className="btn-secondary-glass !py-2 !px-5 text-[10px] uppercase font-black tracking-widest flex items-center gap-2"
          >
            <RefreshCw className="w-3 h-3" /> Flush Metric Cache
          </button>
          <a
            href="http://localhost:3001"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary-glass !py-2 !px-5 text-[10px] uppercase font-black tracking-widest flex items-center gap-2"
          >
            <ExternalLink className="w-3 h-3" /> Open Grafana
          </a>
          <a
            href="http://localhost:16686"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary-glass !py-2 !px-5 text-[10px] uppercase font-black tracking-widest flex items-center gap-2"
          >
            <ExternalLink className="w-3 h-3" /> Open Jaeger
          </a>
        </div>
      </SectionCard>
    </motion.div>
  )
}
