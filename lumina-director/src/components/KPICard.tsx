import React from 'react';
import { motion } from 'motion/react';
import { cn, formatCurrency, formatNumber } from '@/src/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

interface KPICardProps {
  title: string;
  value: number;
  isCurrency?: boolean;
  change: number;
  data?: { value: number }[];
  color?: 'emerald' | 'amber' | 'blue' | 'red';
}

export const KPICard: React.FC<KPICardProps> = ({ 
  title, 
  value, 
  isCurrency = false, 
  change, 
  data = [],
  color = 'blue'
}) => {
  const isPositive = change >= 0;
  
  const colorMap = {
    emerald: '#32d74b',
    amber: '#ff9f0a',
    blue: '#0a84ff',
    red: '#ff453a',
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="apple-card p-6 flex flex-col h-full overflow-hidden relative"
    >
      <div className="flex justify-between items-start mb-2 relative z-10">
        <p className="text-[13px] font-medium text-text-secondary uppercase tracking-wider">{title}</p>
        <div className={cn(
          "flex items-center gap-1 text-[13px] font-semibold",
          isPositive ? "text-accent-emerald" : "text-accent-red"
        )}>
          {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {Math.abs(change)}%
        </div>
      </div>
      
      <h3 className="text-3xl font-bold text-text-primary tracking-tight mb-4 relative z-10">
        {isCurrency ? formatCurrency(value) : formatNumber(value)}
      </h3>

      {data.length > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-16 opacity-30">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colorMap[color]} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={colorMap[color]} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area 
                type="monotone" 
                dataKey="value" 
                stroke={colorMap[color]} 
                strokeWidth={2} 
                fill={`url(#gradient-${title})`} 
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
};
