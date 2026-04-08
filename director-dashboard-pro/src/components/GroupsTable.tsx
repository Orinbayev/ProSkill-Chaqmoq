import React from 'react';
import { Users } from 'lucide-react';
import type { GroupRow } from '../data/mockData';
import { formatUZS } from '../data/mockData';

interface GroupsTableProps { groups: GroupRow[]; }

const statusCfg = {
  aktiv:    { label: 'Aktiv',         cls: 'chip-green'  },
  toxtagan: { label: "To'xtatilgan",  cls: 'chip-red'    },
  yangi:    { label: 'Yangi',         cls: 'chip-cyan'   },
};
const bolimColors: Record<string, string> = { IT: '#22d3ee', Biznes: '#818cf8', Dizayn: '#f59e0b' };

export function GroupsTable({ groups }: GroupsTableProps) {
  const maxRev = Math.max(...groups.map(g => g.daromad));
  return (
    <div className="glass rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="section-label">GURUHLAR</p>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', marginTop: 2 }}>Barcha guruhlar</h3>
        </div>
        <span className="chip chip-purple">{groups.length} guruh</span>
      </div>
      <div className="overflow-x-auto">
        <table className="data-table w-full">
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Guruh nomi</th>
              <th style={{ textAlign: 'left' }}>Ustoz</th>
              <th style={{ textAlign: 'center' }}>Bo'lim</th>
              <th style={{ textAlign: 'center' }}><div className="flex items-center justify-center gap-1"><Users size={10}/>O'quvchi</div></th>
              <th style={{ textAlign: 'left', minWidth: 160 }}>Daromad</th>
              <th style={{ textAlign: 'center' }}>Holat</th>
            </tr>
          </thead>
          <tbody>
            {groups.map(g => {
              const sc = statusCfg[g.status];
              const bc = bolimColors[g.bolim] ?? '#cbd5e1';
              const pct = (g.daromad / maxRev) * 100;
              return (
                <tr key={g.id}>
                  <td><span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: '0.82rem' }}>{g.nom}</span></td>
                  <td><span style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.5)' }}>{g.ustoz}</span></td>
                  <td style={{ textAlign: 'center' }}>
                    <span className="chip" style={{ background: `${bc}14`, color: bc }}>{g.bolim}</span>
                  </td>
                  <td style={{ textAlign: 'center', fontWeight: 700, color: '#818cf8', fontSize: '0.82rem' }}>{g.oquvchilar}</td>
                  <td style={{ minWidth: 160 }}>
                    <div className="flex items-center gap-2">
                      <div className="progress-track flex-1" style={{ height: 4 }}>
                        <div className="progress-fill" style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #22d3ee, #818cf8)' }} />
                      </div>
                      <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#e2e8f0', whiteSpace: 'nowrap', minWidth: 60 }}>
                        {formatUZS(g.daromad)}
                      </span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span className={`chip ${sc.cls}`}>{sc.label}</span>
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
