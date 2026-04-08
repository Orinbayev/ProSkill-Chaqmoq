import React, { useState } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import type { DailyPoint } from '../data/mockData';
import { formatCompact } from '../data/mockData';

interface RevenueChartProps { data: DailyPoint[]; }

const SERIES = [
  { key: 'daromad', label: 'Daromad', color: '#22d3ee', gradId: 'rc-daromad' },
  { key: 'xarajat', label: 'Xarajat', color: '#f43f5e', gradId: 'rc-xarajat' },
  { key: 'foyda',   label: 'Foyda',   color: '#34d399', gradId: 'rc-foyda'   },
  { key: 'qarz',    label: 'Qarz',    color: '#f59e0b', gradId: 'rc-qarz'    },
] as const;
type SeriesKey = 'daromad' | 'xarajat' | 'foyda' | 'qarz';

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; color: string; name: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(8,8,16,0.98)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 12, padding: '10px 14px',
      boxShadow: '0 12px 40px rgba(0,0,0,0.7)', minWidth: 160,
    }}>
      <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.4)', marginBottom: 8 }}>{label}-aprel</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center justify-between gap-6 mb-1">
          <div className="flex items-center gap-1.5">
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: p.color, flexShrink: 0 }} />
            <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.55)' }}>{p.name}</span>
          </div>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: p.color }}>{formatCompact(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

export function RevenueChart({ data }: RevenueChartProps) {
  const [visible, setVisible] = useState<Set<SeriesKey>>(new Set(['daromad', 'xarajat', 'foyda', 'qarz']));
  const toggle = (key: SeriesKey) => setVisible(prev => {
    const next = new Set(prev);
    if (next.has(key) && next.size === 1) return next;
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });

  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <p className="section-label">MOLIYA</p>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>Daromad va xarajat</h3>
        </div>
        <span style={{ fontSize: '0.7rem', color: '#22d3ee', fontWeight: 600, padding: '4px 10px',
          background: 'rgba(34,211,238,0.07)', border: '1px solid rgba(34,211,238,0.12)', borderRadius: 8 }}>
          7 kun
        </span>
      </div>

      {/* Legend / toggle buttons */}
      <div className="flex items-center gap-3 flex-wrap">
        {SERIES.map(({ key, label, color }) => {
          const on = visible.has(key);
          return (
            <button key={key} onClick={() => toggle(key)}
              className="flex items-center gap-2 rounded-lg px-3 py-1.5"
              style={{
                background: on ? `${color}12` : 'rgba(255,255,255,0.03)',
                border: `1px solid ${on ? color + '30' : 'rgba(255,255,255,0.06)'}`,
                opacity: on ? 1 : 0.4, transition: 'all 0.2s',
              }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
              <span style={{ fontSize: '0.72rem', fontWeight: 600, color: on ? color : 'rgba(255,255,255,0.4)' }}>{label}</span>
            </button>
          );
        })}
      </div>

      <div style={{ flex: 1, minHeight: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <defs>
              {SERIES.map(({ color, gradId }) => (
                <linearGradient key={gradId} id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.2} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="kun" tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.3)' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.25)' }} axisLine={false} tickLine={false} tickFormatter={v => formatCompact(v)} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.07)', strokeWidth: 1 }} />
            {SERIES.map(({ key, color, gradId, label }) =>
              visible.has(key) ? (
                <Area key={key} type="monotone" dataKey={key} name={label}
                  stroke={color} strokeWidth={2}
                  fill={`url(#${gradId})`}
                  dot={false}
                  activeDot={{ r: 4, fill: color, stroke: `${color}40`, strokeWidth: 3 }}
                />
              ) : null
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
