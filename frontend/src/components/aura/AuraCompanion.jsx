import { motion, AnimatePresence } from 'framer-motion'
import { useAura, AURA_STATES } from './AuraContext'
import { MessageCircle, X, Zap } from 'lucide-react'
import AuraChat from './AuraChat'

// ── Aura SVG Avatar ───────────────────────────────────────────────────────────
function AuraAvatar({ state }) {
  const colors = {
    [AURA_STATES.IDLE]:     { primary: '#0ea5e9', secondary: '#a855f7', glow: '#0ea5e940' },
    [AURA_STATES.THINKING]: { primary: '#f59e0b', secondary: '#f97316', glow: '#f59e0b40' },
    [AURA_STATES.HAPPY]:    { primary: '#10b981', secondary: '#34d399', glow: '#10b98140' },
    [AURA_STATES.ALERT]:    { primary: '#ef4444', secondary: '#f97316', glow: '#ef444450' },
    [AURA_STATES.SPEAKING]: { primary: '#a855f7', secondary: '#0ea5e9', glow: '#a855f740' },
  }
  const c = colors[state] || colors[AURA_STATES.IDLE]

  return (
    <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
      <defs>
        <radialGradient id={`aura-grad-${state}`} cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor={c.secondary} />
          <stop offset="100%" stopColor={c.primary} />
        </radialGradient>
        <filter id="aura-glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      {/* Outer ring */}
      <motion.circle
        cx="40" cy="40"
        stroke={c.primary} strokeWidth="1.5" fill="none" strokeOpacity="0.3"
        initial={{ r: 37, strokeOpacity: 0.3 }}
        animate={{ strokeOpacity: [0.2, 0.5, 0.2], r: [36, 38, 36] }}
        transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
      />
      {/* Face */}
      <circle cx="40" cy="40" r="28" fill="rgba(5,5,10,0.9)" stroke={c.primary} strokeWidth="1.5" />
      <circle cx="40" cy="34" r="20" fill={`url(#aura-grad-${state})`} fillOpacity="0.15" />
      {/* Eyes */}
      <motion.circle cx="32" cy="35" r="3.5" fill={c.primary}
        initial={{ scaleY: 1, opacity: 1 }}
        animate={state === AURA_STATES.THINKING
          ? { scaleY: [1, 0.2, 1], opacity: [1, 0.5, 1] }
          : state === AURA_STATES.HAPPY
          ? { scaleY: [1, 0.4, 1], opacity: 1 }
          : { scaleY: 1, opacity: [0.8, 1, 0.8] }}
        transition={{ repeat: Infinity, duration: state === AURA_STATES.THINKING ? 1.5 : 3 }}
      />
      <motion.circle cx="48" cy="35" r="3.5" fill={c.primary}
        initial={{ scaleY: 1, opacity: 1 }}
        animate={state === AURA_STATES.THINKING
          ? { scaleY: [1, 0.2, 1], opacity: [1, 0.5, 1] }
          : state === AURA_STATES.HAPPY
          ? { scaleY: [1, 0.4, 1], opacity: 1 }
          : { scaleY: 1, opacity: [0.8, 1, 0.8] }}
        transition={{ repeat: Infinity, duration: state === AURA_STATES.THINKING ? 1.5 : 3, delay: 0.1 }}
      />
      {/* Mouth */}
      {state === AURA_STATES.HAPPY || state === AURA_STATES.SPEAKING ? (
        <motion.path d="M 33 46 Q 40 52 47 46" stroke={c.primary} strokeWidth="2" strokeLinecap="round" fill="none"
          animate={{ d: ['M 33 46 Q 40 52 47 46', 'M 33 45 Q 40 53 47 45', 'M 33 46 Q 40 52 47 46'] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
        />
      ) : state === AURA_STATES.ALERT ? (
        <motion.path d="M 33 49 Q 40 44 47 49" stroke={c.primary} strokeWidth="2" strokeLinecap="round" fill="none" />
      ) : (
        <motion.path d="M 34 47 Q 40 50 46 47" stroke={c.primary} strokeWidth="2" strokeLinecap="round" fill="none" />
      )}
      {/* Thinking dots */}
      {state === AURA_STATES.THINKING && (
        <g>
          {[0, 1, 2].map((i) => (
            <motion.circle key={i} cx={34 + i * 6} cy="58" r="2" fill={c.primary}
              animate={{ opacity: [0.2, 1, 0.2], y: [0, -3, 0] }}
              transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.2 }}
            />
          ))}
        </g>
      )}
      {/* Alert bolt */}
      {state === AURA_STATES.ALERT && (
        <motion.text x="36" y="58" fontSize="12" fill={c.primary}
          animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 0.6 }}>⚡</motion.text>
      )}
    </svg>
  )
}

// ── Main Companion Component ──────────────────────────────────────────────────
export default function AuraCompanion() {
  const { isOpen, openChat, closeChat, auraState, alertCount } = useAura()

  const floatVariants = {
    [AURA_STATES.IDLE]:     { y: [0, -8, 0], rotate: [0, 1, -1, 0] },
    [AURA_STATES.THINKING]: { y: [0, -4, 0], rotate: [0, 2, -2, 0] },
    [AURA_STATES.ALERT]:    { y: [0, -12, 0, -12, 0], x: [0, -3, 3, -3, 0] },
    [AURA_STATES.HAPPY]:    { y: [0, -14, 0], scale: [1, 1.05, 1] },
    [AURA_STATES.SPEAKING]: { y: [0, -6, 0] },
  }

  return (
    <>
      {/* Floating Avatar Button */}
      <motion.div
        className="fixed bottom-6 right-6 z-50 select-none"
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 1 }}
      >
        {/* Glow ring behind button */}
        <motion.div
          className="absolute inset-0 rounded-full"
          animate={{
            boxShadow: auraState === AURA_STATES.ALERT
              ? ['0 0 20px #ef444430', '0 0 40px #ef444460', '0 0 20px #ef444430']
              : ['0 0 15px #0ea5e920', '0 0 30px #0ea5e940', '0 0 15px #0ea5e920'],
          }}
          transition={{ repeat: Infinity, duration: 2 }}
        />

        {/* Alert badge */}
        <AnimatePresence>
          {alertCount > 0 && !isOpen && (
            <motion.div
              initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
              className="absolute -top-1 -right-1 w-5 h-5 bg-rose-500 rounded-full flex items-center justify-center z-10 border-2 border-[#05050a]"
            >
              <span className="text-[9px] font-black text-white">{alertCount}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Avatar */}
        <motion.button
          id="aura-toggle-btn"
          onClick={isOpen ? closeChat : openChat}
          className="relative w-16 h-16 rounded-full cursor-pointer focus:outline-none"
          animate={floatVariants[auraState] || floatVariants[AURA_STATES.IDLE]}
          transition={{ repeat: Infinity, duration: 4, ease: 'easeInOut' }}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
        >
          <div className="w-full h-full rounded-full overflow-hidden border-2 border-sky-500/40 bg-[#0a0a1a] shadow-2xl">
            <AuraAvatar state={auraState} />
          </div>
          {/* Label badge */}
          <motion.div
            className="absolute -top-8 left-1/2 -translate-x-1/2 bg-[#0d0d1a] border border-sky-500/30 rounded-full px-3 py-1 whitespace-nowrap"
            initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 2 }}
          >
            <span className="text-[9px] font-black text-sky-400 uppercase tracking-widest">Aura AI</span>
          </motion.div>
        </motion.button>
      </motion.div>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && <AuraChat />}
      </AnimatePresence>
    </>
  )
}
