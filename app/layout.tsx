import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ASLS – Azimuth Offset Planner',
  description: 'GPS-based live wind and azimuth offset calculator for bipod rotation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
