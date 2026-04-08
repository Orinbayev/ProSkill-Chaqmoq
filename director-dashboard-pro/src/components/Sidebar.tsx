import React from 'react';
import {
  Zap, LayoutDashboard, TrendingUp, Users, BookOpen,
  CreditCard, BarChart3, Settings, Bell, HelpCircle
} from 'lucide-react';

interface SidebarProps {
  active: string;
  onNav: (id: string) => void;
}

const navItems = [
  { id: 'dashboard', icon: LayoutDashboard, label: 'Bosh sahifa' },
  { id: 'moliya',    icon: TrendingUp,      label: 'Moliya'      },
  { id: 'oquvchi',   icon: Users,           label: "O'quvchilar" },
  { id: 'kurs',      icon: BookOpen,        label: 'Kurslar'     },
  { id: 'tolov',     icon: CreditCard,      label: "To'lovlar"   },
  { id: 'hisobot',   icon: BarChart3,       label: 'Hisobotlar'  },
];

const bottomItems = [
  { id: 'xabar',    icon: Bell,        label: 'Xabarnoma'  },
  { id: 'sozlama',  icon: Settings,    label: 'Sozlamalar' },
  { id: 'yordam',   icon: HelpCircle,  label: 'Yordam'     },
];

export function Sidebar({ active, onNav }: SidebarProps) {
  return (
    <aside
      className="fixed left-0 top-0 h-full z-30 flex flex-col"
      style={{
        width: 64,
        background: 'rgba(7,7,12,0.92)',
        borderRight: '1px solid rgba(255,255,255,0.055)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-center"
        style={{ height: 64, borderBottom: '1px solid rgba(255,255,255,0.05)' }}
      >
        <div
          className="flex items-center justify-center rounded-xl"
          style={{
            width: 38, height: 38,
            background: 'linear-gradient(135deg, rgba(34,211,238,0.2) 0%, rgba(129,140,248,0.2) 100%)',
            border: '1px solid rgba(34,211,238,0.25)',
            boxShadow: '0 0 20px rgba(34,211,238,0.15)',
          }}
        >
          <Zap size={18} style={{ color: '#22d3ee' }} strokeWidth={2.5} />
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 flex flex-col gap-1 py-3 px-2 overflow-y-auto">
        {navItems.map(({ id, icon: Icon, label }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              onClick={() => onNav(id)}
              title={label}
              className={`nav-item flex items-center justify-center rounded-lg ${isActive ? 'nav-active' : ''}`}
              style={{ width: '100%', height: 44, position: 'relative' }}
            >
              <Icon size={18} strokeWidth={isActive ? 2.2 : 1.8} />
              {isActive && (
                <span
                  style={{
                    position: 'absolute',
                    right: -2,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: 3,
                    height: 20,
                    borderRadius: '2px 0 0 2px',
                    background: '#22d3ee',
                    boxShadow: '0 0 8px rgba(34,211,238,0.6)',
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom nav */}
      <div
        className="flex flex-col gap-1 py-3 px-2"
        style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
      >
        {bottomItems.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onNav(id)}
            title={label}
            className="nav-item flex items-center justify-center rounded-lg"
            style={{ width: '100%', height: 40, color: 'rgba(255,255,255,0.3)' }}
          >
            <Icon size={16} strokeWidth={1.7} />
          </button>
        ))}

        {/* Avatar */}
        <div className="flex items-center justify-center mt-2">
          <div
            className="flex items-center justify-center rounded-full text-xs font-bold"
            style={{
              width: 34, height: 34,
              background: 'linear-gradient(135deg, #22d3ee, #818cf8)',
              color: '#050507',
              fontSize: '0.65rem',
            }}
          >
            D
          </div>
        </div>
      </div>
    </aside>
  );
}
