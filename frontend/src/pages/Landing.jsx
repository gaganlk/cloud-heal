import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { 
  Activity, Shield, Zap, Globe, HeartPulse, 
  ArrowRight, CheckCircle2, Cloud, Brain, 
  ShieldCheck, ZapOff, Play, Users
} from 'lucide-react'

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#05050a] text-white selection:bg-sky-500/30">
      {/* Background VFX */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-600/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-sky-600/10 blur-[120px] rounded-full" />
        <div className="absolute inset-0 grid-pattern opacity-30" />
      </div>

      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 glass-dark border-b border-white/5 h-20 px-8 flex items-center justify-between">
         <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sky-400 to-indigo-600 flex items-center justify-center shadow-[0_0_20px_rgba(14,165,233,0.3)]">
               <Activity className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-black tracking-tighter">CloudHeal</span>
         </div>
         <div className="hidden md:flex items-center gap-10">
            {['Engine', 'Resilience', 'Safety', 'Company'].map(link => (
              <a key={link} href="#" className="text-xs font-black uppercase tracking-[0.2em] text-slate-400 hover:text-sky-400 transition-colors">{link}</a>
            ))}
         </div>
          <div className="flex items-center gap-4">
             <button 
                onClick={() => {
                   window.localStorage.removeItem('cloud-heal-auth')
                   window.location.href = '/login'
                }}
                className="text-sm font-bold text-slate-400 hover:text-white transition-colors"
             >
                Sign In
             </button>
             <Link to="/register" className="btn-primary-glow !py-2.5 !px-6 text-xs uppercase font-black tracking-widest">
               Get Priority Access
             </Link>
          </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-44 pb-32 px-8">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-premium border-sky-500/20 mb-8"
          >
            <span className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-sky-400">Autonomous Cloud V2.0 Now Live</span>
          </motion.div>
          
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-6xl md:text-8xl font-black tracking-tighter leading-[0.9] mb-8"
          >
            Heal your cloud <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 via-indigo-500 to-purple-500">
              at light speed.
            </span>
          </motion.h1>
          
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto font-medium leading-relaxed mb-12"
          >
            The world's first autonomous self-healing platform for multi-cloud ecosystems. 
            Identify, simulate, and resolve failures before they impact your users.
          </motion.p>

          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4"
          >
            <Link to="/register" className="btn-primary-glow !py-4 !px-10 text-sm">
              Deploy Autonomous Engine <ArrowRight className="w-5 h-5 ml-2" />
            </Link>
            <button className="btn-secondary-glass !py-4 !px-10 text-sm flex items-center gap-2">
              <Play className="w-4 h-4 fill-current" /> Watch Simulation
            </button>
          </motion.div>
        </div>
      </section>

      {/* Mock Interface Preview */}
      <section className="px-8 pb-32">
        <motion.div 
          initial={{ opacity: 0, y: 100 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: 'circOut' }}
          className="max-w-6xl mx-auto relative group"
        >
          <div className="absolute inset-0 bg-sky-500/10 blur-[120px] rounded-[3rem] group-hover:bg-sky-500/20 transition-colors" />
          <div className="glass-premium rounded-[3rem] border border-white/10 p-4 shadow-2xl relative overflow-hidden">
             <div className="bg-[#0b0c14] rounded-[2rem] overflow-hidden border border-white/5 aspect-video flex items-center justify-center">
                {/* Simulated UI Content */}
                <div className="text-center">
                   <div className="flex justify-center gap-4 mb-8">
                      {[1,2,3].map(i => <div key={i} className="w-12 h-12 rounded-xl bg-white/[0.02] border border-white/5 animate-pulse" />)}
                   </div>
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Interface Pre-visualization v2.4.0</p>
                </div>
             </div>
          </div>
          
          {/* Floating badges */}
          <motion.div 
             animate={{ y: [0, -10, 0] }}
             transition={{ duration: 4, repeat: Infinity }}
             className="absolute -top-12 -right-12 glass-premium p-6 rounded-3xl border-emerald-500/20 hidden lg:block"
          >
             <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                   <ShieldCheck className="w-6 h-6 text-emerald-400" />
                </div>
                <div>
                   <p className="text-xs font-black text-white uppercase tracking-tight">System Validated</p>
                   <p className="text-[9px] text-emerald-400/70 font-bold uppercase tracking-widest mt-0.5">Zero Failures Detected</p>
                </div>
             </div>
          </motion.div>
        </motion.div>
      </section>

      {/* Features Grid */}
      <section className="px-8 pb-32">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={Brain} 
              title="AI Failure Prediction" 
              desc="Machine learning models analyze telemetry strings to predict cascade failures before they happen."
              color="#0ea5e9"
            />
            <FeatureCard 
              icon={Zap} 
              title="Instant Remediation" 
              desc="Autonomous healing scripts trigger in milliseconds to redirect traffic or scale clusters automatically."
              color="#a855f7"
            />
            <FeatureCard 
              icon={Globe} 
              title="Multi-Cloud Mesh" 
              desc="Unified control plane across AWS, GCP, and Azure with deep dependency mapping."
              color="#f59e0b"
            />
          </div>
        </div>
      </section>

      {/* Trust Bar */}
      <div className="border-t border-white/5 bg-white/[0.01] py-12 px-8">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8 opacity-40 grayscale group-hover:grayscale-0 transition-all">
           <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.4em]">Engineered for elite teams at</p>
           <div className="flex flex-wrap justify-center gap-12 font-black text-2xl tracking-tighter text-slate-200">
              <span>FORTHCON</span>
              <span>SYNAPSE</span>
              <span>VOID_CORE</span>
              <span>QUANTUM</span>
              <span>AXON</span>
           </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-20 px-8 border-t border-white/5">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between gap-12">
          <div className="max-w-xs">
            <div className="flex items-center gap-3 mb-6">
              <Activity className="w-6 h-6 text-sky-400" />
              <span className="text-xl font-black tracking-tighter">CloudHeal</span>
            </div>
            <p className="text-sm text-slate-500 font-medium leading-relaxed">
              Pioneering the future of cloud autonomous operations. Built by Antigravity.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-12">
            <FooterColumn title="Engine" links={['Architecture', 'Simulation', 'AI Models', 'Security']} />
            <FooterColumn title="Legal" links={['Privacy Policy', 'Terms of Use', 'Security Audit', 'Patents']} />
            <FooterColumn title="Social" links={['Twitter / X', 'GitHub', 'LinkedIn', 'Discord']} />
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-20 pt-8 border-t border-white/5 flex justify-between items-center text-[10px] font-black text-slate-600 uppercase tracking-[0.2em]">
           <span>© 2026 CloudHeal Autonomous Systems</span>
           <span className="flex items-center gap-1.5"><HeartPulse className="w-3 h-3" /> Securely Monitored</span>
        </div>
      </footer>
    </div>
  )
}

function FeatureCard({ icon: Icon, title, desc, color }) {
  return (
    <motion.div 
      whileHover={{ y: -10 }}
      className="glass-premium rounded-[2.5rem] p-10 group relative transition-all"
    >
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-8 border border-white/10 group-hover:border-white/20 transition-colors shadow-inner"
        style={{ background: `${color}08` }}>
        <Icon className="w-8 h-8" style={{ color }} />
      </div>
      <h3 className="text-xl font-bold text-white mb-4 tracking-tight">{title}</h3>
      <p className="text-sm text-slate-500 font-medium leading-relaxed">{desc}</p>
    </motion.div>
  )
}

function FooterColumn({ title, links }) {
  return (
    <div className="space-y-4">
      <h4 className="text-[10px] font-black text-white uppercase tracking-[0.3em]">{title}</h4>
      <ul className="space-y-2">
        {links.map(l => (
          <li key={l}>
            <a href="#" className="text-xs font-bold text-slate-500 hover:text-white transition-colors">{l}</a>
          </li>
        ))}
      </ul>
    </div>
  )
}
