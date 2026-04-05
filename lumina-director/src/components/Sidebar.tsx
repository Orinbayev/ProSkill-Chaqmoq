import React from 'react';
import { 
  LayoutDashboard, 
  Users, 
  GraduationCap, 
  Wallet, 
  Target, 
  Settings, 
  LogOut,
  School,
  Search,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const navItems = [
  { icon: LayoutDashboard, label: 'Overview', active: true },
  { icon: Wallet, label: 'Finance' },
  { icon: Target, label: 'Marketing' },
  { icon: GraduationCap, label: 'Groups' },
  { icon: Users, label: 'Teachers' },
  { icon: GraduationCap, label: 'Students' },
];

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isCollapsed, onToggle }) => {
  return (
    <aside className={cn(
      "bg-app-surface border-r border-app-border h-screen sticky top-0 flex flex-col hidden lg:flex transition-all duration-300 ease-in-out",
      isCollapsed ? "w-[80px]" : "w-[260px]"
    )}>
      <div className={cn("p-6 flex items-center justify-between", isCollapsed ? "px-4" : "px-8")}>
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-9 h-9 min-w-[36px] rounded-apple bg-white flex items-center justify-center text-black">
            <School size={20} />
          </div>
          {!isCollapsed && <span className="font-bold text-lg tracking-tight text-text-primary whitespace-nowrap">Lumina</span>}
        </div>
      </div>

      <div className="px-4 mb-6">
        <div className="relative">
          <Search className={cn("absolute top-1/2 -translate-y-1/2 text-text-tertiary", isCollapsed ? "left-1/2 -translate-x-1/2" : "left-3")} size={16} />
          {!isCollapsed && (
            <input 
              type="text" 
              placeholder="Search" 
              className="w-full apple-input pl-10 h-9 text-[13px]"
            />
          )}
          {isCollapsed && <div className="h-9 w-full" />}
        </div>
      </div>

      <nav className="flex-1 px-4 space-y-1 overflow-hidden">
        {!isCollapsed && <p className="px-4 text-[11px] font-bold text-text-tertiary uppercase tracking-widest mb-2">Main</p>}
        {navItems.map((item, idx) => (
          <button
            key={idx}
            title={isCollapsed ? item.label : undefined}
            className={cn(
              "w-full flex items-center gap-3 rounded-apple text-[14px] font-medium transition-all group",
              isCollapsed ? "justify-center p-2.5" : "px-4 py-2.5",
              item.active 
                ? "bg-app-divider text-text-primary" 
                : "text-text-secondary hover:bg-app-divider/50 hover:text-text-primary"
            )}
          >
            <item.icon size={18} className={cn(item.active ? "text-text-primary" : "text-text-tertiary group-hover:text-text-secondary")} />
            {!isCollapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className={cn("p-6 border-t border-app-divider space-y-4", isCollapsed && "p-4")}>
        <div className={cn("flex items-center gap-3", isCollapsed ? "justify-center" : "px-2")}>
          <div className="w-8 h-8 min-w-[32px] rounded-full bg-app-bg flex items-center justify-center overflow-hidden border border-app-border">
            <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Director" alt="Avatar" referrerPolicy="no-referrer" />
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-bold text-text-primary truncate">Alex Rivera</p>
              <p className="text-[11px] text-text-secondary truncate">Director</p>
            </div>
          )}
          {!isCollapsed && (
            <button className="text-text-tertiary hover:text-text-primary transition-colors">
              <Settings size={16} />
            </button>
          )}
        </div>
        
        <button className={cn(
          "w-full flex items-center gap-3 rounded-apple text-[13px] font-medium text-accent-red hover:bg-accent-red/10 transition-all",
          isCollapsed ? "justify-center p-2.5" : "px-4 py-2"
        )}>
          <LogOut size={16} />
          {!isCollapsed && <span>Sign Out</span>}
        </button>
      </div>

      {/* Collapse Toggle Button */}
      <button 
        onClick={onToggle}
        className="absolute -right-3 top-20 w-6 h-6 bg-app-surface border border-app-border rounded-full flex items-center justify-center text-text-secondary hover:text-text-primary shadow-md z-50 transition-all"
      >
        {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  );
};
