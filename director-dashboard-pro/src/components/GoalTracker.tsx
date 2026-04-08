import React from 'react';
import { Target } from 'lucide-react';
import type { GoalItem } from '../data/mockData';
import { formatUZS } from '../data/mockData';

interface GoalTrackerProps { goals: GoalItem[]; }

function fmt(v: number, b: string) {
  if (b === 'UZS') return formatUZS(v);
  return `${v} ${b}`;
}
function getColor(p: number) {
  if (p >= 80) return '#34d399';
  if (p >= 50) return '#22d3ee';
  if (p >= 30) return '#f59e0b';
  return '#f43f5e';
}

export function GoalTracker({ goals }: GoalTrackerProps) {
  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="section-label">MAQSADLAR</p>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>Oylik maqsadlar</h3>
        </div>
        <div className="flex items-center justify-center rounded-xl"
          style={{ width: 32, height: 32, background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.2)' }}>
          <Target size={15} style={{ color: '#22d3ee' }} />
        </div>
      </div>
      <div className="flex flex-col gap-4">
        {goals.map(g => {
          const pct = Math.min((g.hozir / g.maqsad) * 100, 100);
          const color = getColor(pct);
          const done = pct >= 100;
          return (
            <div key={g.nom}>
              <div className="flex items-center justify-between mb-2">
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e8f0' }}>{g.nom}</span>
                <div className="flex items-center gap-1">
                  <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.4)' }}>{fmt(g.hozir, g.birlik)}</span>
                  <span style={{ fontSize: '0.7rem', color: 'rgba(255,255,255,0.2)' }}>/</span>
                  <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.28)' }}>{fmt(g.maqsad, g.birlik)}</span>
                </div>
              </div>
              <div className="progress-track" style={{ height: 7, borderRadius: 6 }}>
                <div className="progress-fill" style={{
                  width: `${pct}%`, borderRadius: 6,
                  background: done ? `linear-gradient(90deg, ${color}, #f1f5f9)` : `linear-gradient(90deg, ${color}cc, ${color})`,
                  boxShadow: `0 0 10px ${color}50`,
                }} />
              </div>
              <div className="flex items-center justify-between mt-1.5">
                <span style={{ fontSize: '0.68rem', color }}>{done ? '✓ Maqsadga yetildi' : `${pct.toFixed(0)}% bajarildi`}</span>
                {!done && <span style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.25)' }}>
                  Qoldi: {fmt(g.maqsad - g.hozir, g.birlik)}
                </span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
