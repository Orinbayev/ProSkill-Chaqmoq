import React from "react";
import { motion } from "motion/react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowUpRight,
  ArrowDownRight,
  Search,
  Calendar,
  Bell,
  MoreHorizontal,
  TrendingUp,
  Users,
  CreditCard,
  AlertTriangle,
  FileText,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";

// --- Mock Data ---

const incomeData = [
  { name: "Mon", value: 400 },
  { name: "Tue", value: 300 },
  { name: "Wed", value: 550 },
  { name: "Thu", value: 450 },
  { name: "Fri", value: 600 },
  { name: "Sat", value: 700 },
  { name: "Sun", value: 850 },
];

const expenseData = [
  { name: "Mon", value: 200 },
  { name: "Tue", value: 150 },
  { name: "Wed", value: 300 },
  { name: "Thu", value: 250 },
  { name: "Fri", value: 350 },
  { name: "Sat", value: 400 },
  { name: "Sun", value: 380 },
];

const profitData = [
  { name: "Mon", value: 200 },
  { name: "Tue", value: 250 },
  { name: "Wed", value: 350 },
  { name: "Thu", value: 400 },
  { name: "Fri", value: 450 },
  { name: "Sat", value: 500 },
  { name: "Sun", value: 600 },
];

const studentActivityData = [
  { name: "Jam", value: 120 },
  { name: "Jyn", value: 150 },
  { name: "Aror", value: 180 },
  { name: "Avg", value: 220 },
  { name: "Jun", value: 300 },
  { name: "Sen", value: 250 },
  { name: "Oct", value: 280 },
  { name: "Nov", value: 320 },
];

const marketingData = [
  { name: "Telegram", value: 340, color: "#FACC15" }, // Yellow-400
  { name: "Instagram", value: 200, color: "#EAB308" }, // Yellow-500
  { name: "Tavsiyalar", value: 150, color: "#CA8A04" }, // Yellow-600
  { name: "Reklama", value: 120, color: "#A16207" }, // Yellow-700
];

const studentsList = [
  { name: "Bekzod Rashidov", course: "Dizayn | UX/UI", status: -56, img: "https://picsum.photos/seed/u1/40/40" },
  { name: "Dilmurod Yunusov", course: "Frontend - React", status: -47, img: "https://picsum.photos/seed/u2/40/40" },
  { name: "Kamola Alimova", course: "Backend - Python", status: -43, img: "https://picsum.photos/seed/u3/40/40" },
];

const teachersList = [
  { name: "Ali Akbarov", role: "Frontend", groups: 6, students: 165, rating: 4.9, img: "https://picsum.photos/seed/t1/40/40" },
  { name: "Dilnoza Xudoyberdiyeva", role: "Backend", groups: 5, students: 145, rating: 4.9, img: "https://picsum.photos/seed/t2/40/40" },
  { name: "Azamat Qudratov", role: "Mobile", groups: 3, students: 115, rating: 4.7, img: "https://picsum.photos/seed/t3/40/40" },
];

// --- Components ---

const Card = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <motion.div 
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4 }}
    className={cn(
      "bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg relative overflow-hidden group",
      "hover:shadow-[0_0_20px_rgba(250,204,21,0.1)] hover:border-yellow-500/30 transition-all duration-300",
      className
    )}
  >
    {children}
  </motion.div>
);

const SectionTitle = ({ children }: { children: React.ReactNode }) => (
  <h3 className="text-slate-400 text-sm font-medium mb-4 uppercase tracking-wider flex items-center gap-2">
    <span className="w-1 h-4 bg-yellow-500 rounded-full inline-block"></span>
    {children}
  </h3>
);

const StatCard = ({
  title,
  value,
  trend,
  trendUp,
  data,
  color = "#FACC15",
}: {
  title: string;
  value: string;
  trend?: string;
  trendUp?: boolean;
  data: any[];
  color?: string;
}) => (
  <Card className="relative overflow-hidden group hover:border-yellow-500/30 transition-colors">
    <div className="flex justify-between items-start mb-2">
      <div>
        <h4 className="text-slate-400 text-sm font-medium">{title}</h4>
        <div className="text-2xl font-bold text-white mt-1">{value}</div>
      </div>
      {trend && (
        <div className={cn("flex items-center text-sm font-medium", trendUp ? "text-emerald-400" : "text-rose-400")}>
          {trendUp ? <ArrowUpRight size={16} className="mr-1" /> : <ArrowDownRight size={16} className="mr-1" />}
          {trend}
        </div>
      )}
    </div>
    <div className="h-16 w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#gradient-${title})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  </Card>
);

const MetricCard = ({
  title,
  value,
  subtext,
  chartType = "bar",
}: {
  title: string;
  value: string;
  subtext?: string;
  chartType?: "bar" | "line" | "gauge";
}) => (
  <Card className="flex flex-col justify-between h-full hover:border-yellow-500/30 transition-colors">
    <div>
      <h4 className="text-slate-400 text-sm font-medium mb-1">{title}</h4>
      <div className="text-2xl font-bold text-white">{value}</div>
      {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
    </div>
    <div className="h-12 mt-4 flex items-end gap-1">
      {chartType === "bar" &&
        [40, 60, 45, 70, 50, 80, 60, 90].map((h, i) => (
          <div
            key={i}
            className="w-full bg-yellow-500/20 rounded-sm hover:bg-yellow-400 transition-colors"
            style={{ height: `${h}%` }}
          />
        ))}
      {chartType === "line" && (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={incomeData}>
            <Area type="monotone" dataKey="value" stroke="#FACC15" fill="none" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      )}
      {chartType === "gauge" && (
        <div className="w-full flex items-center justify-between">
            <div className="text-xs text-slate-400">Reja bajarilishi</div>
            <div className="text-xl font-bold text-yellow-400">92%</div>
            <div className="h-2 w-24 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-yellow-400 w-[92%]"></div>
            </div>
        </div>
      )}
    </div>
  </Card>
);

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-[#0B1121] p-6 font-sans text-slate-200">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
        <h1 className="text-3xl font-bold text-white tracking-tight">Statistika</h1>
        
        <div className="flex items-center gap-3 bg-slate-900/50 p-1.5 rounded-xl border border-slate-800/50 backdrop-blur-sm">
          <div className="relative">
            <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg text-sm font-medium hover:bg-slate-700 transition-colors">
              Oylik <ChevronDown size={14} />
            </button>
          </div>
          
          <div className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg text-sm text-slate-400">
            <Calendar size={14} />
            <span>2024-04-01 - 2024-04-23</span>
          </div>

          <button className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-yellow-400 transition-colors">
            <FileText size={20} />
          </button>
          <button className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-yellow-400 transition-colors">
            <Search size={20} />
          </button>
        </div>
      </header>

      <div className="grid grid-cols-12 gap-6">
        {/* Left Main Column */}
        <div className="col-span-12 lg:col-span-9 flex flex-col gap-6">
          
          {/* Top KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <StatCard
              title="Jami Daromad"
              value="$1,250,500"
              data={incomeData}
              color="#FACC15" // Yellow
            />
            <StatCard
              title="Xarajatlar"
              value="$530,000"
              data={expenseData}
              color="#F97316" // Orange
            />
            <StatCard
              title="Sof Foyda"
              value="+720,500"
              trend="15.8%"
              trendUp={true}
              data={profitData}
              color="#10B981" // Emerald
            />
          </div>

          {/* Secondary Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <MetricCard title="Qarzdorlik" value="$195" chartType="bar" />
            <MetricCard title="Talabalar soni" value="110,000" subtext="Talabalar soni (o'sish)" chartType="line" />
            <MetricCard title="Reja Bajarilishi" value="118" chartType="gauge" />
          </div>

          {/* Middle Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Financial Stats Table */}
            <Card className="lg:col-span-5">
              <SectionTitle>Moliyaviy Statistika</SectionTitle>
              <div className="space-y-4">
                <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg border border-slate-800">
                  <span className="text-slate-400 text-sm">Oylik to'lov</span>
                  <div className="text-right">
                    <div className="text-yellow-400 font-bold">$25K</div>
                    <div className="text-xs text-slate-500">Kutilayotgan</div>
                  </div>
                  <div className="text-right">
                    <div className="text-white font-bold">$150K</div>
                    <div className="text-xs text-slate-500">Tushgan</div>
                  </div>
                </div>
                
                <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded-lg border border-slate-800">
                  <span className="text-slate-400 text-sm">Qarzdorlik</span>
                  <div className="text-right">
                    <div className="text-rose-400 font-bold">$10K</div>
                    <div className="text-xs text-slate-500">Joriy oy</div>
                  </div>
                  <div className="text-right">
                    <div className="text-emerald-400 font-bold">$95</div>
                    <div className="text-xs text-slate-500">To'langan</div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="bg-slate-800/30 p-3 rounded-lg text-center">
                        <div className="text-xs text-slate-500 mb-1">Qarzdor Talabalar</div>
                        <div className="text-xl font-bold text-yellow-400">215</div>
                    </div>
                    <div className="bg-slate-800/30 p-3 rounded-lg text-center">
                        <div className="text-xs text-slate-500 mb-1">O'rtacha To'lov</div>
                        <div className="text-xl font-bold text-white">$450</div>
                    </div>
                </div>
              </div>
            </Card>

            {/* Student Statistics Chart */}
            <Card className="lg:col-span-7">
              <div className="flex justify-between items-center mb-4">
                <SectionTitle>Talabalar Statistika</SectionTitle>
                <div className="flex gap-2">
                    <span className="text-xs bg-slate-800 px-2 py-1 rounded text-slate-400">Yillik</span>
                </div>
              </div>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={studentActivityData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip 
                        contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                        cursor={{ fill: '#334155', opacity: 0.2 }}
                    />
                    <Bar dataKey="value" fill="#FACC15" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="flex justify-between items-center mt-4 pt-4 border-t border-slate-800">
                <div>
                    <div className="text-xs text-slate-500">Jami Talabalar</div>
                    <div className="text-2xl font-bold text-white">345</div>
                </div>
                <div className="w-1/2">
                    <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-400">O'sish sur'ati</span>
                        <span className="text-white">95%</span>
                    </div>
                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-yellow-600 to-yellow-400 w-[95%]"></div>
                    </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Bottom Lists */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Popular Courses */}
            <Card>
              <SectionTitle>Eng Mashhur Kurslar</SectionTitle>
              <div className="space-y-4">
                {teachersList.map((teacher, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 hover:bg-slate-800/50 rounded-lg transition-colors">
                    <img src={teacher.img} alt={teacher.name} className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-800" />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-white">{teacher.name}</div>
                      <div className="text-xs text-slate-500">{teacher.role}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-slate-400">{teacher.groups} guruhlar</div>
                      <div className="font-bold text-white">{teacher.students}</div>
                    </div>
                    <div className="flex text-yellow-400 gap-0.5">
                        {[...Array(3)].map((_, j) => <div key={j} className="w-1.5 h-1.5 rounded-full bg-yellow-400" />)}
                    </div>
                  </div>
                ))}
              </div>
            </Card>

             {/* Teachers Stats */}
             <Card>
              <SectionTitle>O'qituvchilar Statistika</SectionTitle>
              <div className="space-y-4">
                {teachersList.map((teacher, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 hover:bg-slate-800/50 rounded-lg transition-colors">
                    <img src={teacher.img} alt={teacher.name} className="w-10 h-10 rounded-full object-cover ring-2 ring-slate-800" />
                    <div className="flex-1">
                      <div className="text-sm font-medium text-white">{teacher.name}</div>
                      <div className="text-xs text-slate-500">{teacher.role}</div>
                    </div>
                     <div className="flex items-center gap-1 text-yellow-400 text-sm font-bold">
                        <span>★</span> {teacher.rating}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

        </div>

        {/* Right Sidebar */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
          
          {/* Low Activity Students */}
          <Card>
            <div className="flex justify-between items-center mb-4">
                <SectionTitle>Faollik Past Talabalar</SectionTitle>
                <MoreHorizontal size={16} className="text-slate-500" />
            </div>
            <div className="space-y-4">
              {studentsList.map((student, i) => (
                <div key={i} className="flex items-center gap-3">
                  <img src={student.img} alt={student.name} className="w-9 h-9 rounded-full object-cover" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-white truncate">{student.name}</div>
                    <div className="text-xs text-slate-500 truncate">{student.course}</div>
                  </div>
                  <div className="text-rose-400 text-sm font-medium">{student.status}%</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Marketing Stats */}
          <Card className="flex flex-col items-center">
            <SectionTitle>Marketing Statistika</SectionTitle>
            <div className="relative w-48 h-48 my-4">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={marketingData}
                            innerRadius={60}
                            outerRadius={80}
                            paddingAngle={5}
                            dataKey="value"
                            stroke="none"
                        >
                            {marketingData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Pie>
                    </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <div className="text-2xl font-bold text-white">340</div>
                    <div className="text-xs text-slate-500">Jami</div>
                </div>
            </div>
            
            <div className="w-full space-y-2 mt-2">
                <div className="flex justify-between items-center text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-300"></div>
                        <span className="text-slate-300">Telegram</span>
                    </div>
                    <span className="text-emerald-400 text-xs">↑ 42%</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                        <span className="text-slate-300">Instagram</span>
                    </div>
                    <span className="text-emerald-400 text-xs">↑ 24%</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-600"></div>
                        <span className="text-slate-300">Tavsiyalar</span>
                    </div>
                    <span className="text-emerald-400 text-xs">↑ 18%</span>
                </div>
                 <div className="flex justify-between items-center text-sm">
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-yellow-700"></div>
                        <span className="text-slate-300">Reklama</span>
                    </div>
                    <span className="text-emerald-400 text-xs">↑ 19%</span>
                </div>
            </div>
          </Card>

          {/* Risks & Warnings */}
          <Card>
            <SectionTitle>Risklar & Ogohlantirishlar</SectionTitle>
            <div className="space-y-4">
                <div className="flex gap-3 items-start">
                    <div className="mt-1 min-w-[20px] h-5 flex items-center justify-center rounded-full bg-rose-500/20 text-rose-500 text-xs font-bold">1</div>
                    <div>
                        <div className="flex justify-between">
                            <span className="text-sm text-white font-medium">Qarzdorlik ortgan</span>
                            <span className="text-rose-400 text-xs font-bold">-$29K</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">Qarzdorlik o'tgan oyga nisbatan oshdi.</p>
                    </div>
                </div>
                 <div className="flex gap-3 items-start">
                    <div className="mt-1 min-w-[20px] h-5 flex items-center justify-center rounded-full bg-orange-500/20 text-orange-500 text-xs font-bold">2</div>
                    <div>
                        <div className="flex justify-between">
                            <span className="text-sm text-white font-medium">Qarzdor Talabalar</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">27 nafar talaba to'lovni kechiktirdi.</p>
                    </div>
                </div>
                <div className="flex gap-3 items-start">
                    <div className="mt-1 min-w-[20px] h-5 flex items-center justify-center rounded-full bg-yellow-500/20 text-yellow-500 text-xs font-bold">3</div>
                    <div>
                        <div className="flex justify-between">
                            <span className="text-sm text-white font-medium">Ketish (92 oshgan)</span>
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">Tark etganlar soni ko'paydi.</p>
                    </div>
                </div>
            </div>
          </Card>

          {/* Forecast */}
          <div className="bg-gradient-to-r from-yellow-600 to-yellow-500 rounded-2xl p-5 shadow-lg text-slate-900">
            <div className="text-sm font-semibold opacity-80 mb-1">Prognoz</div>
            <div className="flex justify-between items-end">
                <div className="text-xs opacity-70">Kelgusi oy prognozi</div>
                <div className="text-3xl font-bold">$400K</div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
