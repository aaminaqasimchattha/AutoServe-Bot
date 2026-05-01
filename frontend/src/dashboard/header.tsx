'use client';

import { Bell, Search } from 'lucide-react';

export function Header() {
  return (
    <header className="bg-[hsl(var(--card)/0.6)] backdrop-blur-xl border-b border-[hsl(var(--border))] h-16 flex items-center justify-between px-8">
      {/* Search Bar */}
      <div className="flex-1 max-w-md">
        <div className="relative group">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-[hsl(var(--primary))] transition-colors"
            size={18}
          />
          <input
            type="text"
            placeholder="Search files, activity..."
            className="w-full pl-10 pr-4 py-2 bg-[hsl(var(--secondary))] text-foreground placeholder-[hsl(var(--muted-foreground))] rounded-xl border border-[hsl(var(--border))] focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary)/0.5)] focus:border-[hsl(var(--primary)/0.5)] transition-all duration-200"
            id="header-search"
          />
        </div>
      </div>

      {/* Right Section */}
      <div className="flex items-center gap-3 ml-8">
        {/* Notifications */}
        <button
          className="relative p-2.5 text-muted-foreground hover:text-foreground hover:bg-[hsl(var(--secondary))] rounded-xl transition-all duration-200"
          id="notifications-button"
        >
          <Bell size={20} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[hsl(var(--danger))] rounded-full ring-2 ring-[hsl(var(--card))]" />
        </button>

        {/* Status Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[hsl(var(--success)/0.1)] border border-[hsl(var(--success)/0.2)]">
          <div className="w-2 h-2 rounded-full bg-[hsl(var(--success))] animate-pulse" />
          <span className="text-xs font-medium text-[hsl(var(--success))]">
            Bot Online
          </span>
        </div>

        {/* User Avatar */}
        <div
          className="w-10 h-10 rounded-full bg-gradient-to-br from-[hsl(var(--primary))] to-[hsl(var(--accent))] flex items-center justify-center cursor-pointer hover:opacity-90 transition-opacity shadow-md"
          id="user-avatar"
        >
          <span className="text-white font-semibold text-sm">AQ</span>
        </div>
      </div>
    </header>
  );
}
