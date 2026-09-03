import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Real-time Collaborative Document Editor',
  description: 'A real-time collaborative document editor built with Next.js, Yjs, and WebSockets',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}