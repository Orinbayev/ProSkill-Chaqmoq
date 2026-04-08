import React, { useState } from 'react';
import { RefreshCw, Download, ChevronDown, FileText, FileSpreadsheet, Image } from 'lucide-react';
import type { Period } from '../data/mockData';

interface HeaderProps {
  period: Period;
  onPeriodChange: (p: Period) => void;
  onRefresh: () => void;
}

export function Header({ period, onPeriodChange, onRefresh }: HeaderProps) {
  const [exportOpen, setExportOpen] = useState(false);

  const now = new Date();
  const timeStr = now.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = now.toLocaleDateString('uz-UZ', { day: '2-digit', month: '2-digit', year: 'numeric' });

  const handleExport = (type: string) => {
    setExportOpen(false);
    alert(`${type} formatida eksport qilinmoqda...`);
  };

  return (
    <header
      className="fixed top-0 right-0 z-20 flex items-center gap-3 px-5"
      style={{
        left: 64,
        height: 64,
        background: 'rgba(5,5,7,0.85)',
        borderBottom: '1px solid rgba(255,255,255,0.055)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
      }}
    >
      {/* Title block */}
      <div className="flex items-center gap-3 mr-auto">
        <div>
          <h1
            className="font-bold tracking-tight gradient-text-cyan"
            style={{ fontSize: '1.05rem', lineHeight: 1.2 }}
          >
            DIREKTOR PANELI
          </h1>
          <p style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.3)', marginTop: 1 }}>
            ChaqmoqApp CRM · {dateStr} · {timeStr}
          </p>
        </div>

        {/* Live dot */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: 'rgba(52,211,153,0.08)', border: '1px solid rgba(52,211,153,0.18)' }}>
          <span className="pulse-dot" style={{ background: '#34d399' }} />
          <span style={{ fontSize: '0.68rem', color: '#34d399', fontWeight: 600 }}>Jonli</span>
        </div>
      </div>

      {/* Period Toggle */}
      <div
        className="flex rounded-xl overflow-hidden"
        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', padding: 3 }}
      >
        {([
          { value: 'bu_oy',    label: 'Bu oy'      },
          { value: 'otgan_oy', label: "O'tgan oy" },
        ] as { value: Period; label: string }[]).map(({ value, label }) => (
          <button
            key={value}
            onClick={() => onPeriodChange(value)}
            style={{
              padding: '5px 14px',
              borderRadius: 9,
              fontSize: '0.75rem',
              fontWeight: 600,
              transition: 'all 0.2s',
              ...(period === value
                ? {
                    background: 'linear-gradient(135deg, rgba(34,211,238,0.18) 0%, rgba(129,140,248,0.18) 100%)',
                    color: '#22d3ee',
                    boxShadow: '0 1px 8px rgba(34,211,238,0.15)',
                  }
                : { color: 'rgba(255,255,255,0.38)' }),
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Filters strip */}
      {(['Filial: Test', 'Ustoz: Barchasi', "Bo'lim: Barchasi"] as const).map((f) => (
        <button
          key={f}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5"
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.07)',
            fontSize: '0.72rem',
            color: 'rgba(255,255,255,0.5)',
            fontWeight: 500,
            whiteSpace: 'nowrap',
          }}
        >
          {f}
          <ChevronDown size={12} style={{ opacity: 0.5 }} />
        </button>
      ))}

      {/* Refresh */}
      <button
        onClick={onRefresh}
        className="flex items-center justify-center rounded-xl"
        style={{
          width: 36, height: 36,
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.08)',
          color: 'rgba(255,255,255,0.5)',
          transition: 'all 0.2s',
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#22d3ee'; }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.5)'; }}
      >
        <RefreshCw size={15} />
      </button>

      {/* Export */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setExportOpen(o => !o)}
          className="flex items-center gap-2 rounded-xl px-4"
          style={{
            height: 36,
            background: 'linear-gradient(135deg, rgba(34,211,238,0.18) 0%, rgba(129,140,248,0.18) 100%)',
            border: '1px solid rgba(34,211,238,0.25)',
            color: '#22d3ee',
            fontSize: '0.78rem',
            fontWeight: 600,
            boxShadow: '0 0 20px rgba(34,211,238,0.08)',
            transition: 'all 0.2s',
          }}
        >
          <Download size={14} />
          Eksport
          <ChevronDown size={12} style={{ opacity: 0.7, marginLeft: -2 }} />
        </button>

        {exportOpen && (
          <div
            className="slide-up"
            style={{
              position: 'absolute',
              top: 42, right: 0,
              background: 'rgba(12,12,20,0.98)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12,
              padding: '6px',
              minWidth: 168,
              boxShadow: '0 16px 48px rgba(0,0,0,0.7)',
              zIndex: 999,
            }}
          >
            {[
              { icon: FileText,        label: 'PDF sifatida',    ext: 'PDF'   },
              { icon: FileSpreadsheet, label: 'Excel sifatida',  ext: 'Excel' },
              { icon: Image,           label: 'PNG sifatida',    ext: 'PNG'   },
            ].map(({ icon: Icon, label, ext }) => (
              <button
                key={ext}
                onClick={() => handleExport(ext)}
                className="flex items-center gap-3 w-full rounded-lg px-3 py-2.5"
                style={{
                  fontSize: '0.78rem',
                  color: 'rgba(255,255,255,0.75)',
                  transition: 'all 0.15s',
                  textAlign: 'left',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
              >
                <Icon size={14} style={{ color: '#22d3ee', opacity: 0.8 }} />
                {label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Avatar */}
      <div className="flex items-center gap-2 pl-1">
        <div
          className="flex items-center justify-center rounded-full font-bold"
          style={{
            width: 34, height: 34,
            background: 'linear-gradient(135deg, #22d3ee 0%, #818cf8 100%)',
            color: '#050507',
            fontSize: '0.72rem',
            flexShrink: 0,
          }}
        >
          D
        </div>
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#e2e8f0', lineHeight: 1.2 }}>Test</p>
          <p style={{ fontSize: '0.64rem', color: 'rgba(255,255,255,0.35)' }}>Direktor</p>
        </div>
      </div>
    </header>
  );
}
