
import React from 'react';
import { Monitor, User, Layout, Database, Book, GraduationCap, Brain, Code } from 'lucide-react';
import { Theme } from '../App';

interface VisualSectionProps {
  theme: Theme;
}

const VisualSection: React.FC<VisualSectionProps> = ({ theme }) => {
  const isDark = theme === 'dark';

  return (
    <div className="relative w-full h-full flex flex-col items-center justify-center overflow-hidden">
      {/* Dynamic Background Elements */}
      <div className={`absolute inset-0 transition-colors duration-700 ${
        isDark 
        ? 'bg-[radial-gradient(circle_at_30%_30%,rgba(59,130,246,0.1),transparent_70%)]' 
        : 'bg-[radial-gradient(circle_at_30%_30%,rgba(59,130,246,0.08),transparent_70%)]'
      }`}></div>

      {/* Floating Education Icons in Background */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <Book className="absolute top-[15%] left-[10%] w-8 h-8 text-blue-400 rotate-12 animate-pulse" />
        <GraduationCap className="absolute bottom-[20%] left-[15%] w-12 h-12 text-indigo-400 -rotate-12 animate-bounce" style={{ animationDuration: '5s' }} />
        <Brain className="absolute top-[20%] right-[15%] w-10 h-10 text-cyan-400 rotate-6 animate-pulse" />
        <Code className="absolute bottom-[15%] right-[20%] w-8 h-8 text-blue-500 -rotate-6" />
      </div>

      <div className="relative z-10 w-full max-w-lg flex flex-col items-center justify-center">
        <div className="relative w-64 h-64 md:w-80 md:h-80">
          {/* Main Visual Core */}
          <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full rounded-full blur-[80px] transition-colors duration-500 ${
            isDark ? 'bg-primary-600/20' : 'bg-primary-500/10'
          }`}></div>
          
          {/* Abstract UI Elements - Compacted for better fit */}
          <div className={`absolute bottom-1/4 left-1/2 -translate-x-1/2 w-64 h-36 rounded-2xl shadow-2xl border transition-all duration-500 ${
            isDark ? 'bg-slate-800/90 border-slate-700 shadow-black/40' : 'bg-white border-slate-200 shadow-slate-200'
          } p-5 flex flex-col space-y-3 backdrop-blur-sm`}>
              <div className={`h-2.5 w-1/2 rounded-full ${isDark ? 'bg-slate-700' : 'bg-slate-100'}`}></div>
              <div className={`h-2.5 w-full rounded-full ${isDark ? 'bg-slate-700' : 'bg-slate-100'}`}></div>
              <div className={`h-16 w-full rounded-xl mt-1 transition-colors ${isDark ? 'bg-primary-900/30' : 'bg-primary-50/50'}`}></div>
          </div>

          {/* User Badge - Floating Badge */}
          <div className={`absolute top-[10%] right-[10%] p-3.5 rounded-2xl shadow-xl transition-all duration-500 animate-bounce ${
            isDark ? 'bg-slate-700 border-slate-600' : 'bg-white border-white shadow-blue-500/10'
          } border`} style={{ animationDuration: '4s' }}>
            <User className="w-7 h-7 text-primary-500" />
          </div>

          {/* Orbiting Tech Icons */}
          <div className="absolute top-0 left-0 p-2.5 bg-primary-600 shadow-lg shadow-primary-500/30 rounded-xl">
            <Layout className="w-5 h-5 text-white" />
          </div>
          <div className={`absolute bottom-10 right-0 p-2.5 rounded-xl shadow-lg border transition-all ${
            isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-100'
          }`}>
            <Database className="w-5 h-5 text-cyan-500" />
          </div>
        </div>
        
        <div className="mt-10 text-center space-y-3 px-6">
          <div className="inline-flex items-center space-x-2 bg-primary-500/10 text-primary-600 dark:text-primary-400 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider mb-2">
            <GraduationCap size={14} />
            <span>Top-tier Academy</span>
          </div>
          <h3 className={`text-3xl font-black transition-colors leading-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
            ProSkill <span className="text-primary-500">Academy</span>
          </h3>
          <p className={`text-base font-medium max-w-xs mx-auto transition-colors ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Professional education platform for the next generation of IT leaders.
          </p>
        </div>
      </div>
    </div>
  );
};

export default VisualSection;
