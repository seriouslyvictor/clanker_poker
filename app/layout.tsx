import type { Metadata } from 'next';
import { Press_Start_2P, VT323, Rajdhani } from 'next/font/google';
import './globals.css';

const pressStart2P = Press_Start_2P({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-press-start',
});

const vt323 = VT323({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-vt323',
});

const rajdhani = Rajdhani({
  weight: ['600', '700'],
  subsets: ['latin'],
  variable: '--font-rajdhani',
});

export const metadata: Metadata = {
  title: '♠ IA Poker Battleground ♠',
  description: 'Watch AI models battle it out at the poker table',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${pressStart2P.variable} ${vt323.variable} ${rajdhani.variable}`}>
      <body style={{ fontFamily: 'var(--font-press-start), monospace' }}>
        {children}
      </body>
    </html>
  );
}
