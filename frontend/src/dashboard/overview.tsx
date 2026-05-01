'use client';

import { FileText, Link as LinkIcon, MessageSquare, Zap } from 'lucide-react';

export function Overview() {
  const stats = [
    {
      label: 'Total Documents',
      value: '248',
      change: '+12 this week',
      icon: FileText,
      gradient: 'from-blue-500 to-cyan-500',
      shadowColor: 'shadow-blue-500/20',
    },
    {
      label: 'URLs Indexed',
      value: '87',
      change: '+5 this week',
      icon: LinkIcon,
      gradient: 'from-purple-500 to-pink-500',
      shadowColor: 'shadow-purple-500/20',
    },
    {
      label: 'Chat Sessions',
      value: '1,429',
      change: '+124 this week',
      icon: MessageSquare,
      gradient: 'from-emerald-500 to-teal-500',
      shadowColor: 'shadow-emerald-500/20',
    },
    {
      label: 'Processing Speed',
      value: '2.4s',
      change: 'Avg response time',
      icon: Zap,
      gradient: 'from-orange-500 to-amber-500',
      shadowColor: 'shadow-orange-500/20',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div
            key={stat.label}
            className="glass-card rounded-xl p-6 hover:border-[hsl(var(--border-hover))] transition-all duration-300 group hover:-translate-y-0.5"
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="text-muted-foreground text-sm font-medium">
                {stat.label}
              </h3>
              <div
                className={`p-2.5 rounded-xl bg-gradient-to-br ${stat.gradient} shadow-lg ${stat.shadowColor} group-hover:scale-110 transition-transform duration-300`}
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
