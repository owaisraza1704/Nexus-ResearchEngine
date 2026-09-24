'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Search, Brain, Zap, GitBranch, FlaskConical, Settings, Layers, ArrowRight } from 'lucide-react';
import { useResearch } from './ResearchStore';

const SCOPED_COMMANDS = [
  { label: 'Search Sources', icon: Search, to: '/sources', group: 'Navigate' },
  { label: 'Research Runs', icon: Zap, to: '/runs', group: 'Navigate' },
  { label: 'Evidence Explorer', icon: Search, to: '/evidence', group: 'Navigate' },
  { label: 'Reports', icon: Layers, to: '/reports', group: 'Navigate' },
  { label: 'Research Graph', icon: GitBranch, to: '/graph', group: 'Navigate' },
  { label: 'Evaluation', icon: FlaskConical, to: '/evaluation', group: 'Navigate' },
  { label: 'Settings', icon: Settings, to: '/settings', group: 'Navigate' },
] as const;

export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const research = useResearch();
  const commands = [
    { label: 'All research', icon: Layers, to: '/research' as const, group: 'Navigate' },
    { label: 'New Research', icon: Brain, to: '/research/new' as const, group: 'Actions' },
    ...SCOPED_COMMANDS.map(command => ({ ...command, to: `/research/${research.id}${command.to}` as const })),
  ];

  const filtered = commands.filter(c =>
    query === '' || c.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelected(s => Math.min(s + 1, filtered.length - 1)); }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
      if (e.key === 'Enter' && filtered[selected]) {
        router.push(filtered[selected].to);
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, selected, filtered, router, onClose]);

  if (!open) return null;

  const groups = Array.from(new Set(filtered.map(c => c.group)));

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9999,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
        paddingTop: '18vh',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 560, maxWidth: 'calc(100vw - 32px)', background: '#17171d',
          border: '1px solid #2c2c3a', borderRadius: 10,
          overflow: 'hidden', boxShadow: '0 24px 48px rgba(0,0,0,0.5)',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Search input */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 16px', borderBottom: '1px solid #1e1e26',
        }}>
          <Search size={15} color="#55535d" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0); }}
            placeholder="Search commands..."
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              fontSize: 14, color: '#f0ede8', fontFamily: 'inherit',
            }}
          />
          <kbd style={{
            fontSize: 10, fontFamily: 'var(--font-mono, monospace)',
            background: '#1e1e27', border: '1px solid #2c2c3a',
            padding: '2px 6px', borderRadius: 4, color: '#55535d',
          }}>ESC</kbd>
        </div>

        {/* Results */}
        <div style={{ maxHeight: 320, overflowY: 'auto', padding: '6px 0' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: '#55535d', fontSize: 13 }}>
              No commands found
            </div>
          ) : groups.map(group => (
            <div key={group}>
              <div style={{
                padding: '6px 16px 3px',
                fontSize: 10, fontWeight: 600, letterSpacing: 0.8,
                color: '#55535d', textTransform: 'uppercase',
              }}>{group}</div>
              {filtered.filter(c => c.group === group).map((cmd, i) => {
                const globalIdx = filtered.indexOf(cmd);
                const Icon = cmd.icon;
                return (
                  <button
                    key={cmd.label}
                    onMouseEnter={() => setSelected(globalIdx)}
                    onClick={() => { router.push(cmd.to); onClose(); }}
                    style={{
                      width: '100%', padding: '8px 16px',
                      background: globalIdx === selected ? 'rgba(59,158,255,0.08)' : 'transparent',
                      border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      color: globalIdx === selected ? '#f0ede8' : '#8b8897',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Icon size={14} color={globalIdx === selected ? '#3b9eff' : '#55535d'} />
                      <span style={{ fontSize: 13 }}>{cmd.label}</span>
                    </div>
                    <ArrowRight size={12} color={globalIdx === selected ? '#3b9eff' : 'transparent'} />
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
