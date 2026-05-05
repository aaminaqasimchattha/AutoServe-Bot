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
    <aside className="w-64 bg-sidebar border-r border-border h-screen flex flex-col">
      {/* Logo Section */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-linear-to-br from-primary to-accent flex items-center justify-center shadow-lg shadow-primary/30">
            <Bot className="text-white" size={22} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-foreground tracking-tight">
              AutoServe
            </h1>
            <p className="text-xs text-primary font-medium">
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
      <div className="p-4 border-t border-border space-y-3">
        <div className="flex items-center gap-3 px-3">
          <div className="w-10 h-10 rounded-full bg-linear-to-br from-accent to-primary flex items-center justify-center shrink-0 shadow-md">
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
        <button className="w-full flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-all duration-200">
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
          ? 'bg-linear-to-br from-primary to-primary-hover text-white shadow-lg shadow-primary/30'
          : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
      }`}
    >
      {icon}
      <span className="text-sm font-medium">{label}</span>
    </Link>
  );
}
