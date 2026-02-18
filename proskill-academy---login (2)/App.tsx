
import React, { useState, useEffect } from 'react';
import VisualSection from './components/VisualSection';
import LoginForm from './components/LoginForm';
import { Sun, Moon } from 'lucide-react';

export type Language = 'uz' | 'ru' | 'en';
export type Theme = 'light' | 'dark';

const App: React.FC = () => {
  const [theme, setTheme] = useState<Theme>('light');
  const [lang, setLang] = useState<Language>('uz');

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  return (
    <main className={`h-screen-custom w-full flex flex-col md:flex-row overflow-hidden transition-all-custom ${theme === 'dark' ? 'bg-slate-950' : 'bg-white'}`}>
      
      {/* Settings Bar - Top Corner */}
      <div className="absolute top-5 right-5 z-50 flex items-center space-x-3">
        {/* Language Switcher - More Compact */}
        <div className="flex bg-slate-100/80 dark:bg-slate-800/80 backdrop-blur-md p-0.5 rounded-lg border border-slate-200 dark:border-slate-700 shadow-sm">
          {(['uz', 'ru', 'en'] as Language[]).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-2.5 py-1 rounded-md text-[10px] font-black transition-all uppercase ${
                lang === l 
                ? 'bg-white dark:bg-slate-600 text-primary-600 dark:text-white shadow-sm' 
                : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        {/* Theme Toggle */}
        <button
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          className="p-2 bg-slate-100/80 dark:bg-slate-800/80 backdrop-blur-md rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all shadow-sm"
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>

      {/* Left Side: Illustration & Glows */}
      <section className={`hidden md:flex md:w-1/2 h-full items-center justify-center relative transition-all-custom ${
        theme === 'dark' ? 'bg-slate-900' : 'bg-[#fcfdff]'
      }`}>
        <VisualSection theme={theme} />
      </section>

      {/* Right Side: Primary Panel */}
      <section className={`w-full md:w-1/2 h-full flex items-center justify-center p-6 md:p-10 relative transition-all-custom ${
        theme === 'dark' 
        ? 'bg-gradient-to-br from-slate-900 via-slate-950 to-blue-950/40' 
        : 'bg-gradient-to-br from-primary-600 to-indigo-700'
      }`}>
        {/* Background Decorative elements - Abstract patterns */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/5 rounded-full blur-[100px] -mr-40 -mt-40 pointer-events-none"></div>
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-black/10 rounded-full blur-[100px] -ml-40 -mb-40 pointer-events-none"></div>
        
        <LoginForm lang={lang} theme={theme} />
      </section>
    </main>
  );
};

export default App;
