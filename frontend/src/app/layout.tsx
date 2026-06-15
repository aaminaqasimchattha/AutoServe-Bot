'use client';

import { Inter } from 'next/font/google';
import './globals.css';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
});

function NavBar() {
  const pathname = usePathname();

  const links = [
    {
      href: '/',
      label: 'Knowledge Base',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7L12 12L22 7L12 2Z"/>
          <path d="M2 17L12 22L22 17"/>
          <path d="M2 12L12 17L22 12"/>
        </svg>
      ),
    },
    {
      href: '/dashboard',
      label: 'Records',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/>
          <path d="M3 9h18M9 21V9"/>
        </svg>
      ),
    },
    {
      href: '/analytics',
      label: 'Analytics',
      icon: (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="20" x2="18" y2="10"/>
          <line x1="12" y1="20" x2="12" y2="4"/>
          <line x1="6" y1="20" x2="6" y2="14"/>
        </svg>
      ),
    },
  ];

  return (
    <header className="border-b border-border/50 backdrop-blur-md bg-background/70 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center gap-6">
        {/* Brand */}
        <div className="flex items-center gap-3 mr-4">
          <div className="p-2 rounded-xl" style={{ background: 'hsl(var(--primary)/0.15)', boxShadow: '0 0 16px hsl(var(--primary)/0.2)' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 17L12 22L22 17" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="hsl(var(--primary))" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-bold text-foreground tracking-tight leading-none">AutoServe</p>
            <p style={{ fontSize: '0.65rem', color: 'hsl(var(--muted-foreground))' }}>Admin Dashboard</p>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex items-center gap-1">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`nav-link${pathname === link.href ? ' active' : ''}`}
            >
              {link.icon}
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Live indicator */}
        <div className="ml-auto flex items-center gap-2">
          <span className="pulse-dot"/>
          <span style={{ fontSize: '0.7rem', color: 'hsl(var(--muted-foreground))' }}>Live</span>
        </div>
      </div>
    </header>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <head>
        <title>AutoServe Bot — Admin Dashboard</title>
        <meta name="description" content="AutoServe Bot admin panel — manage knowledge base, view orders, transactions, customers, and analytics." />
      </head>
      <body className="min-h-full flex flex-col font-inter">
        <NavBar />
        {children}
      </body>
    </html>
  );
}
