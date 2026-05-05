'use client';

import { FileText, Link as LinkIcon, MessageSquare, Settings } from 'lucide-react';

interface ActivityItem {
  id: string;
  type: 'upload' | 'url' | 'chat' | 'setting';
  title: string;
  description: string;
  timestamp: string;
}

export function Activity() {
  const activities: ActivityItem[] = [];

  const typeConfig = {
    upload: {
      icon: FileText,
      gradient: 'from-blue-500 to-cyan-500',
      iconColor: 'text-white',
    },
    url: {
      icon: LinkIcon,
      gradient: 'from-purple-500 to-pink-500',
      iconColor: 'text-white',
    },
    chat: {
      icon: MessageSquare,
      gradient: 'from-emerald-500 to-teal-500',
      iconColor: 'text-white',
    },
    setting: {
      icon: Settings,
      gradient: 'from-orange-500 to-amber-500',
      iconColor: 'text-white',
    },
  };

  return (
    <div className="glass-card rounded-xl p-6">
      <h2 className="text-lg font-semibold text-foreground mb-6 tracking-tight">
        Recent Activity
      </h2>
      <div className="space-y-4">
        {activities.map((activity) => {
          const config = typeConfig[activity.type];
          const Icon = config.icon;

          return (
            <div
              key={activity.id}
              className="flex gap-3 p-2.5 rounded-xl hover:bg-secondary/50 transition-all duration-200 group cursor-default"
            >
              <div
                className={`p-2 rounded-lg h-fit bg-linear-to-br ${config.gradient} shadow-sm group-hover:scale-110 transition-transform duration-200`}
              >
                <Icon size={14} className={config.iconColor} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-foreground font-medium text-sm">
                  {activity.title}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {activity.description}
                </p>
              </div>
              <p className="text-xs text-muted-foreground shrink-0 mt-0.5">
                {activity.timestamp}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
