'use client';

import { useState, useEffect, type ReactNode } from 'react';
import Sidebar from './Sidebar';
import CommandPalette from './CommandPalette';
import { useResearch } from './ResearchStore';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function Layout({ children }: { children: ReactNode }) {
  const [cmdOpen, setCmdOpen] = useState(false);
  const research = useResearch();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div
      className="workspace-shell"
      style={{
        display: 'flex',
        height: '100dvh',
        background: '#0c0c0e',
        overflow: 'hidden',
      }}
    >
      <Sidebar onCmd={() => setCmdOpen(true)} />
      <main
        style={{
          flex: 1,
          minWidth: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <header className="workspace-header">
          <Link href="/research" aria-label="Back to all research" className="workspace-back">
            <ArrowLeft size={15} />
          </Link>
          <span className="workspace-title">{research.title}</span>
          <span className="local-badge">Local workspace</span>
        </header>
        {children}
      </main>
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  );
}
