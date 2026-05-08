/**
 * Production-grade Toast Notification System
 * Provides imperative toast API usable anywhere in the app.
 * Supports: success, error, warning, info, loading states.
 */
import { create } from 'zustand'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, XCircle, AlertTriangle, Info, X, Loader2 } from 'lucide-react'
import { useEffect } from 'react'

let toastIdCounter = 0

const useToastStore = create((set) => ({
  toasts: [],
  
  addToast: (toast) => {
    const id = ++toastIdCounter
    set((state) => ({
      toasts: [...state.toasts, { id, ...toast, createdAt: Date.now() }]
    }))
    return id
  },
  
  removeToast: (id) => set((state) => ({
    toasts: state.toasts.filter(t => t.id !== id)
  })),
  
  updateToast: (id, updates) => set((state) => ({
    toasts: state.toasts.map(t => t.id === id ? { ...t, ...updates } : t)
  })),
}))

// Imperative API — call toast.success('msg') from anywhere
export const toast = {
  success: (message, options = {}) => {
    return useToastStore.getState().addToast({ type: 'success', message, duration: 4000, ...options })
  },
  error: (message, options = {}) => {
    return useToastStore.getState().addToast({ type: 'error', message, duration: 6000, ...options })
  },
  warning: (message, options = {}) => {
    return useToastStore.getState().addToast({ type: 'warning', message, duration: 5000, ...options })
  },
  info: (message, options = {}) => {
    return useToastStore.getState().addToast({ type: 'info', message, duration: 4000, ...options })
  },
  loading: (message, options = {}) => {
    return useToastStore.getState().addToast({ type: 'loading', message, duration: 0, ...options })
  },
  dismiss: (id) => {
    useToastStore.getState().removeToast(id)
  },
  update: (id, updates) => {
    useToastStore.getState().updateToast(id, updates)
  },
  promise: async (promise, { loading, success, error }) => {
    const id = toast.loading(loading)
    try {
      const result = await promise
      useToastStore.getState().updateToast(id, {
        type: 'success',
        message: typeof success === 'function' ? success(result) : success,
        duration: 4000,
      })
      setTimeout(() => useToastStore.getState().removeToast(id), 4000)
      return result
    } catch (err) {
      useToastStore.getState().updateToast(id, {
        type: 'error',
        message: typeof error === 'function' ? error(err) : error,
        duration: 6000,
      })
      setTimeout(() => useToastStore.getState().removeToast(id), 6000)
      throw err
    }
  },
}

const TOAST_CONFIG = {
  success: {
    icon: CheckCircle2,
    bgClass: 'bg-emerald-500/10 border-emerald-500/20',
    iconColor: 'text-emerald-400',
    barColor: 'bg-emerald-500',
  },
  error: {
    icon: XCircle,
    bgClass: 'bg-red-500/10 border-red-500/20',
    iconColor: 'text-red-400',
    barColor: 'bg-red-500',
  },
  warning: {
    icon: AlertTriangle,
    bgClass: 'bg-amber-500/10 border-amber-500/20',
    iconColor: 'text-amber-400',
    barColor: 'bg-amber-500',
  },
  info: {
    icon: Info,
    bgClass: 'bg-sky-500/10 border-sky-500/20',
    iconColor: 'text-sky-400',
    barColor: 'bg-sky-500',
  },
  loading: {
    icon: Loader2,
    bgClass: 'bg-white/5 border-white/10',
    iconColor: 'text-slate-400',
    barColor: 'bg-slate-500',
  },
}

function ToastItem({ toast }) {
  const { removeToast } = useToastStore()
  const config = TOAST_CONFIG[toast.type] || TOAST_CONFIG.info
  const Icon = config.icon

  useEffect(() => {
    if (toast.duration === 0) return // loading toasts stay until manually dismissed
    const timer = setTimeout(() => removeToast(toast.id), toast.duration)
    return () => clearTimeout(timer)
  }, [toast.id, toast.duration, removeToast])

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 60, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 60, scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className={`relative flex items-start gap-3 w-80 p-4 rounded-2xl border backdrop-blur-xl shadow-2xl overflow-hidden ${config.bgClass}`}
      style={{ background: 'rgba(5, 5, 10, 0.92)' }}
    >
      {/* Progress bar */}
      {toast.duration > 0 && (
        <motion.div
          initial={{ scaleX: 1 }}
          animate={{ scaleX: 0 }}
          transition={{ duration: toast.duration / 1000, ease: 'linear' }}
          className={`absolute bottom-0 left-0 h-0.5 w-full origin-left ${config.barColor}`}
          style={{ opacity: 0.5 }}
        />
      )}

      <div className={`mt-0.5 flex-shrink-0 ${config.iconColor}`}>
        <Icon className={`w-5 h-5 ${toast.type === 'loading' ? 'animate-spin' : ''}`} />
      </div>

      <div className="flex-1 min-w-0">
        {toast.title && (
          <p className="text-sm font-bold text-white mb-0.5">{toast.title}</p>
        )}
        <p className="text-sm text-slate-300 leading-snug">{toast.message}</p>
      </div>

      <button
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 text-slate-600 hover:text-slate-300 transition-colors p-0.5 rounded"
      >
        <X className="w-4 h-4" />
      </button>
    </motion.div>
  )
}

export function ToastContainer() {
  const { toasts } = useToastStore()

  return (
    <div className="fixed top-6 right-6 z-[9999] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence mode="sync">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <ToastItem toast={t} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export default toast
