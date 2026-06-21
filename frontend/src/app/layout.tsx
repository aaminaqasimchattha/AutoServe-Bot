import { Inter } from 'next/font/google';
import './globals.css';
import { NavBar } from '@/components/navbar';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} suppressHydrationWarning>
      <head>
        <title>AutoServe Bot — Admin Dashboard</title>
        <meta name="description" content="AutoServe Bot admin panel — manage knowledge base, view orders, transactions, customers, and analytics." />
      </head>
      <body className="min-h-full flex flex-col font-inter" suppressHydrationWarning>
        <NavBar />
        {children}
      </body>
    </html>
  );
}
