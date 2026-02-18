
import React, { useState } from 'react';
import { Mail, Lock, Eye, EyeOff, ArrowRight, ShieldCheck } from 'lucide-react';
import { Language, Theme } from '../App';

interface LoginFormProps {
  lang: Language;
  theme: Theme;
}

const translations = {
  uz: {
    hello: "Xush kelibsiz!",
    sign_in: "Tizimga kirish uchun ma'lumotlarni kiriting",
    email: "Email manzili",
    password: "Parol",
    login_btn: "Tizimga kirish",
    forgot: "Parolni unutdingizmi?",
    no_account: "Hisobingiz yo'qmi?",
    create: "Ro'yxatdan o'ting"
  },
  ru: {
    hello: "Добро пожаловать!",
    sign_in: "Войдите в свой аккаунт",
    email: "Email адрес",
    password: "Пароль",
    login_btn: "Войти",
    forgot: "Забыли пароль?",
    no_account: "Нет аккаунта?",
    create: "Создать аккаунт"
  },
  en: {
    hello: "Welcome Back!",
    sign_in: "Sign in to access your dashboard",
    email: "Email Address",
    password: "Password",
    login_btn: "Sign In",
    forgot: "Forgot Password?",
    no_account: "New student?",
    create: "Create Account"
  }
};

const LoginForm: React.FC<LoginFormProps> = ({ lang, theme }) => {
  const [showPassword, setShowPassword] = useState(false);
  const isDark = theme === 'dark';
  const t = translations[lang];

  return (
    <div className={`w-full max-w-[420px] rounded-[1.5rem] p-8 md:p-10 premium-shadow relative z-10 transition-all duration-500 border overflow-hidden ${
      isDark 
      ? 'bg-slate-900/90 backdrop-blur-2xl border-white/10' 
      : 'bg-white/95 backdrop-blur-md border-slate-100'
    }`}>
      
      {/* Brand Icon & Trust Badge */}
      <div className="flex justify-between items-start mb-6">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-primary-600 to-cyan-500 flex items-center justify-center shadow-lg shadow-primary-500/20">
          <span className="text-white font-black text-xl">P</span>
        </div>
        <div className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider ${
          isDark ? 'bg-slate-800 text-slate-400' : 'bg-slate-50 text-slate-500'
        }`}>
          <ShieldCheck size={12} className="text-emerald-500" />
          <span>Secure Login</span>
        </div>
      </div>

      <div className="flex flex-col mb-6">
        <h1 className={`text-2xl font-extrabold mb-1.5 tracking-tight transition-colors ${isDark ? 'text-white' : 'text-slate-900'}`}>
          {t.hello}
        </h1>
        <p className={`text-sm font-medium transition-colors ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          {t.sign_in}
        </p>
      </div>

      <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
        {/* Email Address */}
        <div className="group space-y-1.5">
          <label className={`text-[10px] font-bold uppercase tracking-widest ml-1 transition-colors ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            {t.email}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Mail className={`h-4.5 w-4.5 transition-colors ${isDark ? 'text-slate-600 group-focus-within:text-primary-400' : 'text-slate-400 group-focus-within:text-primary-600'}`} />
            </div>
            <input
              type="email"
              placeholder="example@mail.com"
              className={`w-full border text-sm rounded-xl block pl-12 p-3.5 focus:ring-4 transition-all outline-none py-3 font-medium ${
                isDark 
                ? 'bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-600 focus:ring-primary-500/10 focus:border-primary-500' 
                : 'bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:ring-primary-500/10 focus:border-primary-500'
              }`}
              required
            />
          </div>
        </div>

        {/* Password */}
        <div className="group space-y-1.5">
          <label className={`text-[10px] font-bold uppercase tracking-widest ml-1 transition-colors ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
            {t.password}
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
              <Lock className={`h-4.5 w-4.5 transition-colors ${isDark ? 'text-slate-600 group-focus-within:text-primary-400' : 'text-slate-400 group-focus-within:text-primary-600'}`} />
            </div>
            <input
              type={showPassword ? "text" : "password"}
              placeholder="••••••••"
              className={`w-full border text-sm rounded-xl block pl-12 p-3.5 pr-12 focus:ring-4 transition-all outline-none py-3 font-medium ${
                isDark 
                ? 'bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-600 focus:ring-primary-500/10 focus:border-primary-500' 
                : 'bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:ring-primary-500/10 focus:border-primary-500'
              }`}
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-primary-500 transition-colors"
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </div>

        {/* Login Button */}
        <button
          type="submit"
          className="w-full relative group bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white font-bold py-4 rounded-xl transition-all shadow-lg shadow-primary-600/20 active:scale-[0.98] mt-2 flex items-center justify-center space-x-2"
        >
          <span className="text-sm uppercase tracking-wider">{t.login_btn}</span>
          <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
        </button>
      </form>

      {/* Footer Options - Reduced Spacing */}
      <div className="mt-6 flex flex-col items-center space-y-4">
        <a href="#" className={`text-xs font-bold transition-colors ${isDark ? 'text-primary-400 hover:text-primary-300' : 'text-primary-600 hover:text-primary-700'}`}>
          {t.forgot}
        </a>
        
        <div className={`w-full pt-5 border-t transition-colors ${isDark ? 'border-slate-800' : 'border-slate-100'}`}>
          <p className="text-center text-xs font-medium">
            <span className={isDark ? 'text-slate-500' : 'text-slate-400'}>{t.no_account} </span>
            <span className={`font-bold cursor-pointer hover:underline ${isDark ? 'text-white' : 'text-slate-900'}`}>
              {t.create}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginForm;
