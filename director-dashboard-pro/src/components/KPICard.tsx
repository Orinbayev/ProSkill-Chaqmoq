import React, { useCallback } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts';
import type { DailyPoint } from '../data/mockData';
import { formatCompact } from '../data/mockData';

export interface KPICardDef {
  id: string;
  label: string;
  value: string;
  subLabel?: string;
  delta: number;
  color: string;
  glowColor: string;
  sparkClass: string;
  dataKey: keyof DailyPoint;
  icon: React.ReactNode;
}

interface KPICardProps {
  card: KPICardDef;
  daily: DailyPoint[];
  onClick: () => void;
  index: number;
}

function SparkTooltip({ active, payload }: { active?: boolean; payload?: { value: number }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(10,10,18,0.95)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 8, padding: '5px 10px',
      fontSize: '0.7rem', color: '#e2e8f0',
    }}>
      {formatCompact(payload[0].value)}
    </div>
  );
}

export function KPICard({ card, daily, onClick, index }: KPICardProps) {
  const { label, value, subLabel, delta, color, glowColor, sparkClass, dataKey, icon } = card;
  const isPos = delta > 0;
  const isNeg = delta < 0;
  const deltaLabel = delta === 0 ? '0%' : `${isPos ? '+' : ''}${delta.toFixed(1)}%`;
  const deltaClass = isPos ? 'chip-green' : isNeg ? 'chip-red' : 'chip-amber';

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') onClick();
  }, [onClick]);

  return (
    <div
      className="glass glass-hover rounded-2xl p-4 flex flex-col gap-3 cursor-pointer fade-in"
      style={{
        animationDelay: `${index * 0.05}s`,
        animationFillMode: 'both',
        position: 'relative',
        overflow: 'hidden',
        minWidth: 0,
      }}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="button"
      aria-label={`${label} tafsilotlarini ko'rish`}
    >
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
        opacity: 0.6,
      }} />
      <div style={{
        position: 'absolute', top: -30, right: -30,
        width: 80, height: 80,
        background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center rounded-xl flex-shrink-0"
            style={{ width: 34, height: 34, background: `${color}18`, border: `1px solid ${color}28` }}>
            {icon}
          </div>
          <span style={{
            fontSize: '0.7rem', fontWeight: 600,
            color: 'rgba(255,255,255,0.5)',
            letterSpacing: '0.03em', textTransform: 'uppercase', lineHeight: 1.3,
          }}>
            {label}
          </span>
        </div>
        <span className={`chip ${deltaClass} flex-shrink-0`}>
          {isPos ? <TrendingUp size={10} /> : isNeg ? <TrendingDown size={10} /> : <Minus size={10} />}
          {deltaLabel}
        </span>
      </div>

      <div>
        <div className="font-bold tracking-tight"
          style={{ fontSize: '1.3rem', color: '#f1f5f9', lineHeight: 1.1 }}>
          {value}
        </div>
        {subLabel && (
          <div style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.38)', marginTop: 3 }}>
            {subLabel}
          </div>
        )}
      </div>

      <div className={`${sparkClass} mt-auto`} style={{ height: 44 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={daily} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id={`spark-${card.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <Tooltip content={<SparkTooltip />} />
            <Area type="monotone" dataKey={dataKey as string}
              stroke={color} strokeWidth={2}
              fill={`url(#spark-${card.id})`}
              dot={false}
              activeDot={{ r: 3, fill: color, stroke: 'none' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
