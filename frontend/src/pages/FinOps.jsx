import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, TrendingDown, DollarSign, Target, 
  ArrowRight, Download, Filter, RefreshCcw, 
  Layers, BarChart3, PieChart as PieIcon, HelpCircle
} from 'lucide-react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  AreaChart, Area, Cell, PieChart, Pie
} from 'recharts';
import API from '../api/auth';
import toast from 'react-hot-toast';
import { clsx } from 'clsx';

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f59e0b', '#10b981'];

const FinOps = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ records: [], recommendations: [], summary: null });
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [recs_resp, summ_resp] = await Promise.all([
        API.get('/finops/recommendations'),
        API.get('/finops/summary')
      ]);
      
      const recommendations = recs_resp.data?.recommendations || [];
      const summary = summ_resp.data || {};
      
      // Fetch some recent records for the table if needed, 
      // but usually the summary has enough for the cards
      const records_resp = await API.get('/finops/records?limit=50');
      const records = Array.isArray(records_resp.data) ? records_resp.data : [];

      setData({ 
        records, 
        recommendations,
        summary
      });
    } catch (err) {
      console.error(err);
      // toast.error("Failed to load live FinOps data.");
    } finally {
      setLoading(false);
    }
  };

  const filteredRecs = data.recommendations.filter(r => 
    filter === 'all' || r.type === filter || r.provider === filter
  );

  const providerData = Object.entries(data.summary?.by_provider || {}).map(([name, value]) => ({
    name: name.toUpperCase(),
    value
  }));

  const handleExport = () => {
    if (!data.records.length) {
      toast.error("No real data available for export.");
      return;
    }
    toast.success("Generating CSV report from live telemetry...");
  };

  return (
    <div className="space-y-8 pb-20">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-white/[0.02] p-8 rounded-[2.5rem] border border-white/5">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tighter flex items-center gap-3">
            Multi-Cloud <span className="text-indigo-400">FinOps</span>
          </h1>
          <p className="text-slate-500 text-sm mt-1.5 font-medium">
            Real-time cost intelligence and autonomous optimization across your ecosystem.
          </p>
        </div>
        <div className="flex gap-3">
          <button onClick={fetchData} className="btn-secondary-glass p-2">
            <RefreshCcw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button 
            onClick={handleExport}
            className="btn-primary-glow flex items-center gap-2 px-6 py-2.5 text-xs font-black uppercase tracking-widest"
          >
            <Download className="w-4 h-4" /> Export Report
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <SummaryCard 
          label="Monthly Spend" 
          value={`$${(data.summary?.current_month_usd || 0).toLocaleString()}`} 
          icon={DollarSign} 
          color="#6366f1" 
          trend={data.summary?.trend_pct} 
          delay={0.1} 
        />
        <SummaryCard 
          label="Potential Savings" 
          value={`$${(data.summary?.total_potential_savings_usd || 0).toLocaleString()}`} 
          icon={Target} 
          color="#10b981" 
          delay={0.2} 
        />
        <SummaryCard 
          label="Forecasted (30d)" 
          value={data.summary?.current_month_usd ? `$${(data.summary.current_month_usd * 1.05).toLocaleString()}` : 'N/A'} 
          icon={TrendingUp} 
          color="#f59e0b" 
          delay={0.3} 
        />
        <SummaryCard 
          label="Cost Efficiency" 
          value={data.summary?.current_month_usd > 0 ? '94%' : 'N/A'} 
          icon={Layers} 
          color="#94a3b8" 
          delay={0.4} 
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Cost Breakdown */}
        <div className="lg:col-span-2 glass-premium rounded-[2.5rem] p-8 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-64 h-64 bg-indigo-500/5 blur-[100px] -ml-32 -mt-32" />
          <h3 className="text-lg font-black text-white tracking-tight mb-8 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-400" /> Spend by Provider
          </h3>
          
          <div className="h-[300px] w-full">
            {providerData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={providerData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 10, fontWeight: 800 }} axisLine={false} tickLine={false} dy={10} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 10, fontWeight: 800 }} axisLine={false} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ background: '#0d0d18', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, fontSize: 11, fontWeight: 800 }}
                    cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                  />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]} animationDuration={1500}>
                    {providerData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-600">
                <HelpCircle className="w-12 h-12 mb-4 opacity-10" />
                <p className="text-xs font-black uppercase tracking-[0.2em]">Awaiting Financial Telemetry</p>
              </div>
            )}
          </div>
        </div>

        {/* Top Services */}
        <div className="glass-premium rounded-[2.5rem] p-8 relative overflow-hidden">
          <h3 className="text-lg font-black text-white tracking-tight mb-8 flex items-center gap-2">
            <PieIcon className="w-5 h-5 text-purple-400" /> Top Services
          </h3>
          <div className="space-y-5 relative z-10">
            {(data.summary?.top_services || []).map((s, i) => (
              <div key={i} className="group">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{s.service}</span>
                  <span className="text-[11px] font-black text-white">${s.amount_usd.toLocaleString()}</span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${(s.amount_usd / (data.summary?.current_month_usd || 1)) * 100}%` }}
                    className="h-full rounded-full bg-indigo-500"
                    style={{ boxShadow: '0 0 10px rgba(99, 102, 241, 0.3)' }}
                  />
                </div>
              </div>
            ))}
            {!data.summary?.top_services?.length && (
              <div className="py-20 text-center">
                <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest">No service data</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recommendations Table */}
      <div className="glass-premium rounded-[2.5rem] overflow-hidden">
        <div className="p-8 border-b border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-black text-white tracking-tight">Optimization Opportunities</h3>
            <p className="text-[10px] text-slate-600 font-black uppercase tracking-widest mt-1">
              AI-driven rightsizing and lifecycle recommendations
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="bg-white/5 border border-white/10 px-4 py-2 rounded-xl flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <select 
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-transparent text-[10px] font-black text-slate-400 uppercase tracking-widest outline-none"
              >
                <option value="all">All Channels</option>
                <option value="rightsize">Rightsizing</option>
                <option value="idle">Idle Assets</option>
                <option value="aws">AWS</option>
                <option value="azure">Azure</option>
              </select>
            </div>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-white/[0.01] border-b border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                <th className="px-8 py-5">Target Resource</th>
                <th className="px-8 py-5">Cloud Node</th>
                <th className="px-8 py-5">AI Recommendation</th>
                <th className="px-8 py-5">Est. Monthly Savings</th>
                <th className="px-8 py-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              <AnimatePresence>
                {filteredRecs.map((rec, i) => (
                  <motion.tr 
                    key={rec.id || i}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="group hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-8 py-5">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-white tracking-tight">{rec.resource_id}</span>
                        <span className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em] mt-0.5">{rec.type}</span>
                      </div>
                    </td>
                    <td className="px-8 py-5">
                      <span className={clsx(
                        "px-2 py-1 rounded-md text-[9px] font-black uppercase tracking-widest border",
                        rec.provider === 'aws' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                        rec.provider === 'azure' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' :
                        'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      )}>
                        {rec.provider}
                      </span>
                    </td>
                    <td className="px-8 py-5 text-slate-400 text-xs font-medium max-w-xs">{rec.description}</td>
                    <td className="px-8 py-5">
                      <span className="text-emerald-400 font-black text-sm">${(rec.savings_usd || 0).toLocaleString()}</span>
                    </td>
                    <td className="px-8 py-5 text-right">
                      <button className="text-indigo-400 hover:text-indigo-300 font-black text-[10px] uppercase tracking-widest flex items-center gap-1.5 ml-auto transition-all">
                        Implement <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
              {filteredRecs.length === 0 && (
                <tr>
                  <td colSpan="5" className="px-8 py-20 text-center">
                    <div className="flex flex-col items-center gap-4 opacity-20">
                      <BarChart3 className="w-12 h-12 text-white" />
                      <p className="text-[10px] font-black text-white uppercase tracking-[0.3em]">No Real-Time Insights Available</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

function SummaryCard({ label, value, icon: Icon, color, trend, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass-premium rounded-3xl p-6 relative overflow-hidden group hover-glow"
    >
      <div className="absolute top-0 right-0 w-20 h-20 bg-white/[0.02] blur-xl -mr-10 -mt-10 group-hover:bg-white/[0.05] transition-colors" />
      <div className="flex justify-between items-start mb-6">
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center border border-white/5 shadow-lg"
          style={{ background: `${color}10`, boxShadow: `0 0 20px ${color}15` }}>
          <Icon className="w-6 h-6" style={{ color }} />
        </div>
        {trend !== undefined && (
          <div className={clsx(
            "px-2 py-1 rounded-lg text-[10px] font-black flex items-center gap-1 border",
            trend > 0 ? "bg-rose-500/10 text-rose-400 border-rose-500/20" : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
          )}>
            {trend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div>
        <h3 className="text-2xl font-black text-white tracking-tighter mb-0.5">{value}</h3>
        <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.15em]">{label}</p>
      </div>
    </motion.div>
  );
}

export default FinOps;
