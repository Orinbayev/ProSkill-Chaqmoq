import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Bell, 
  Calendar, 
  Filter, 
  ArrowUpRight,
  TrendingUp,
  BarChart3,
  BrainCircuit,
  Menu,
  X,
  ChevronDown,
  MoreHorizontal,
  ArrowRight,
  Download
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { Sidebar } from './components/Sidebar';
import { KPICard } from './components/KPICard';
import { InsightCard } from './components/InsightCard';
import { DataCard } from './components/DataCard';
import { cn, formatCurrency } from './lib/utils';

// Premium Mock Data
const revenueTrend = [
  { name: 'Jan', revenue: 42000, expense: 31000, cash: 11000 },
  { name: 'Feb', revenue: 48000, expense: 32000, cash: 16000 },
  { name: 'Mar', revenue: 45000, expense: 30000, cash: 15000 },
  { name: 'Apr', revenue: 58000, expense: 36000, cash: 22000 },
  { name: 'May', revenue: 52000, expense: 34000, cash: 18000 },
  { name: 'Jun', revenue: 64000, expense: 38000, cash: 26000 },
];

const marketingData = [
  { name: 'Instagram', value: 45, color: '#32d74b' },
  { name: 'Google', value: 25, color: '#0a84ff' },
  { name: 'Referral', value: 20, color: '#ff9f0a' },
  { name: 'Other', value: 10, color: '#636366' },
];

const topTeachers = [
  { name: 'Sarah Jenkins', role: 'Mathematics', revenue: 14200, students: 48, rating: 4.9 },
  { name: 'Michael Chen', role: 'Physics', revenue: 12800, students: 42, rating: 4.8 },
  { name: 'Emma Wilson', role: 'English', revenue: 11500, students: 56, rating: 4.7 },
  { name: 'David Miller', role: 'Chemistry', revenue: 9800, students: 34, rating: 4.6 },
];

const groupPerformance = [
  { name: 'Calculus Advanced', students: '12/15', revenue: '$4,200', status: 'Profitable' },
  { name: 'IELTS Intensive', students: '18/20', revenue: '$5,800', status: 'Profitable' },
  { name: 'Physics Basic', students: '6/12', revenue: '$1,800', status: 'At Risk' },
  { name: 'SAT Prep', students: '14/15', revenue: '$4,500', status: 'Profitable' },
];

export default function App() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedRange, setSelectedRange] = useState('Last 6 Months');

  return (
    <div className="flex min-h-screen bg-app-bg transition-colors duration-500">
      <Sidebar 
        isCollapsed={isSidebarCollapsed} 
        onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)} 
      />

      {/* Mobile Menu Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 lg:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <motion.div 
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              className="w-64 h-full bg-app-surface p-6"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex justify-between items-center mb-8">
                <span className="font-bold text-xl text-text-primary">Lumina</span>
                <button onClick={() => setIsMobileMenuOpen(false)}><X size={20} /></button>
              </div>
              <nav className="space-y-4">
                <div className="p-3 bg-app-bg rounded-apple font-medium">Overview</div>
                <div className="p-3 text-text-secondary">Finance</div>
                <div className="p-3 text-text-secondary">Marketing</div>
                <div className="p-3 text-text-secondary">Groups</div>
              </nav>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-16 border-b border-app-divider flex items-center justify-between px-6 lg:px-10 bg-app-surface/80 backdrop-blur-xl sticky top-0 z-40">
          <div className="flex items-center gap-4">
            <button 
              className="lg:hidden p-2 hover:bg-app-bg rounded-apple"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <Menu size={20} />
            </button>
            <div className="flex items-center gap-2 text-text-secondary text-sm font-medium">
              <span>Dashboard</span>
              <span className="text-text-tertiary">/</span>
              <span className="text-text-primary">Overview</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button className="p-2 hover:bg-app-bg rounded-apple text-text-secondary relative transition-all">
              <Bell size={18} />
              <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-accent-red rounded-full border border-app-surface"></span>
            </button>
            <button className="apple-button-primary flex items-center gap-2">
              <Download size={16} />
              <span className="hidden sm:inline">Export Report</span>
            </button>
          </div>
        </header>

        {/* Content */}
        <div className="p-6 lg:p-10 space-y-10 max-w-[1600px] mx-auto w-full">
          {/* Top Section: Title & Filters */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
            <div>
              <h1 className="text-3xl font-bold text-text-primary tracking-tight">Executive Summary</h1>
              <p className="text-text-secondary mt-1">Real-time performance metrics for Lumina Academy.</p>
            </div>
            
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-3 bg-app-surface p-1 rounded-full border border-app-border shadow-sm">
                {['Today', 'Week', 'Month', 'Year'].map((range) => (
                  <button 
                    key={range}
                    onClick={() => setSelectedRange(range)}
                    className={cn(
                      "px-5 py-1.5 rounded-full text-[13px] font-medium transition-all",
                      selectedRange === range ? "bg-text-primary text-white shadow-md" : "text-text-secondary hover:text-text-primary"
                    )}
                  >
                    {range}
                  </button>
                ))}
              </div>
              
              <div className="h-8 w-[1px] bg-app-divider mx-1 hidden md:block"></div>

              <button className="flex items-center gap-2 px-4 py-2 bg-app-surface border border-app-border rounded-full text-[13px] font-medium text-text-secondary hover:text-text-primary transition-all">
                <Filter size={14} />
                <span>Filters</span>
                <ChevronDown size={14} />
              </button>
            </div>
          </div>

          {/* KPI Strip */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <KPICard 
              title="Total Revenue" 
              value={154200} 
              isCurrency 
              change={12.5} 
              color="emerald"
              data={[{value: 30}, {value: 45}, {value: 35}, {value: 60}, {value: 50}, {value: 75}]}
            />
            <KPICard 
              title="Net Profit" 
              value={68400} 
              isCurrency 
              change={8.2} 
              color="blue"
              data={[{value: 20}, {value: 30}, {value: 25}, {value: 40}, {value: 35}, {value: 50}]}
            />
            <KPICard 
              title="Active Students" 
              value={1240} 
              change={5.4} 
              color="amber"
              data={[{value: 80}, {value: 85}, {value: 82}, {value: 90}, {value: 88}, {value: 95}]}
            />
            <KPICard 
              title="Conversion Rate" 
              value={24.8} 
              change={-2.1} 
              color="red"
              data={[{value: 28}, {value: 26}, {value: 27}, {value: 24}, {value: 25}, {value: 24}]}
            />
          </div>

          {/* Main Analytics Grid */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Finance Chart */}
            <DataCard 
              className="xl:col-span-2"
              title="Financial Performance" 
              subtitle="Revenue vs Expenses trend over the last 6 months"
              headerAction={
                <button className="flex items-center gap-1 text-[13px] font-medium text-text-secondary hover:text-text-primary">
                  Details <ArrowUpRight size={14} />
                </button>
              }
            >
              <div className="h-[380px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={revenueTrend}>
                    <defs>
                      <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#32d74b" stopOpacity={0.2}/>
                        <stop offset="95%" stopColor="#32d74b" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2c2c2e" vertical={false} />
                    <XAxis 
                      dataKey="name" 
                      stroke="#8e8e93" 
                      fontSize={12} 
                      tickLine={false} 
                      axisLine={false} 
                      dy={10}
                    />
                    <YAxis 
                      stroke="#8e8e93" 
                      fontSize={12} 
                      tickLine={false} 
                      axisLine={false} 
                      tickFormatter={(val) => `$${val / 1000}k`}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#1c1c1e', border: '1px solid #2c2c2e', borderRadius: '12px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}
                      itemStyle={{ fontSize: '12px', fontWeight: '600', color: '#ffffff' }}
                    />
                    <Area type="monotone" dataKey="revenue" stroke="#32d74b" strokeWidth={3} fillOpacity={1} fill="url(#colorRev)" />
                    <Area type="monotone" dataKey="expense" stroke="#8e8e93" strokeWidth={2} strokeDasharray="5 5" fill="none" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </DataCard>

            {/* Executive Insights */}
            <div className="flex flex-col gap-6">
              <div className="apple-card p-8 flex-1 flex flex-col">
                <div className="flex items-center gap-3 mb-8">
                  <div className="p-2 rounded-apple bg-text-primary text-white">
                    <BrainCircuit size={20} />
                  </div>
                  <h2 className="text-lg font-bold">Executive Insights</h2>
                </div>
                
                <div className="space-y-4 flex-1">
                  <InsightCard 
                    type="positive" 
                    title="Revenue Growth" 
                    description="Revenue is up 12% this month, primarily driven by Advanced Calculus enrollments."
                  />
                  <InsightCard 
                    type="warning" 
                    title="Retention Alert" 
                    description="Student activity in 'Physics Basic' has dropped by 15%. Intervention recommended."
                  />
                  <InsightCard 
                    type="info" 
                    title="Marketing Efficiency" 
                    description="Instagram leads are converting at 24%, outperforming Google Ads by 8%."
                  />
                </div>

                <button className="mt-8 w-full py-3 rounded-apple bg-app-bg text-text-primary text-sm font-bold hover:bg-app-border transition-all flex items-center justify-center gap-2">
                  View All Signals <ArrowRight size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Secondary Analytics Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-8">
            {/* Marketing */}
            <DataCard title="Lead Sources" subtitle="Distribution of new student inquiries">
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={marketingData}
                      cx="50%"
                      cy="50%"
                      innerRadius={70}
                      outerRadius={90}
                      paddingAngle={8}
                      dataKey="value"
                    >
                      {marketingData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend verticalAlign="bottom" height={36} iconType="circle" />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </DataCard>

            {/* Top Teachers */}
            <DataCard 
              className="xl:col-span-2"
              title="Top Performing Teachers" 
              subtitle="Ranked by student satisfaction and revenue"
              headerAction={<button className="text-accent-blue text-sm font-medium hover:underline">View All</button>}
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="text-[11px] font-bold text-text-tertiary uppercase tracking-widest border-b border-app-divider">
                      <th className="pb-4">Teacher</th>
                      <th className="pb-4">Subject</th>
                      <th className="pb-4">Students</th>
                      <th className="pb-4">Revenue</th>
                      <th className="pb-4 text-right">Rating</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-app-divider">
                    {topTeachers.map((teacher, idx) => (
                      <tr key={idx} className="group hover:bg-app-bg/30 transition-all">
                        <td className="py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-app-bg border border-app-border flex items-center justify-center text-[11px] font-bold">
                              {teacher.name.split(' ').map(n => n[0]).join('')}
                            </div>
                            <span className="text-[14px] font-bold text-text-primary">{teacher.name}</span>
                          </div>
                        </td>
                        <td className="py-4 text-[13px] text-text-secondary">{teacher.role}</td>
                        <td className="py-4 text-[13px] text-text-secondary">{teacher.students}</td>
                        <td className="py-4 text-[13px] font-bold text-accent-emerald">${teacher.revenue.toLocaleString()}</td>
                        <td className="py-4 text-right">
                          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-amber/10 text-accent-amber text-[12px] font-bold">
                            ★ {teacher.rating}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </DataCard>
          </div>

          {/* Bottom Grid: Groups & Retention */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <DataCard className="lg:col-span-2" title="Group Performance" subtitle="Profitability and occupancy status">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {groupPerformance.map((group, idx) => (
                  <div key={idx} className="p-5 rounded-apple border border-app-border hover:border-text-primary/20 transition-all cursor-pointer group">
                    <div className="flex justify-between items-start mb-4">
                      <h4 className="font-bold text-[15px] text-text-primary">{group.name}</h4>
                      <span className={cn(
                        "text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider",
                        group.status === 'Profitable' ? "bg-accent-emerald/10 text-accent-emerald" : "bg-accent-red/10 text-accent-red"
                      )}>
                        {group.status}
                      </span>
                    </div>
                    <div className="flex justify-between items-end">
                      <div className="space-y-1">
                        <p className="text-[12px] text-text-secondary">Occupancy: <span className="text-text-primary font-bold">{group.students}</span></p>
                        <p className="text-[12px] text-text-secondary">Revenue: <span className="text-accent-emerald font-bold">{group.revenue}</span></p>
                      </div>
                      <div className="w-8 h-8 rounded-full bg-app-bg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <ArrowRight size={14} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </DataCard>

            <DataCard title="Retention Risk" subtitle="Students requiring immediate attention">
              <div className="space-y-6">
                {[
                  { name: 'James Wilson', risk: 88, status: 'High' },
                  { name: 'Linda Garcia', risk: 65, status: 'Medium' },
                  { name: 'Robert Chen', risk: 42, status: 'Low' },
                ].map((student, idx) => (
                  <div key={idx} className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-app-bg border border-app-border flex items-center justify-center text-[11px] font-bold">
                      {student.name.split(' ').map(n => n[0]).join('')}
                    </div>
                    <div className="flex-1">
                      <p className="text-[14px] font-bold text-text-primary">{student.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <div className="flex-1 h-1 bg-app-divider rounded-full overflow-hidden">
                          <div 
                            className={cn(
                              "h-full rounded-full",
                              student.status === 'High' ? "bg-accent-red" : student.status === 'Medium' ? "bg-accent-amber" : "bg-accent-emerald"
                            )}
                            style={{ width: `${student.risk}%` }}
                          ></div>
                        </div>
                        <span className="text-[11px] font-bold text-text-secondary">{student.risk}%</span>
                      </div>
                    </div>
                  </div>
                ))}
                <button className="w-full py-2.5 mt-2 rounded-apple border border-app-border text-text-secondary text-[13px] font-bold hover:bg-app-bg transition-all">
                  View Retention Report
                </button>
              </div>
            </DataCard>
          </div>
        </div>
      </main>
    </div>
  );
}
