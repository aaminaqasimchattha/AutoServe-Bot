'use client';

import { FileText, Link as LinkIcon, MessageSquare, Zap } from 'lucide-react';

interface Stat {
  label: string;
  value: string | number;
  change: string;
  icon: React.ElementType;
  gradient: string;
  shadowColor: string;
}

export function Overview() {
  const stats: Stat[] = [];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div
            key={stat.label}
            className="glass-card rounded-xl p-6 hover:border-primary/50 transition-all duration-300 group hover:-translate-y-0.5"
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-muted-foreground text-sm font-medium">
                {stat.label}
              </h3>
              <div
                className={`p-2.5 rounded-xl bg-linear-to-br ${stat.gradient} shadow-lg ${stat.shadowColor} group-hover:scale-110 transition-transform duration-300`}
              >
                <Icon size={18} className="text-white" />
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-3xl font-bold text-foreground tracking-tight">
                {stat.value}
              </p>
              <p className="text-xs text-muted-foreground">{stat.change}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
