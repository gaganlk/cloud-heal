import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Cloud, Plus, Trash2, RefreshCw, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, AlertTriangle, Loader2, Shield,
  Scan, Server, Key, Globe, Layout,
} from 'lucide-react'
import { addCredential, listCredentials, deleteCredential, validateCredential } from '../api/credentials'
import { triggerScan, getScanStatus } from '../api/scanner'
import { useCloudStore } from '../store/cloudStore'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'

const PROVIDERS = [
  {
    id: 'aws',
    name: 'Amazon Web Services',
    icon: '🟡',
    color: '#f59e0b',
    fields: [
      { 
        key: 'access_key_id', 
        label: 'Access Key ID', 
        placeholder: 'AKIA...', 
        pattern: /^(AKIA|ASIA)[0-9A-Z]{16}$/,
        hint: 'Must start with AKIA or ASIA followed by 16 uppercase alphanumeric chars'
      },
      { 
        key: 'secret_access_key', 
        label: 'Secret Access Key', 
        placeholder: '••••••••', 
        type: 'password',
        pattern: /^[A-Za-z0-9/+=]{40}$/,
        hint: 'Exactly 40 base64-style characters'
      },
      { key: 'region', label: 'Region', placeholder: 'us-east-1', defaultValue: 'us-east-1' },
    ],
  },
  {
    id: 'gcp',
    name: 'Google Cloud Platform',
    icon: '🔵',
    color: '#4285f4',
    fields: [
      { 
        key: 'project_id', 
        label: 'Project ID', 
        placeholder: 'my-gcp-project',
        pattern: /^[a-z][a-z0-9-]{4,28}[a-z0-9]$/,
        hint: '6-30 chars, lowercase, letters first'
      },
      { 
        key: 'service_account_json', 
        label: 'Service Account JSON', 
        placeholder: '{"type":"service_account",...}', 
        type: 'textarea',
        validate: (val) => {
          try {
            const parsed = JSON.parse(val)
            return parsed.type === 'service_account' && !!parsed.private_key
          } catch { return false }
        },
        hint: 'Must be a valid GCP Service Account JSON'
      },
    ],
  },
  {
    id: 'azure',
    name: 'Microsoft Azure',
    icon: '🔷',
    color: '#00a4ef',
    fields: [
      { 
        key: 'subscription_id', 
        label: 'Subscription ID', 
        placeholder: 'xxxxxxxx-xxxx-xxxx-...',
        pattern: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/,
        hint: 'Valid UUID/GUID format'
      },
      { 
        key: 'client_id', 
        label: 'Client (App) ID', 
        placeholder: 'xxxxxxxx-xxxx-...',
        pattern: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/,
        hint: 'Valid UUID/GUID format'
      },
      { 
        key: 'client_secret', 
        label: 'Client Secret', 
        placeholder: '••••••••', 
        type: 'password',
        minLength: 10,
        hint: 'Minimum 10 characters'
      },
      { 
        key: 'tenant_id', 
        label: 'Tenant ID', 
        placeholder: 'xxxxxxxx-xxxx-...',
        pattern: /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/,
        hint: 'Valid UUID/GUID format'
      },
    ],
  },
]

function ProviderCard({ provider, selected, onClick }) {
  return (
    <button
      id={`provider-${provider.id}`}
      onClick={onClick}
      className={clsx(
        'w-full flex items-center gap-3 p-4 rounded-2xl border transition-all duration-300 text-left group relative overflow-hidden',
        selected
          ? 'border-sky-500/50 bg-sky-500/10 text-white shadow-[0_0_20px_rgba(14,165,233,0.15)]'
          : 'border-white/5 bg-white/[0.02] text-slate-400 hover:border-white/20 hover:bg-white/[0.04] hover:text-white',
      )}
    >
      {selected && <div className="absolute top-0 right-0 w-24 h-24 bg-sky-500/5 blur-2xl -mr-12 -mt-12" />}
      <span className="text-2xl group-hover:scale-110 transition-transform duration-300">{provider.icon}</span>
      <div className="relative z-10">
        <div className="text-sm font-bold tracking-tight">{provider.name}</div>
        <div className="text-[10px] text-slate-500 font-mono mt-0.5 uppercase tracking-wider">{provider.id}</div>
      </div>
      {selected && (
        <motion.div 
          layoutId="provider-check"
          className="ml-auto w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center"
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-white" />
        </motion.div>
      )}
    </button>
  )
}

function CredentialCard({ cred, onScan, onDelete, scanStatus }) {
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState(null)
  const scanning = scanStatus?.status === 'scanning'
  const PROVIDER_COLORS = { aws: '#f59e0b', gcp: '#4285f4', azure: '#00a4ef' }

  const handleValidate = async () => {
    setValidating(true)
    try {
      const res = await validateCredential(cred.id)
      setValidation(res.data)
      if (res.data.valid) toast.success(res.data.message)
      else toast.error(res.data.message)
    } catch {
      toast.error('Validation failed')
    } finally {
      setValidating(false)
    }
  }

  return (
    <motion.div 
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="glass-premium rounded-2xl p-6 hover-glow"
    >
      <div className="flex items-start justify-between mb-5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl border border-white/5"
            style={{ background: `${PROVIDER_COLORS[cred.provider] || '#00d4ff'}10` }}>
            {{ aws: '🟡', gcp: '🔵', azure: '🔷' }[cred.provider] || '☁️'}
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">{cred.name}</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{cred.provider}</span>
              <span className="w-1 h-1 rounded-full bg-slate-700" />
              <p className="text-[10px] text-slate-500 font-medium">{
                cred.last_scan
                  ? `Last verified: ${new Date(cred.last_scan).toLocaleTimeString()}`
                  : 'Pending first scan'
              }</p>
            </div>
          </div>
        </div>
        <div className={clsx(
          'px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border',
          cred.scan_status === 'completed' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
          cred.scan_status === 'scanning' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20 animate-pulse' :
          cred.scan_status === 'failed' ? 'bg-red-500/10 text-red-500 border-red-500/20' : 
          'bg-slate-500/10 text-slate-500 border-white/5',
        )}>
          {cred.scan_status || 'idle'}
        </div>
      </div>

      <AnimatePresence>
        {validation && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className={clsx(
              'flex items-center gap-3 p-3 rounded-xl mb-5 text-xs font-medium border overflow-hidden',
              validation.valid ? 'bg-emerald-400/5 text-emerald-400 border-emerald-400/20' : 'bg-red-400/5 text-red-400 border-red-400/20',
            )}
          >
            {validation.valid ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
            {validation.message}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center gap-3">
        <button
          onClick={() => onScan(cred.id)}
          disabled={scanning}
          className="btn-primary-glow !py-2 !px-4 text-xs h-9 flex-1"
        >
          {scanning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Scan className="w-3.5 h-3.5" />}
          {scanning ? 'Analyzing Infrastructure...' : 'Discover Resources'}
        </button>
        <button
          onClick={handleValidate}
          disabled={validating}
          className="btn-secondary-glass !py-2 !px-4 text-xs h-9"
        >
          {validating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Shield className="w-3.5 h-3.5" />}
          Re-verify
        </button>
        <button
          onClick={() => onDelete(cred.id)}
          className="w-9 h-9 rounded-xl flex items-center justify-center text-red-400 hover:bg-red-500/10 border border-white/5 hover:border-red-500/30 transition-all"
          title="Delete Credential"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {scanStatus && scanStatus.status !== 'never' && (
        <div className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between">
           <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase font-black tracking-widest">
            <Server className="w-3 h-3 text-sky-500" />
            Infrastructure Inventory
           </div>
           <span className="text-xs font-mono text-sky-400 bg-sky-400/10 px-2 py-0.5 rounded-md">
             {scanStatus.resource_count || 0} active resources
           </span>
        </div>
      )}

    </motion.div>
  )
}

export default function CloudConnect() {
  const [creds, setCreds] = useState([])
  const [scanStatuses, setScanStatuses] = useState({})
  const [selectedProvider, setSelectedProvider] = useState('aws')
  const [form, setForm] = useState({ name: '', credentials: {} })
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadCreds = useCallback(async () => {
    try {
      const res = await listCredentials()
      setCreds(res.data)
      const statuses = {}
      await Promise.all(res.data.map(async (c) => {
        try {
          const s = await getScanStatus(c.id)
          statuses[c.id] = s.data
        } catch {}
      }))
      setScanStatuses(statuses)
    } catch {
      toast.error('Session expired. Please re-login.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadCreds() }, [loadCreds])

  const validateField = (field, val) => {
    if (!val) return false
    if (field.pattern) return field.pattern.test(val)
    if (field.validate) return field.validate(val)
    if (field.minLength) return val.length >= field.minLength
    return true
  }

  const isFormValid = useMemo(() => {
    if (!form.name || form.name.length < 3) return false
    const provider = PROVIDERS.find((p) => p.id === selectedProvider)
    return provider.fields.every(f => {
      const val = form.credentials[f.key] || f.defaultValue
      return validateField(f, val)
    })
  }, [form, selectedProvider])

  const handleScan = async (credId) => {
    try {
      await triggerScan(credId)
      toast.success('Inventory discovery started...')
      setScanStatuses((prev) => ({ ...prev, [credId]: { status: 'scanning', resource_count: 0 } }))
      let polls = 0
      const poll = setInterval(async () => {
        polls++
        try {
          const s = await getScanStatus(credId)
          setScanStatuses((prev) => ({ ...prev, [credId]: s.data }))
          if (s.data.status === 'completed' || s.data.status === 'failed' || polls > 30) {
            clearInterval(poll)
            if (s.data.status === 'completed') toast.success(`Discovery complete: ${s.data.resource_count} resources found`)
            loadCreds()
          }
        } catch { clearInterval(poll) }
      }, 2000)
    } catch {
      toast.error('Discovery engine failed to start')
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteCredential(id)
      setCreds((prev) => prev.filter((c) => c.id !== id))
      toast.success('Connection terminated')
    } catch {
      toast.error('Failed to terminate connection')
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!isFormValid) {
      toast.error('Please provide valid real-world credentials as required')
      return
    }
    setSubmitting(true)
    try {
      const provider = PROVIDERS.find((p) => p.id === selectedProvider)
      const submitData = {}
      provider.fields.forEach((f) => {
        submitData[f.key] = form.credentials[f.key] || f.defaultValue || ''
      })
      const res = await addCredential({ provider: selectedProvider, name: form.name, credentials: submitData })
      setCreds((prev) => [...prev, res.data])
      setForm({ name: '', credentials: {} })
      setShowForm(false)
      toast.success(`Connected to ${selectedProvider.toUpperCase()} securely`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Handshake failed')
    } finally {
      setSubmitting(false)
    }
  }

  const currentProvider = PROVIDERS.find((p) => p.id === selectedProvider)

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
            <Cloud className="w-8 h-8 text-sky-500" />
            Cloud Environment
          </h1>
          <p className="text-slate-500 text-sm mt-2 max-w-sm font-medium leading-relaxed">
            Attach multi-cloud providers to enable real-time autonomous healing and risk discovery.
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="btn-primary-glow flex items-center gap-2 px-8"
          >
            <Plus className="w-5 h-5" />
            Connect Provider
          </button>
        )}
      </div>

      {/* Security alert */}
      <div className="glass-premium rounded-2xl p-4 flex items-center gap-4 border-emerald-500/20 bg-emerald-500/[0.02]">
        <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
          <Shield className="w-5 h-5 text-emerald-400" />
        </div>
        <div className="text-xs text-slate-400 leading-relaxed">
          <strong className="text-emerald-400 uppercase tracking-widest text-[10px] block mb-0.5">Zero-Trust Security</strong>
          Credentials are AES-256 encrypted at rest and never transmitted in logs. 
          Scanning is read-only and uses minimal-privilege patterns.
        </div>
      </div>

      {/* Form section */}
      <AnimatePresence>
        {showForm && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass-premium rounded-[2.5rem] p-8 space-y-8 overflow-hidden relative"
          >
            <div className="absolute bottom-0 right-0 w-64 h-64 bg-sky-500/5 blur-[100px] -mr-32 -mb-32" />
            
            <div>
              <h2 className="text-lg font-black text-white flex items-center gap-3 mb-6">
                <Globe className="w-5 h-5 text-sky-400" />
                Select Cloud Ecosystem
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {PROVIDERS.map((p) => (
                  <ProviderCard
                    key={p.id}
                    provider={p}
                    selected={selectedProvider === p.id}
                    onClick={() => {
                        setSelectedProvider(p.id)
                        setForm({ ...form, credentials: {} })
                    }}
                  />
                ))}
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Environment Name</label>
                  <input
                    type="text"
                    placeholder="e.g. Production Cluster"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="input-premium"
                    required
                  />
                  {form.name && form.name.length < 3 && <p className="text-[10px] text-red-400">Name must be at least 3 characters</p>}
                </div>

                {currentProvider?.fields.map((field) => (
                  <div key={field.key} className="space-y-2">
                    <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] flex items-center justify-between">
                      {field.label}
                      {form.credentials[field.key] && (
                         validateField(field, form.credentials[field.key]) 
                          ? <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                          : <XCircle className="w-3 h-3 text-red-500" />
                      )}
                    </label>
                    {field.type === 'textarea' ? (
                      <textarea
                        placeholder={field.placeholder}
                        value={form.credentials[field.key] || ''}
                        onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, [field.key]: e.target.value } })}
                        className="input-premium min-h-[120px] font-mono text-xs resize-y"
                      />
                    ) : (
                      <input
                        type={field.type || 'text'}
                        placeholder={field.placeholder}
                        value={form.credentials[field.key] || field.defaultValue || ''}
                        onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, [field.key]: e.target.value } })}
                        className="input-premium"
                      />
                    )}
                    {field.hint && (
                      <p className={clsx(
                        'text-[10px] font-medium transition-colors',
                        form.credentials[field.key] && !validateField(field, form.credentials[field.key]) ? 'text-red-400' : 'text-slate-600'
                      )}>
                        {field.hint}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-white/5">
                <button 
                   type="submit" 
                   disabled={submitting || !isFormValid} 
                   className="btn-primary-glow px-10 disabled:grayscale disabled:opacity-30 disabled:hover:shadow-none"
                >
                  {submitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Shield className="w-5 h-5" />}
                  {submitting ? 'Verifying Handshake...' : `Connect ${currentProvider?.name}`}
                </button>
                <button 
                  type="button" 
                  onClick={() => setShowForm(false)} 
                  className="btn-secondary-glass px-8"
                >
                  Discard
                </button>
                
                <div className="hidden lg:flex ml-auto items-center gap-2 text-[10px] text-slate-600 font-bold uppercase tracking-widest">
                  <Layout className="w-3 h-3" />
                  All fields strictly validated for production
                </div>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* List section */}
      <div className="space-y-6">
        <div className="flex items-center gap-4 px-4">
          <h2 className="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em]">
            Active Cloud Connections
          </h2>
          <div className="h-px flex-1 bg-white/5" />
          <span className="text-[10px] font-bold text-sky-400 bg-sky-400/10 px-3 py-1 rounded-full border border-sky-400/20">
            {creds.length} CONNECTED
          </span>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             {[1,2].map(i => <div key={i} className="h-48 glass-premium rounded-2xl animate-pulse bg-white/5" />)}
          </div>
        ) : creds.length === 0 ? (
          <div className="glass-premium rounded-[2.5rem] p-20 text-center flex flex-col items-center">
            <div className="w-20 h-20 rounded-3xl bg-white/[0.02] border border-white/5 flex items-center justify-center mb-6">
              <Cloud className="w-10 h-10 text-slate-700" />
            </div>
            <h3 className="text-xl font-bold text-white mb-2 tracking-tight">Zero Clouds Attached</h3>
            <p className="text-sm text-slate-500 max-w-xs mx-auto mb-8 font-medium">
              You haven't connected any cloud providers yet. Connect one to enable auto-healing.
            </p>
            <button onClick={() => setShowForm(true)} className="btn-primary-glow px-10">
              Start Your First Connection
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <AnimatePresence mode="popLayout">
              {creds.map((cred) => (
                <CredentialCard
                  key={cred.id}
                  cred={cred}
                  onScan={handleScan}
                  onDelete={handleDelete}
                  scanStatus={scanStatuses[cred.id]}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </motion.div>
  )
}
