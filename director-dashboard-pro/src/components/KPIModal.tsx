import React, { useEffect, useRef } from 'react';
import { X, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts';
import type { DailyPoint } from '../data/mockData';
import { formatCompact } from '../data/mockData';
import type { KPICardDef } from './KPICard';

interface KPIModalProps {
  card: KPICardDef;
  daily: DailyPoint[];
  onClose: () => void;
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(8,8,16,0.98)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 10, padding: '8px 12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
    }}>
      <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.4)', marginBottom: 4 }}>Kun {label}</p>
      <p style={{ fontSize: '0.82rem', fontWeight: 700, color: payload[0].color }}>
        {formatCompact(payload[0].value)}
      </p>
    </div>
  );
}

export function KPIModal({ card, daily, onClose }: KPIModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handleKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const isPos = card.delta > 0;
  const isNeg = card.delta < 0;
  const deltaLabel = card.delta === 0 ? '0%' : `${isPos ? '+' : ''}${card.delta.toFixed(1)}%`;

  const vals = daily.map(d => d[card.dataKey] as number);
  const avg = vals.reduce((s, v) => s + v, 0) / vals.length;
  const max = Math.max(...vals);
  const min = Math.min(...vals);

  return (
    <div
      ref={overlayRef}
      className="modal-overlay fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div
        className="slide-up rounded-2xl w-full max-w-2xl"
        style={{
          background: 'rgba(10,10,18,0.98)',
          border: '1px solid rgba(255,255,255,0.09)',
          boxShadow: `0 0 0 1px rgba(255,255,255,0.04), 0 24px 80px rgba(0,0,0,0.8), 0 0 80px ${card.glowColor}`,
          overflow: 'hidden',
        }}
      >
        <div style={{ height: 2, background: `linear-gradient(90deg, transparent, ${card.color}, transparent)` }} />

        <div className="flex items-center justify-between px-6 pt-5 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center rounded-xl"
              style={{ width: 40, height: 40, background: `${card.color}18`, border: `1px solid ${card.color}28` }}>
              {card.icon}
            </div>
            <div>
              <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#f1f5f9' }}>{card.label}</h2>
              <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.35)' }}>So'nggi 7 kun statistikasi</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center rounded-xl"
            style={{
              width: 36, height: 36,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              color: 'rgba(255,255,255,0.4)',
              transition: 'all 0.2s', cursor: 'pointer',
            }}
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex items-end gap-4 px-6 pb-5">
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#f1f5f9', lineHeight: 1 }}>
            {card.value}
          </div>
          <div className={`chip mb-1 ${isPos ? 'chip-green' : isNeg ? 'chip-red' : 'chip-amber'}`}>
            {isPos ? <TrendingUp size={11} /> : isNeg ? <TrendingDown size={11} /> : <Minus size={11} />}
            {deltaLabel} o'tgan oyga nisbatan
          </div>
        </div>

        <div className="px-6 pb-5" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={daily} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="modal-area-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={card.color} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={card.color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(255,255,255,0.04)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="kun" tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.3)' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <ReferenceLine y={avg} stroke={card.color} strokeOpacity={0.3} strokeDasharray="4 4" />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: card.color, strokeOpacity: 0.3, strokeWidth: 1, strokeDasharray: '4 4' }} />
              <Area type="monotone" dataKey={card.dataKey as string}
                stroke={card.color} strokeWidth={2.5}
                fill="url(#modal-area-grad)"
                dot={{ r: 3, fill: card.color, strokeWidth: 0 }}
                activeDot={{ r: 5, fill: card.color, stroke: `${card.color}40`, strokeWidth: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="grid grid-cols-3 px-6 pb-6 gap-3">
          {[
            { label: "O'rtacha", value: formatCompact(avg), color: card.color },
            { label: 'Maksimum', value: formatCompact(max), color: '#34d399' },
            { label: 'Minimum',  value: formatCompact(min), color: '#f43f5e' },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl p-3 text-center"
              style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.35)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</p>
              <p style={{ fontSize: '1rem', fontWeight: 700, color }}>{value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
