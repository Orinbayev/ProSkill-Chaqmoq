/**
 * ChaqmoqApp — Direktor Paneli (Premium Rebuild v3)
 * React 19 · TypeScript · Tailwind v4 · Recharts v3
 * 100% fresh — zero legacy code
 */
import React, { useState, useCallback, useMemo } from 'react';
import {
  DollarSign, TrendingUp, TrendingDown, Users,
  Percent, Activity
} from 'lucide-react';

import { Sidebar }       from './components/Sidebar';
import { Header }        from './components/Header';
import { KPICard }       from './components/KPICard';
import { KPIModal }      from './components/KPIModal';
import { RevenueChart }  from './components/RevenueChart';
import { PaymentStatus } from './components/PaymentStatus';
import { TeacherBoard }  from './components/TeacherBoard';
import { GroupsTable }   from './components/GroupsTable';
import { FunnelViz }     from './components/FunnelViz';
import { GoalTracker }   from './components/GoalTracker';

import { mockData, formatUZS, type Period } from './data/mockData';
import type { KPICardDef } from './components/KPICard';

export default function App() {
  const [navActive, setNavActive]   = useState('dashboard');
  const [period, setPeriod]         = useState<Period>('bu_oy');
  const [modalCard, setModalCard]   = useState<KPICardDef | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const data = mockData[period];
  const { kpi, daily, payment, teachers, groups, funnel, goals } = data;

  const handleRefresh = useCallback(() => setRefreshKey(k => k + 1), []);
  const handlePeriod  = useCallback((p: Period) => setPeriod(p), []);
  const handleNav     = useCallback((id: string) => setNavActive(id), []);

  /* ── KPI card definitions ─────────────────────────────────────────────── */
  const kpiCards: KPICardDef[] = useMemo(() => [
    {
      id: 'daromad',
      label: 'Daromad',
      value: formatUZS(kpi.daromad),
      delta: kpi.daromadDelta,
      color: '#22d3ee',
      glowColor: 'rgba(34,211,238,0.12)',
      sparkClass: 'sparkline-cyan',
      dataKey: 'daromad',
      icon: <DollarSign size={16} style={{ color: '#22d3ee' }} />,
    },
    {
      id: 'foyda',
      label: 'Foyda',
      value: formatUZS(kpi.foyda),
      subLabel: `Marja ${kpi.marja}%`,
      delta: kpi.foydaDelta,
      color: '#34d399',
      glowColor: 'rgba(52,211,153,0.12)',
      sparkClass: 'sparkline-green',
      dataKey: 'foyda',
      icon: <TrendingUp size={16} style={{ color: '#34d399' }} />,
    },
    {
      id: 'xarajat',
      label: 'Xarajat',
      value: formatUZS(kpi.xarajat),
      delta: kpi.xarajatDelta,
      color: '#f43f5e',
      glowColor: 'rgba(244,63,94,0.12)',
      sparkClass: 'sparkline-red',
      dataKey: 'xarajat',
      icon: <TrendingDown size={16} style={{ color: '#f43f5e' }} />,
    },
    {
      id: 'qarz',
      label: 'Qarz',
      value: formatUZS(kpi.qarz),
      delta: kpi.qarzDelta,
      color: '#f59e0b',
      glowColor: 'rgba(245,158,11,0.12)',
      sparkClass: 'sparkline-amber',
      dataKey: 'qarz',
      icon: <Activity size={16} style={{ color: '#f59e0b' }} />,
    },
    {
      id: 'faol',
      label: "Faol o'quvchi",
      value: `${kpi.faolOquvchi} kishi`,
      delta: kpi.faolOquvchiDelta,
      color: '#818cf8',
      glowColor: 'rgba(129,140,248,0.12)',
      sparkClass: 'sparkline-purple',
      dataKey: 'foyda',
      icon: <Users size={16} style={{ color: '#818cf8' }} />,
    },
    {
      id: 'konversiya',
      label: 'Konversiya',
      value: `${kpi.konversiya}%`,
      delta: kpi.konversiyaDelta,
      color: '#22d3ee',
      glowColor: 'rgba(34,211,238,0.08)',
      sparkClass: 'sparkline-cyan',
      dataKey: 'daromad',
      icon: <Percent size={16} style={{ color: '#22d3ee' }} />,
    },
  ], [kpi]);

  return (
    <div style={{ minHeight: '100vh', background: '#050507' }}>

      {/* Ambient glow layer */}
      <div className="ambient-bg" aria-hidden>
        <div className="ambient-emerald" />
      </div>

      {/* Sidebar */}
      <Sidebar active={navActive} onNav={handleNav} />

      {/* Top header */}
      <Header period={period} onPeriodChange={handlePeriod} onRefresh={handleRefresh} />

      {/* Main scrollable area */}
      <main
        key={refreshKey}
        style={{ marginLeft: 64, paddingTop: 64, minHeight: '100vh', position: 'relative', zIndex: 1 }}
      >
        <div style={{ maxWidth: 1560, margin: '0 auto', padding: '24px 20px 40px' }}>

          {/* ── Section: KPI Overview ─────────────────────────────────────── */}
          <div className="mb-6">
            <div className="flex items-center gap-3 mb-4">
              <div style={{ width: 3, height: 18, borderRadius: 2, background: 'linear-gradient(180deg, #22d3ee, #818cf8)' }} />
              <span className="section-label">UMUMIY HOLAT</span>
              <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.22)' }}>— Asosiy ko'rsatkichlar</span>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(6, minmax(0, 1fr))',
                gap: 12,
              }}
            >
              {kpiCards.map((card, i) => (
                <KPICard
                  key={`${card.id}-${period}`}
                  card={card}
                  daily={daily}
                  onClick={() => setModalCard(card)}
                  index={i}
                />
              ))}
            </div>
          </div>

          {/* ── Section: Revenue chart + Payment status ───────────────────── */}
          <div
            className="mb-5"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 340px',
              gap: 12,
              alignItems: 'stretch',
            }}
          >
            <div style={{ minHeight: 360 }}>
              <RevenueChart data={daily} />
            </div>
            <div style={{ minHeight: 360 }}>
              <PaymentStatus data={payment} />
            </div>
          </div>

          {/* ── Section: Funnel + Goals ───────────────────────────────────── */}
          <div
            className="mb-5"
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 12,
            }}
          >
            <FunnelViz stages={funnel} />
            <GoalTracker goals={goals} />
          </div>

          {/* ── Section: Teacher board ────────────────────────────────────── */}
          <div className="mb-5">
            <TeacherBoard teachers={teachers} />
          </div>

          {/* ── Section: Groups table ─────────────────────────────────────── */}
          <div>
            <GroupsTable groups={groups} />
          </div>

        </div>
      </main>

      {/* KPI Detail Modal */}
      {modalCard && (
        <KPIModal
          card={modalCard}
          daily={daily}
          onClose={() => setModalCard(null)}
        />
      )}

    </div>
  );
}
