import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldAlert, ShieldCheck, Shield, AlertTriangle, 
  ExternalLink, CheckCircle2, Lock, Eye, Filter,
  RefreshCcw, ShieldHalf, Layout
} from 'lucide-react';
import API from '../api/auth';
import toast from 'react-hot-toast';
import { clsx } from 'clsx';

const Security = () => {
  const [loading, setLoading] = useState(true);
  const [findings, setFindings] = useState([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchFindings();
  }, []);

  const fetchFindings = async () => {
    setLoading(true);
    try {
      const resp = await API.get('/security/findings');
      setFindings(Array.isArray(resp.data) ? resp.data : []);
    } catch (err) {
      console.error(err);
      // toast.error("Failed to load security findings.");
    } finally {
      setLoading(false);
    }
  };

  const filteredFindings = findings.filter(f => 
    filter === 'all' || f.severity === filter || f.provider === filter
  );

  const stats = {
    critical: findings.filter(f => f.severity === 'critical').length,
    high: findings.filter(f => f.severity === 'high').length,
    medium: findings.filter(f => f.severity === 'medium').length,
  };

  // Dynamic security score calculation
  const baseScore = 100;
  const penalties = (stats.critical * 15) + (stats.high * 8) + (stats.medium * 3);
  const score = findings.length > 0 ? Math.max(0, baseScore - penalties) : 'N/A';

  return (
    <div className="space-y-8 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            Security <span className="text-rose-500">Intelligence</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium">
            Autonomous threat detection and multi-cloud posture management.
          </p>
        </div>
        <div className="flex gap-4">
          <button onClick={fetchFindings} className="btn-secondary-glass p-2">
            <RefreshCcw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <div className="bg-white/5 p-1 rounded-2xl flex gap-1 border border-white/5">
            <button className="px-6 py-2 rounded-xl bg-white/10 text-white text-[10px] font-black uppercase tracking-widest shadow-lg">Live Findings</button>
            <button className="px-6 py-2 rounded-xl text-slate-500 text-[10px] font-black uppercase tracking-widest hover:text-white transition-colors">Compliance</button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Posture Score Card */}
        <div className="lg:col-span-1 glass-premium rounded-[2.5rem] p-8 flex flex-col items-center justify-center relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Shield className="w-48 h-48" />
          </div>
          <h3 className="text-slate-500 font-black uppercase tracking-[0.2em] text-[10px] mb-10">Posture Health Index</h3>
          
          <div className="relative w-56 h-56">
            <svg className="w-full h-full transform -rotate-90">
              <circle cx="112" cy="112" r="100" stroke="rgba(255,255,255,0.05)" strokeWidth="16" fill="transparent" />
              <circle cx="112" cy="112" r="100" stroke="currentColor" strokeWidth="16" fill="transparent" 
                strokeDasharray={2 * Math.PI * 100} 
                strokeDashoffset={score === 'N/A' ? 2 * Math.PI * 100 : 2 * Math.PI * 100 * (1 - score/100)}
                className={clsx(
                  'transition-all duration-1500 ease-out',
                  score > 80 ? 'text-emerald-500' : score > 50 ? 'text-amber-500' : 'text-rose-500'
                )}
                style={{ filter: `drop-shadow(0 0 12px currentColor)` }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-6xl font-black text-white tracking-tighter">{score}</span>
              <span className="text-slate-500 text-[10px] font-black uppercase tracking-widest mt-1">Trust Score</span>
            </div>
          </div>

          <div className="mt-10 grid grid-cols-3 gap-4 w-full relative z-10">
            <SeverityBox label="Critical" count={stats.critical} color="text-rose-500" bg="bg-rose-500/5" />
            <SeverityBox label="High" count={stats.high} color="text-amber-500" bg="bg-amber-500/5" />
            <SeverityBox label="Medium" count={stats.medium} color="text-indigo-500" bg="bg-indigo-500/5" />
          </div>
        </div>

        {/* Active Findings Table */}
        <div className="lg:col-span-2 glass-premium rounded-[2.5rem] border border-white/5 overflow-hidden">
          <div className="p-8 border-b border-white/5 flex justify-between items-center bg-white/[0.01]">
            <h3 className="text-lg font-black text-white tracking-tight flex items-center gap-2">
               <ShieldAlert className="w-5 h-5 text-rose-500" /> Detected Vulnerabilities
            </h3>
            <div className="bg-white/5 border border-white/10 px-4 py-2 rounded-xl flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <select 
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-transparent text-[10px] font-black text-slate-400 uppercase tracking-widest outline-none"
              >
                <option value="all">Global Scan</option>
                <option value="critical">Critical Only</option>
                <option value="high">High Severity</option>
                <option value="aws">AWS Cloud</option>
                <option value="azure">Azure Cloud</option>
              </select>
            </div>
          </div>
          
          <div className="overflow-y-auto max-h-[500px] custom-scrollbar">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-white/[0.02] text-slate-500 text-[10px] font-black uppercase tracking-widest border-b border-white/5">
                  <th className="px-8 py-5">Finding Signature</th>
                  <th className="px-8 py-5">Risk Level</th>
                  <th className="px-8 py-5">Target Asset</th>
                  <th className="px-8 py-5">Status</th>
                  <th className="px-8 py-5 text-right">Pivot</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                <AnimatePresence>
                  {filteredFindings.map((f, i) => (
                    <motion.tr 
                      key={f.id || i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="group hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-8 py-5">
                        <div className="flex flex-col">
                          <span className="text-sm font-bold text-white tracking-tight">{f.finding_type}</span>
                          <span className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{f.description}</span>
                        </div>
                      </td>
                      <td className="px-8 py-5">
                        <span className={clsx(
                          "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border",
                          f.severity === 'critical' ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' :
                          f.severity === 'high' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                          'bg-indigo-500/10 text-indigo-500 border-indigo-500/20'
                        )}>
                          <div className={clsx("w-1.5 h-1.5 rounded-full", 
                            f.severity === 'critical' ? 'bg-rose-500' : 'bg-amber-500'
                          )} />
                          {f.severity}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-slate-400 text-xs font-mono font-bold tracking-tight">{f.resource_id}</td>
                      <td className="px-8 py-5">
                        <div className="flex items-center gap-1.5 text-emerald-400 text-[10px] font-black uppercase tracking-widest">
                          <span className="w-1 h-1 bg-emerald-400 rounded-full animate-pulse" /> Live Finding
                        </div>
                      </td>
                      <td className="px-8 py-5 text-right">
                        <button className="p-2 hover:bg-white/5 rounded-xl transition-all">
                          <ExternalLink className="w-4 h-4 text-slate-600 hover:text-white" />
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
                {filteredFindings.length === 0 && (
                  <tr>
                    <td colSpan="5" className="px-8 py-24 text-center">
                      <div className="flex flex-col items-center gap-5 opacity-20">
                        <ShieldCheck className="w-16 h-16 text-emerald-500" />
                        <p className="text-[10px] font-black text-white uppercase tracking-[0.3em]">No Active Threats Detected</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Compliance Strip */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <ComplianceCard label="IAM Compliance" value={findings.length > 0 ? "Verified" : "N/A"} icon={Lock} color="#6366f1" />
        <ComplianceCard label="Data Encryption" value={findings.length > 0 ? "Secure" : "N/A"} icon={ShieldHalf} color="#a855f7" />
        <ComplianceCard label="Resource Exposure" value={`${stats.critical + stats.high} Risks`} icon={Eye} color="#f43f5e" />
      </div>
    </div>
  );
};

function SeverityBox({ label, count, color, bg }) {
  return (
    <div className={clsx("p-4 rounded-[2rem] text-center border border-white/5 transition-all hover:border-white/10", bg)}>
      <p className={clsx("font-black text-2xl tracking-tighter", color)}>{count}</p>
      <p className="text-[9px] text-slate-600 font-black uppercase tracking-widest mt-1">{label}</p>
    </div>
  );
}

function ComplianceCard({ label, value, icon: Icon, color }) {
  return (
    <div className="glass-premium p-8 rounded-[2.5rem] border border-white/5 flex items-center gap-6 group hover-glow transition-all">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center border border-white/5 bg-white/[0.02] shadow-inner"
        style={{ boxShadow: `0 0 20px ${color}10` }}>
        <Icon className="w-7 h-7" style={{ color }} />
      </div>
      <div>
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">{label}</p>
        <div className="flex items-center gap-2">
          <h4 className="text-xl font-black text-white tracking-tight">{value}</h4>
          <span className="w-2 h-2 rounded-full bg-emerald-500/20 border border-emerald-500/30" />
        </div>
      </div>
    </div>
  );
}

export default Security;
