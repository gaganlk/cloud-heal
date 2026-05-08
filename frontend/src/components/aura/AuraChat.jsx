import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Send, Loader2, Bot, User, Sparkles, Cpu, ShieldAlert, HeartPulse, RefreshCw, Zap } from 'lucide-react'
import { useAura, AURA_STATES } from './AuraContext'
import { chatWithAura, getAuraContext } from '../../api/aura'
import { clsx } from 'clsx'

// ── Quick action chips ────────────────────────────────────────────────────────
const QUICK_ACTIONS = [
  { label: 'Degraded Resources', icon: ShieldAlert, query: 'Show me all degraded or critical resources right now' },
  { label: 'Last Healing', icon: HeartPulse, query: 'Explain the last autonomous healing action taken' },
  { label: 'CPU Hotspots', icon: Cpu, query: 'Which resources have the highest CPU usage?' },
  { label: 'System Health', icon: RefreshCw, query: 'Give me a full system health summary' },
]

// ── Markdown-style message renderer ──────────────────────────────────────────
function MessageContent({ content }) {
  // Simple bold + code formatting
  const parts = content.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return (
    <span>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**'))
          return <strong key={i} className="font-black text-white">{part.slice(2, -2)}</strong>
        if (part.startsWith('`') && part.endsWith('`'))
          return <code key={i} className="text-sky-300 bg-sky-500/10 px-1.5 py-0.5 rounded text-[10px] font-mono">{part.slice(1, -1)}</code>
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}

// ── Chat message bubble ───────────────────────────────────────────────────────
function ChatBubble({ msg }) {
  const isAura = msg.role === 'aura'
  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className={clsx('flex gap-3', isAura ? 'flex-row' : 'flex-row-reverse')}
    >
      {/* Avatar */}
      <div className={clsx(
        'w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center border',
        isAura
          ? 'bg-gradient-to-br from-sky-500 to-purple-600 border-sky-500/30'
          : 'bg-white/5 border-white/10'
      )}>
        {isAura ? <Bot className="w-4 h-4 text-white" /> : <User className="w-4 h-4 text-slate-400" />}
      </div>
      {/* Bubble */}
      <div className={clsx(
        'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
        isAura
          ? 'bg-gradient-to-br from-sky-500/10 to-purple-500/10 border border-sky-500/20 text-slate-200 rounded-tl-sm'
          : 'bg-white/5 border border-white/10 text-slate-300 rounded-tr-sm'
      )}>
        {msg.isTyping ? (
          <motion.div className="flex gap-1 items-center py-1">
            {[0, 1, 2].map((i) => (
              <motion.span key={i} className="w-2 h-2 bg-sky-400 rounded-full"
                animate={{ y: [0, -5, 0] }}
                transition={{ repeat: Infinity, duration: 0.6, delay: i * 0.15 }}
              />
            ))}
          </motion.div>
        ) : (
          <MessageContent content={msg.content} />
        )}
        <div className="text-[9px] text-slate-600 mt-2 font-mono">
          {msg.timestamp?.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </motion.div>
  )
}

// ── Main Chat Panel ───────────────────────────────────────────────────────────
export default function AuraChat() {
  const { closeChat, messages, addMessage, setMessages, transitionState } = useAura()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [ctx, setCtx] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  // Load live system context on open
  useEffect(() => {
    getAuraContext().then((r) => setCtx(r.data)).catch(() => {})
    inputRef.current?.focus()
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async (query) => {
    const text = query ?? input.trim()
    if (!text || loading) return
    setInput('')
    setLoading(true)

    addMessage({ role: 'user', content: text })
    addMessage({ role: 'aura', content: '', isTyping: true, id: 'typing' })
    transitionState(AURA_STATES.THINKING, 30000)

    try {
      const res = await chatWithAura({ message: text, context: ctx })
      const reply = res.data.reply

      // Replace typing indicator with real message
      setMessages((prev) => {
        const filtered = prev.filter((m) => m.id !== 'typing')
        return [...filtered, { id: Date.now(), role: 'aura', content: reply, timestamp: new Date() }]
      })
      transitionState(AURA_STATES.SPEAKING, 4000)
    } catch (e) {
      setMessages((prev) => prev.filter((m) => m.id !== 'typing'))
      addMessage({
        role: 'aura',
        content: '⚠️ I ran into an issue connecting to the backend. Make sure the API server is running.',
      })
      transitionState(AURA_STATES.ALERT, 3000)
    } finally {
      setLoading(false)
    }
  }, [input, loading, ctx, addMessage, setMessages, transitionState])

  return (
    <motion.div
      id="aura-chat-panel"
      initial={{ opacity: 0, y: 30, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 30, scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="fixed bottom-28 right-6 z-50 w-[380px] max-h-[600px] flex flex-col rounded-[2rem] overflow-hidden shadow-2xl border border-sky-500/20"
      style={{ background: 'rgba(5, 5, 15, 0.97)', backdropFilter: 'blur(40px)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5 bg-gradient-to-r from-sky-500/5 to-purple-500/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-sky-500 to-purple-600 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-black text-white">Aura</h3>
            <p className="text-[9px] text-sky-400 uppercase tracking-widest font-bold">AI Healing Companion</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {ctx && (
            <div className="text-[9px] text-emerald-400 bg-emerald-400/10 border border-emerald-400/20 rounded-full px-2 py-0.5 font-black uppercase tracking-widest flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              Live
            </div>
          )}
          <button onClick={closeChat} className="w-7 h-7 rounded-xl bg-white/5 hover:bg-white/10 transition-all flex items-center justify-center">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>
      </div>

      {/* Context strip */}
      {ctx && (
        <div className="flex items-center gap-4 px-4 py-2 border-b border-white/5 text-[9px] font-black uppercase tracking-widest">
          <span className="text-slate-600">Resources: <span className="text-white">{ctx.total_resources ?? '—'}</span></span>
          <span className="text-slate-600">Critical: <span className="text-rose-400">{ctx.critical_count ?? 0}</span></span>
          <span className="text-slate-600">Healed: <span className="text-emerald-400">{ctx.healing_total ?? 0}</span></span>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0" style={{ maxHeight: '340px' }}>
        <AnimatePresence initial={false}>
          {messages.map((msg) => (
            <ChatBubble key={msg.id} msg={msg} />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* Quick Actions */}
      <div className="px-4 py-2 flex gap-2 flex-wrap border-t border-white/5">
        {QUICK_ACTIONS.map((a) => (
          <button
            key={a.label}
            onClick={() => sendMessage(a.query)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/10 text-[9px] font-black uppercase tracking-wider text-slate-400 hover:text-white hover:bg-white/[0.07] hover:border-sky-500/30 transition-all disabled:opacity-40"
          >
            <a.icon className="w-3 h-3" />
            {a.label}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="px-4 py-4 border-t border-white/5">
        <div className="flex gap-2 items-center bg-white/[0.03] border border-white/10 rounded-2xl px-4 py-2.5 focus-within:border-sky-500/40 transition-all">
          <Zap className="w-4 h-4 text-sky-500 flex-shrink-0" />
          <input
            ref={inputRef}
            id="aura-chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="Ask Aura anything..."
            disabled={loading}
            className="flex-1 bg-transparent text-sm text-white placeholder:text-slate-600 focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="w-8 h-8 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center flex-shrink-0 hover:shadow-[0_0_15px_rgba(14,165,233,0.4)] transition-all disabled:opacity-40 disabled:pointer-events-none"
          >
            {loading ? <Loader2 className="w-4 h-4 text-white animate-spin" /> : <Send className="w-4 h-4 text-white" />}
          </button>
        </div>
      </div>
    </motion.div>
  )
}
