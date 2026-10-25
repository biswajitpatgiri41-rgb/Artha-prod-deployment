import { ReactNode } from 'react';
import { Geist, JetBrains_Mono } from 'next/font/google';
import { AdminAuthProvider } from '@/lib/auth';
import './globals.css';

const geist = Geist({ subsets: ['latin'], display: 'swap', variable: '--font-geist' });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], display: 'swap', variable: '--font-jetbrains-mono' });

export const metadata = {
  title: 'INDIA MACRO AI - SYSTEM CONTROL',
  description: 'Agentic Monetary Policy Administration Terminal',
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className={`min-h-screen bg-admin-bg text-admin-text-primary font-sans antialiased ${geist.variable} ${jetbrainsMono.variable}`}>
        <AdminAuthProvider>
          {children}
        </AdminAuthProvider>
      </body>
    </html>
  );
}
