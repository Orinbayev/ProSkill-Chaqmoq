import React from 'react';
import { Star, Users, BookOpen } from 'lucide-react';
import type { TeacherRow } from '../data/mockData';
import { formatUZS } from '../data/mockData';

interface TeacherBoardProps { teachers: TeacherRow[]; }

const AV_COLORS = [
  { bg: '#22d3ee', fg: '#050507' },
  { bg: '#818cf8', fg: '#050507' },
  { bg: '#34d399', fg: '#050507' },
  { bg: '#f59e0b', fg: '#050507' },
  { bg: '#f43f5e', fg: '#fff'    },
];
const initials = (n: string) => n.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

function MarjaBar({ v }: { v: number }) {
  const c = v >= 80 ? '#34d399' : v >= 70 ? '#22d3ee' : '#f59e0b';
  return (
    <div className="flex items-center gap-2">
      <div className="progress-track flex-1" style={{ height: 4 }}>
        <div className="progress-fill" style={{ width: `${v}%`, background: c, boxShadow: `0 0 6px ${c}60` }} />
      </div>
      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: c, minWidth: 36, textAlign: 'right' }}>{v}%</span>
    </div>
  );
}

export function TeacherBoard({ teachers }: TeacherBoardProps) {
  const sorted = [...teachers].sort((a, b) => b.daromad - a.daromad);
  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="section-label">USTOZLAR</p>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>Samaradorlik reytingi</h3>
        </div>
        <span className="chip chip-cyan">{teachers.length} ustoz</span>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table w-full">
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>#</th>
              <th style={{ textAlign: 'left' }}>Ustoz</th>
              <th style={{ textAlign: 'center' }}><div className="flex items-center justify-center gap-1"><BookOpen size={10}/>Guruh</div></th>
              <th style={{ textAlign: 'center' }}><div className="flex items-center justify-center gap-1"><Users size={10}/>O'q.</div></th>
              <th style={{ textAlign: 'right' }}>Daromad</th>
              <th style={{ textAlign: 'left', minWidth: 120 }}>Marja</th>
              <th style={{ textAlign: 'center' }}><div className="flex items-center justify-center gap-1"><Star size={10}/>Baho</div></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const av = AV_COLORS[i % AV_COLORS.length];
              return (
                <tr key={t.id}>
                  <td>
                    {i === 0
                      ? <span style={{ fontSize: '0.8rem' }}>🥇</span>
                      : <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: '0.75rem' }}>{i + 1}</span>}
                  </td>
                  <td>
                    <div className="flex items-center gap-2.5">
                      <div className="flex items-center justify-center rounded-full font-bold flex-shrink-0"
                        style={{ width: 30, height: 30, background: av.bg, color: av.fg, fontSize: '0.62rem' }}>
                        {initials(t.ism)}
                      </div>
                      <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.8rem', whiteSpace: 'nowrap' }}>{t.ism}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'center', color: '#818cf8', fontWeight: 700, fontSize: '0.82rem' }}>{t.guruhlar}</td>
                  <td style={{ textAlign: 'center', color: '#22d3ee', fontWeight: 700, fontSize: '0.82rem' }}>{t.oquvchilar}</td>
                  <td style={{ textAlign: 'right', fontWeight: 700, fontSize: '0.82rem', color: '#f1f5f9', whiteSpace: 'nowrap' }}>{formatUZS(t.daromad)}</td>
                  <td style={{ minWidth: 120 }}><MarjaBar v={t.marja} /></td>
                  <td style={{ textAlign: 'center' }}>
                    <div className="flex items-center justify-center gap-1">
                      <Star size={11} style={{ color: '#f59e0b', fill: '#f59e0b' }} />
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f1f5f9' }}>{t.baho}</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
