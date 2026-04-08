import React from 'react';
import { CheckCircle2, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import type { PaymentData } from '../data/mockData';
import { formatUZS } from '../data/mockData';

interface PaymentStatusProps { data: PaymentData; }

const RADIAN = Math.PI / 180;
function PieLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: {
  cx: number; cy: number; midAngle: number; innerRadius: number; outerRadius: number; percent: number;
}) {
  if (percent < 0.08) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return <text x={x} y={y} fill="rgba(255,255,255,0.75)" textAnchor="middle" dominantBaseline="central"
    style={{ fontSize: 10, fontWeight: 700 }}>{`${(percent * 100).toFixed(0)}%`}</text>;
}

function PieTip({ active, payload }: { active?: boolean; payload?: { name: string; value: number; payload: { color: string } }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'rgba(8,8,16,0.97)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 10, padding: '7px 12px', fontSize: '0.75rem', fontWeight: 700, color: payload[0].payload.color }}>
      {payload[0].name}: {payload[0].value}%
    </div>
  );
}

export function PaymentStatus({ data }: PaymentStatusProps) {
  const pieData = [
    { name: "To'landi",     value: data.completed, color: '#34d399' },
    { name: 'Kutilmoqda',   value: data.pending,   color: '#818cf8' },
    { name: "Muddati o'tgan", value: data.overdue, color: '#f43f5e' },
  ];
  const metrics = [
    { icon: CheckCircle2, color: '#34d399', label: "O'rtacha to'lov",  value: formatUZS(data.ortachaTolov)   },
    { icon: Clock,        color: '#818cf8', label: "To'lov bajarildi", value: formatUZS(data.tolovBajarildi) },
    { icon: AlertCircle,  color: '#22d3ee', label: 'Daromad sifati',   value: `${data.daromadSifati}%`       },
    { icon: RefreshCw,    color: '#f59e0b', label: "Qayta to'lov",     value: formatUZS(data.qaytaTolov)     },
  ];

  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4 h-full">
      <div>
        <p className="section-label">TO'LOVLAR</p>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>To'lov holati</h3>
      </div>

      <div className="flex items-center gap-4">
        <div style={{ width: 130, height: 130, flexShrink: 0, position: 'relative' }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={38} outerRadius={58}
                paddingAngle={3} dataKey="value" labelLine={false} label={PieLabel}
                startAngle={90} endAngle={-270}>
                {pieData.map(e => (
                  <Cell key={e.name} fill={e.color} opacity={0.9}
                    style={{ filter: `drop-shadow(0 0 4px ${e.color}60)` }} />
                ))}
              </Pie>
              <Tooltip content={<PieTip />} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', pointerEvents: 'none',
          }}>
            <span style={{ fontSize: '1.1rem', fontWeight: 800, color: '#34d399' }}>{data.completed}%</span>
            <span style={{ fontSize: '0.58rem', color: 'rgba(255,255,255,0.35)', marginTop: 1 }}>to'landi</span>
          </div>
        </div>

        <div className="flex flex-col gap-2.5 flex-1">
          {pieData.map(({ name, value, color }) => (
            <div key={name} className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0,
                  boxShadow: `0 0 6px ${color}` }} />
                <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)' }}>{name}</span>
              </div>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color }}>{value}%</span>
            </div>
          ))}
          <div className="mt-1">
            <div className="progress-track" style={{ height: 5 }}>
              <div className="progress-fill" style={{
                width: `${data.completed}%`,
                background: 'linear-gradient(90deg, #34d399, #22d3ee)',
                boxShadow: '0 0 8px rgba(34,211,153,0.4)',
              }} />
            </div>
          </div>
        </div>
      </div>

      <div style={{ height: 1, background: 'rgba(255,255,255,0.05)' }} />

      <div className="grid grid-cols-2 gap-3">
        {metrics.map(({ icon: Icon, color, label, value }) => (
          <div key={label} className="rounded-xl p-3"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div className="flex items-center gap-1.5 mb-2">
              <Icon size={12} style={{ color, opacity: 0.8 }} />
              <span style={{ fontSize: '0.63rem', color: 'rgba(255,255,255,0.35)', fontWeight: 600,
                textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#e2e8f0' }}>{value}</div>
          </div>
        ))}
      </div>

      <div className="rounded-xl p-3 flex items-center justify-between"
        style={{
          background: 'linear-gradient(135deg, rgba(34,211,238,0.07) 0%, rgba(129,140,248,0.07) 100%)',
          border: '1px solid rgba(34,211,238,0.12)',
        }}>
        <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.45)' }}>Jami to'lov hajmi</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 800, color: '#22d3ee' }}>{formatUZS(data.total)}</span>
      </div>
    </div>
  );
}
