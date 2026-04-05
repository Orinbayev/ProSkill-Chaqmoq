import React from 'react';
import { motion } from 'motion/react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { cn } from '@/src/lib/utils';

interface InsightCardProps {
  title: string;
  description: string;
  type: 'positive' | 'warning' | 'info';
}

export const InsightCard: React.FC<InsightCardProps> = ({ title, description, type }) => {
  const styles = {
    positive: 'bg-accent-emerald/10 text-accent-emerald border-accent-emerald/20',
    warning: 'bg-accent-amber/10 text-accent-amber border-accent-amber/20',
    info: 'bg-accent-blue/10 text-accent-blue border-accent-blue/20',
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "p-5 rounded-apple-lg border flex gap-4 items-start group cursor-pointer hover:shadow-lg transition-all",
        styles[type]
      )}
    >
      <div className="mt-1 p-2 rounded-full bg-app-surface shadow-md">
        <Sparkles size={16} />
      </div>
      <div className="flex-1">
        <h4 className="font-bold text-sm mb-1 text-text-primary">{title}</h4>
        <p className="text-[13px] text-text-secondary leading-relaxed">{description}</p>
      </div>
      <div className="mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <ArrowRight size={16} />
      </div>
    </motion.div>
  );
};
