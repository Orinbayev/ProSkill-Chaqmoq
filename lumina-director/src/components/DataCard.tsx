import React from 'react';
import { cn } from '@/src/lib/utils';

interface DataCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  headerAction?: React.ReactNode;
}

export const DataCard: React.FC<DataCardProps> = ({ 
  title, 
  subtitle, 
  children, 
  className,
  headerAction 
}) => {
  return (
    <div className={cn("apple-card flex flex-col", className)}>
      <div className="px-6 py-5 border-b border-app-divider flex justify-between items-center">
        <div>
          <h3 className="text-[15px] font-bold text-text-primary">{title}</h3>
          {subtitle && <p className="text-[12px] text-text-secondary mt-0.5">{subtitle}</p>}
        </div>
        {headerAction && <div>{headerAction}</div>}
      </div>
      <div className="flex-1 p-6">
        {children}
      </div>
    </div>
  );
};
