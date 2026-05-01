'use client';

import Link from 'next/link';
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  Settings,
  LogOut,
  Bot,
} from 'lucide-react';

export function Sidebar() {
  return (
    <aside className="w-64 bg-[hsl(var(--sidebar))] border-r border-[hsl(var(--border))] h-screen flex flex-col">
      {/* Logo Section */}
      <div className="p-6 border-b border-[hsl(var(--border))]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center shadow-lg shadow-[hsl(var(--primary)/0.3)]">
            <Bot className="text-white" size={22} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground tracking-tight">
              AutoServe
            </h1>
            <p className="text-xs text-[hsl(var(--primary))] font-medium">
              AI Knowledge Hub
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <NavItem
          href="#"
          icon={<LayoutDashboard size={20} />}
          label="Dashboard"
          active
        />
        <NavItem
          href="#"
          icon={<FileText size={20} />}
          label="Knowledge Base"
        />
        <NavItem
          href="#"
          icon={<MessageSquare size={20} />}
          label="Chat"
        />
        <NavItem
          href="#"
          icon={<Settings size={20} />}
          label="Settings"
        />
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-[hsl(var(--border))] space-y-3">
        <div className="flex items-center gap-3 px-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[hsl(var(--accent))] to-[hsl(var(--primary))] flex items-center justify-center flex-shrink-0 shadow-md">
            <span className="text-white font-semibold text-sm">AQ</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">
              Admin
            </p>
            <p className="text-xs text-muted-foreground truncate">
              admin@autoserve.bot
            </p>
          </div>
        </div>
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-[hsl(var(--secondary))] rounded-lg transition-all duration-200">
          <LogOut size={18} />
          Logout
        </button>
      </div>
    </aside>
  );
}

interface NavItemProps {
  href: string;
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}

function NavItem({ href, icon, label, active }: NavItemProps) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 ${
        active
          ? 'bg-gradient-to-r from-[hsl(var(--primary))] to-[hsl(var(--primary-hover))] text-white shadow-lg shadow-[hsl(var(--primary)/0.3)]'
          : 'text-muted-foreground hover:text-foreground hover:bg-[hsl(var(--secondary))]'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </Link>
  );
}
