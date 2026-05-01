// ============================================================
// ChaqmoqApp — Shared primitives (Phone, StatusBar, BottomNav, etc.)
// ============================================================

const { useState, useEffect, useRef, useMemo } = React;

// ---- Phone shell with iOS status bar ----
function Phone({ children, dark = false, lightBezel = false, label, onTap }) {
  return (
    <div className={`phone-shell ${lightBezel ? 'light-bezel' : ''}`}>
      <div
        className="phone-screen"
        style={{
          background: dark ? 'var(--s-bg-gradient)' : 'var(--p-bg)',
          color: dark ? 'var(--s-text)' : 'var(--p-text)'
        }}
        onClick={onTap}
      >
        {children}
      </div>
    </div>
  );
}

function StatusBar({ dark = false, time = "9:41" }) {
  const color = dark ? '#F1F2F6' : '#0F1E33';
  return (
    <div className="statusbar" style={{ color }}>
      <span>{time}</span>
      <div className="right">
        <span className="icon"><i></i><i></i><i></i><i></i></span>
        <span className="wifi"></span>
        <span className="battery"><i></i></span>
      </div>
    </div>
  );
}

// ---- Parent bottom nav ----
function ParentBottomNav({ active = 'home', onChange = () => {} }) {
  const items = [
    { id: 'home',     label: 'Bosh',     icon: 'home' },
    { id: 'attend',   label: 'Davomat',  icon: 'fact_check' },
    { id: 'pay',      label: "To'lovlar", icon: 'payments' },
    { id: 'progress', label: 'Progress', icon: 'insights' },
    { id: 'profile',  label: 'Profil',   icon: 'person' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      background: 'rgba(255,255,255,0.92)',
      backdropFilter: 'blur(20px)',
      borderTop: '1px solid var(--p-line)',
      padding: '8px 8px 28px',
      display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
      zIndex: 10,
    }}>
      {items.map(it => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            onClick={() => onChange(it.id)}
            style={{
              border: 0, background: 'transparent',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              padding: '6px 0',
              color: isActive ? 'var(--p-primary)' : 'var(--p-text-muted)',
              cursor: 'pointer',
              fontFamily: 'inherit',
            }}
          >
            <span className={`material-symbols-rounded ${isActive ? 'msr-fill' : ''}`} style={{ fontSize: 24 }}>{it.icon}</span>
            <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.01em' }}>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ---- Student bottom nav (dark glass) ----
function StudentBottomNav({ active = 'panel', onChange = () => {} }) {
  const items = [
    { id: 'panel',    label: 'Panel',     icon: 'dashboard' },
    { id: 'pay',      label: "To'lovlar", icon: 'payments' },
    { id: 'msg',      label: 'Xabarlar',  icon: 'forum' },
    { id: 'profile',  label: 'Profil',    icon: 'person' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 14, right: 14, bottom: 18,
      height: 70,
      background: 'rgba(19,19,26,0.85)',
      backdropFilter: 'blur(24px)',
      border: '1px solid var(--s-border)',
      borderRadius: 22,
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
      alignItems: 'center', padding: '0 6px',
      zIndex: 10,
      boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    }}>
      {items.map(it => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            onClick={() => onChange(it.id)}
            style={{
              border: 0, background: 'transparent',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
              padding: '6px 0',
              color: isActive ? 'var(--s-primary)' : 'var(--s-text-muted)',
              cursor: 'pointer',
              fontFamily: 'inherit',
              position: 'relative',
            }}
          >
            <span style={{
              padding: isActive ? '5px 16px' : 0,
              borderRadius: 100,
              background: isActive ? 'rgba(0,212,170,0.14)' : 'transparent',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s',
            }}>
              <span className={`material-symbols-rounded ${isActive ? 'msr-fill' : ''}`} style={{ fontSize: 22 }}>{it.icon}</span>
            </span>
            <span style={{ fontSize: 10, fontWeight: 700 }}>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ---- Parent app bar ----
function ParentAppBar({ title, onBack, right, leftAction }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 18px 14px',
      background: 'var(--p-bg)',
    }}>
      {onBack ? (
        <button onClick={onBack} style={iconBtnLight}>
          <span className="material-symbols-rounded" style={{ fontSize: 22 }}>arrow_back</span>
        </button>
      ) : leftAction || null}
      <h1 style={{
        fontSize: 19, fontWeight: 800, margin: 0,
        letterSpacing: '-0.01em', flex: 1,
      }}>{title}</h1>
      {right}
    </div>
  );
}

const iconBtnLight = {
  width: 40, height: 40, borderRadius: 12,
  background: 'var(--p-card)',
  border: '1px solid var(--p-line)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--p-text)',
  cursor: 'pointer', flexShrink: 0,
};

const iconBtnDark = {
  width: 40, height: 40, borderRadius: 12,
  background: 'var(--s-glass)',
  border: '1px solid var(--s-border)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  color: 'var(--s-text)',
  cursor: 'pointer', flexShrink: 0,
};

// ---- Avatar (initials) ----
function Avatar({ name, size = 40, color = 'blue', src }) {
  const initials = name.split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase();
  const palettes = {
    blue:   { bg: 'linear-gradient(135deg, #3B82F6, #60A5FA)', fg: '#fff' },
    teal:   { bg: 'linear-gradient(135deg, #00D4AA, #2BE5BF)', fg: '#0A1F1A' },
    violet: { bg: 'linear-gradient(135deg, #6C63FF, #8C85FF)', fg: '#fff' },
    amber:  { bg: 'linear-gradient(135deg, #F59E0B, #FBBF24)', fg: '#3F2A06' },
    rose:   { bg: 'linear-gradient(135deg, #F43F5E, #FB7185)', fg: '#fff' },
    slate:  { bg: 'linear-gradient(135deg, #475569, #64748B)', fg: '#fff' },
  };
  const p = palettes[color] || palettes.blue;
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: p.bg, color: p.fg,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 800, fontSize: size * 0.36,
      flexShrink: 0,
      boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
      letterSpacing: '-0.01em',
    }}>
      {initials}
    </div>
  );
}

// ---- Badge ----
function Badge({ tone = 'success', children, soft = true, dark = false }) {
  const tones = {
    success: dark
      ? { bg: 'rgba(46,213,115,0.14)', fg: '#2ED573' }
      : { bg: 'var(--p-success-bg)', fg: 'var(--p-success)' },
    warning: dark
      ? { bg: 'rgba(255,165,2,0.16)', fg: '#FFA502' }
      : { bg: 'var(--p-warning-bg)', fg: 'var(--p-amber-deep)' },
    danger: dark
      ? { bg: 'rgba(255,71,87,0.14)', fg: '#FF4757' }
      : { bg: 'var(--p-danger-bg)', fg: 'var(--p-danger)' },
    info: dark
      ? { bg: 'rgba(79,195,247,0.14)', fg: '#4FC3F7' }
      : { bg: 'var(--p-info-bg)', fg: 'var(--p-primary-deep)' },
    teal: { bg: 'rgba(0,212,170,0.14)', fg: '#00D4AA' },
    violet: { bg: 'rgba(108,99,255,0.16)', fg: '#8C85FF' },
    neutral: dark
      ? { bg: 'rgba(255,255,255,0.06)', fg: '#8892A4' }
      : { bg: '#F1F5F9', fg: '#64748B' },
  };
  const t = tones[tone] || tones.success;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '4px 9px',
      borderRadius: 100,
      background: t.bg, color: t.fg,
      fontSize: 11, fontWeight: 700,
      letterSpacing: '0.01em',
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

// ---- Card (light) ----
function PCard({ children, style, padding = 16, ...rest }) {
  return (
    <div style={{
      background: 'var(--p-card)',
      border: '1px solid var(--p-line)',
      borderRadius: 20,
      padding,
      boxShadow: 'var(--p-shadow-sm)',
      ...style,
    }} {...rest}>{children}</div>
  );
}

// ---- Glass card (dark) ----
function GCard({ children, style, padding = 16, strong = false, ...rest }) {
  return (
    <div style={{
      background: strong ? 'var(--s-glass-strong)' : 'var(--s-glass)',
      border: '1px solid var(--s-border)',
      borderRadius: 20,
      padding,
      ...style,
    }} {...rest}>{children}</div>
  );
}

// ---- Primary button ----
function PButton({ children, icon, full = true, variant = 'primary', onClick, dark = false }) {
  const variants = dark ? {
    primary: { bg: 'var(--s-primary-gradient)', fg: '#0A1F1A', shadow: 'var(--s-glow-teal)' },
    violet:  { bg: 'var(--s-violet-gradient)',  fg: '#fff',     shadow: 'var(--s-glow-violet)' },
    ghost:   { bg: 'var(--s-glass)', fg: 'var(--s-text)', shadow: 'none', border: '1px solid var(--s-border)' },
  } : {
    primary: { bg: 'linear-gradient(135deg, var(--p-primary), var(--p-primary-deep))', fg: '#fff', shadow: 'var(--p-shadow-blue)' },
    secondary: { bg: 'var(--p-card)', fg: 'var(--p-text)', shadow: 'var(--p-shadow-sm)', border: '1px solid var(--p-line-strong)' },
    ghost: { bg: 'transparent', fg: 'var(--p-primary)', shadow: 'none' },
  };
  const v = variants[variant] || variants.primary;
  return (
    <button
      onClick={onClick}
      style={{
        width: full ? '100%' : 'auto',
        height: 52,
        borderRadius: 16,
        background: v.bg,
        color: v.fg,
        border: v.border || 0,
        boxShadow: v.shadow,
        fontFamily: 'inherit',
        fontWeight: 700,
        fontSize: 14.5,
        letterSpacing: '0.01em',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        cursor: 'pointer',
        padding: full ? 0 : '0 22px',
      }}
    >
      {icon ? <span className="material-symbols-rounded" style={{ fontSize: 20 }}>{icon}</span> : null}
      {children}
    </button>
  );
}

// ---- Inline mini line chart (SVG) ----
function MiniLine({ data, color = 'var(--p-primary)', width = 320, height = 80, fill = true, animate = true }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = Math.max(1, max - min);
  const stepX = width / (data.length - 1);
  const pts = data.map((v, i) => {
    const x = i * stepX;
    const y = height - 8 - ((v - min) / range) * (height - 16);
    return [x, y];
  });
  const path = pts.map((p, i) => (i === 0 ? `M ${p[0]} ${p[1]}` : `L ${p[0]} ${p[1]}`)).join(' ');
  const area = `${path} L ${width} ${height} L 0 ${height} Z`;
  const id = useMemo(() => `g${Math.random().toString(36).slice(2, 8)}`, []);
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', overflow: 'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${id})`} style={animate ? { animation: 'fadeIn 0.7s ease' } : {}} />}
      <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        style={animate ? { strokeDasharray: 1000, strokeDashoffset: 1000, animation: 'drawLine 1.2s ease forwards' } : {}}
      />
      {pts.map(([x, y], i) => (
        i === pts.length - 1 ? (
          <g key={i}>
            <circle cx={x} cy={y} r="6" fill={color} opacity="0.18" />
            <circle cx={x} cy={y} r="3.5" fill={color} />
            <circle cx={x} cy={y} r="2" fill="#fff" />
          </g>
        ) : null
      ))}
    </svg>
  );
}

// ---- Bar chart ----
function MiniBars({ data, labels, color = 'var(--p-primary)', height = 110, max }) {
  const m = max || Math.max(...data);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height }}>
      {data.map((v, i) => (
        <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, height: '100%' }}>
          <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'flex-end' }}>
            <div style={{
              width: '100%',
              height: `${(v / m) * 100}%`,
              background: color, opacity: 0.85,
              borderRadius: '6px 6px 2px 2px',
              minHeight: 4,
              transition: 'height 0.6s ease',
            }} />
          </div>
          <div style={{ fontSize: 10, color: 'var(--p-text-muted)', fontWeight: 600 }}>{labels[i]}</div>
        </div>
      ))}
    </div>
  );
}

// ---- Lightning logo mark ----
function ChaqmoqMark({ size = 32, dark = false }) {
  return (
    <div style={{
      width: size, height: size,
      borderRadius: size * 0.28,
      background: dark
        ? 'linear-gradient(135deg, rgba(0,212,170,0.18), rgba(108,99,255,0.18))'
        : 'linear-gradient(135deg, var(--p-primary), var(--p-primary-deep))',
      color: dark ? 'var(--s-primary)' : '#fff',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      boxShadow: dark ? 'none' : '0 6px 16px rgba(59,130,246,0.32)',
      flexShrink: 0,
      border: dark ? '1px solid rgba(0,212,170,0.32)' : 'none',
    }}>
      <span className="material-symbols-rounded msr-fill" style={{ fontSize: size * 0.6 }}>bolt</span>
    </div>
  );
}

// ---- Bottom sheet wrapper (just the chrome) ----
function BottomSheet({ title, onClose, children, dark = false, height }) {
  const bg = dark ? 'rgba(19,19,26,0.98)' : '#fff';
  const fg = dark ? 'var(--s-text)' : 'var(--p-text)';
  const line = dark ? 'var(--s-border)' : 'var(--p-line)';
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0,
      background: bg, color: fg,
      borderTopLeftRadius: 28, borderTopRightRadius: 28,
      borderTop: `1px solid ${line}`,
      borderLeft: `1px solid ${line}`, borderRight: `1px solid ${line}`,
      boxShadow: '0 -20px 40px rgba(0,0,0,0.18)',
      maxHeight: height || '70%',
      overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
      zIndex: 30,
      backdropFilter: dark ? 'blur(24px)' : 'none',
    }}>
      <div style={{ padding: '12px 0 6px', display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: 40, height: 4, borderRadius: 2, background: dark ? 'rgba(255,255,255,0.18)' : 'var(--p-line-strong)' }} />
      </div>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '4px 20px 14px',
      }}>
        <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800 }}>{title}</h3>
        {onClose && (
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 10,
            background: dark ? 'var(--s-glass)' : 'var(--p-bg-soft)',
            border: 0, color: 'inherit',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer',
          }}>
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>close</span>
          </button>
        )}
      </div>
      <div style={{ overflowY: 'auto', padding: '0 20px 28px', flex: 1 }} className="no-scrollbar">
        {children}
      </div>
    </div>
  );
}

// ---- Scrim ----
function Scrim({ onClick }) {
  return (
    <div onClick={onClick} style={{
      position: 'absolute', inset: 0,
      background: 'rgba(8,12,22,0.55)',
      zIndex: 25, backdropFilter: 'blur(2px)',
    }} />
  );
}

// Export to global scope so other JSX scripts can use them
Object.assign(window, {
  Phone, StatusBar, ParentBottomNav, StudentBottomNav,
  ParentAppBar, iconBtnLight, iconBtnDark,
  Avatar, Badge, PCard, GCard, PButton,
  MiniLine, MiniBars, ChaqmoqMark,
  BottomSheet, Scrim,
});
