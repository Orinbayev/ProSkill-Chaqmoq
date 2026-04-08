import React from 'react';
import type { FunnelStage } from '../data/mockData';

interface FunnelVizProps { stages: FunnelStage[]; }

export function FunnelViz({ stages }: FunnelVizProps) {
  const maxSon = stages[0]?.son ?? 1;
  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4">
      <div>
        <p className="section-label">SAVDO HUNARI</p>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>Konversiya voronkasi</h3>
      </div>
      <div className="flex flex-col gap-2">
        {stages.map((stage, i) => {
          const pct = (stage.son / maxSon) * 100;
          const isLast = i === stages.length - 1;
          return (
            <div key={stage.nom}>
              <div className="flex items-center gap-3">
                <div style={{ minWidth: 96, fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)', fontWeight: 500, textAlign: 'right' }}>
                  {stage.nom}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="rounded-lg flex items-center px-3"
                    style={{
                      width: `${pct}%`, height: 34,
                      background: `linear-gradient(90deg, ${stage.color}22, ${stage.color}14)`,
                      border: `1px solid ${stage.color}30`,
                      boxShadow: isLast ? `0 0 16px ${stage.color}30` : 'none',
                      transition: 'width 0.8s cubic-bezier(0.34,1.56,0.64,1)',
                    }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: stage.color, boxShadow: `0 0 8px ${stage.color}`, flexShrink: 0 }} />
                    <span style={{ marginLeft: 8, fontSize: '0.8rem', fontWeight: 700, color: stage.color }}>{stage.son}</span>
                    <span style={{ marginLeft: 4, fontSize: '0.65rem', color: `${stage.color}80` }}>kishi</span>
                  </div>
                </div>
                <div className="chip flex-shrink-0" style={{ background: `${stage.color}12`, color: stage.color, minWidth: 44, justifyContent: 'center' }}>
                  {stage.foiz}%
                </div>
              </div>
              {!isLast && (
                <div className="flex justify-start ml-24 my-0.5">
                  <svg width="12" height="10" viewBox="0 0 12 10" fill="none">
                    <path d="M6 0L6 7M3 4.5L6 7.5L9 4.5" stroke={stage.color} strokeOpacity="0.3" strokeWidth="1.2" strokeLinecap="round"/>
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {stages.length >= 2 && (
        <div className="rounded-xl p-3 flex items-center justify-between mt-1"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.4)' }}>
            Umumiy konversiya ({stages[0].nom} → {stages[stages.length - 1].nom})
          </span>
          <span style={{ fontSize: '0.9rem', fontWeight: 800, color: stages[stages.length - 1].color }}>
            {((stages[stages.length - 1].son / stages[0].son) * 100).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}
