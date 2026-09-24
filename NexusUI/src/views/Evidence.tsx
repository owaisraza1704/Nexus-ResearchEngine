'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';

const EVIDENCE = [
  { id: 'E001', source: 'architecture.pdf', doc: 'architecture.pdf', page: 7, chunk: 18, score: 0.94, claim: 'Encoder-only architectures use bidirectional attention', status: 'SUPPORTED', run: 'run-001' },
  { id: 'E002', source: 'architecture.pdf', doc: 'architecture.pdf', page: 14, chunk: 42, score: 0.91, claim: 'Decoder-only models apply causal masking to restrict attention to preceding tokens', status: 'SUPPORTED', run: 'run-001' },
  { id: 'E003', source: 'research-paper.pdf', doc: 'research-paper.pdf', page: 3, chunk: 7, score: 0.88, claim: 'Cross-attention bridges encoder representation and autoregressive decoder', status: 'SUPPORTED', run: 'run-001' },
  { id: 'E004', source: 'research-paper.pdf', doc: 'research-paper.pdf', page: 11, chunk: 31, score: 0.85, claim: 'Decoder-only models achieve competitive understanding performance at scale', status: 'PARTIALLY_SUPPORTED', run: 'run-001' },
  { id: 'E005', source: 'design-notes.docx', doc: 'design-notes.docx', page: 2, chunk: 5, score: 0.72, claim: 'Retrieval-augmented generation improves factual accuracy over base models', status: 'SUPPORTED', run: 'run-003' },
  { id: 'E006', source: 'architecture.pdf', doc: 'architecture.pdf', page: 22, chunk: 67, score: 0.61, claim: 'Sparse attention reduces quadratic complexity for long-context models', status: 'UNRESOLVED', run: 'run-003' },
];

const STATUS_STYLES = {
  SUPPORTED: { color: '#22c55e', label: 'SUPPORTED' },
  PARTIALLY_SUPPORTED: { color: '#f59e0b', label: 'PARTIAL' },
  CONTRADICTED: { color: '#ef4444', label: 'CONTRADICTED' },
  UNRESOLVED: { color: '#55535d', label: 'UNRESOLVED' },
};

export default function Evidence() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selected, setSelected] = useState<typeof EVIDENCE[0] | null>(EVIDENCE[0]);

  const filtered = EVIDENCE.filter(e => {
    const matchSearch = search === '' || e.claim.toLowerCase().includes(search.toLowerCase()) || e.source.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'ALL' || e.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '28px 28px 0', borderBottom: '1px solid #1e1e26', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#55535d', textTransform: 'uppercase', marginBottom: 6 }}>
          Evidence
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 300, letterSpacing: -0.5, color: '#f0ede8', margin: '0 0 20px' }}>
          Evidence Explorer
        </h1>

        <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center' }}>
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', gap: 8,
            background: '#111116', border: '1px solid #1e1e26', borderRadius: 6, padding: '7px 12px',
          }}>
            <Search size={13} color="#55535d" />
            <input
              value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search claims, sources..."
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 13, color: '#f0ede8', fontFamily: 'inherit' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['ALL', 'SUPPORTED', 'PARTIALLY_SUPPORTED', 'UNRESOLVED'].map(f => (
              <button key={f} onClick={() => setStatusFilter(f)} style={{
                padding: '5px 10px', borderRadius: 5, fontSize: 11, cursor: 'pointer',
                background: statusFilter === f ? '#1e1e27' : 'transparent',
                border: `1px solid ${statusFilter === f ? '#2c2c3a' : 'transparent'}`,
                color: statusFilter === f ? '#f0ede8' : '#55535d',
              }}>
                {f === 'PARTIALLY_SUPPORTED' ? 'PARTIAL' : f}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: selected ? '1fr 300px' : '1fr', overflow: 'hidden' }}>
        {/* List */}
        <div style={{ overflowY: 'auto', padding: '12px 28px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {filtered.map(ev => {
              const sc = STATUS_STYLES[ev.status as keyof typeof STATUS_STYLES];
              const isSelected = selected?.id === ev.id;
              return (
                <div
                  key={ev.id}
                  onClick={() => setSelected(s => s?.id === ev.id ? null : ev)}
                  style={{
                    padding: '14px 16px', borderRadius: 7, cursor: 'pointer',
                    background: isSelected ? '#111116' : 'transparent',
                    border: `1px solid ${isSelected ? '#2c2c3a' : '#1e1e26'}`,
                    transition: 'all 120ms',
                  }}
                  onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = '#111116'; }}
                  onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, color: '#3b9eff' }}>{ev.id}</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: sc.color, background: `${sc.color}18`, padding: '2px 5px', borderRadius: 3 }}>
                        {sc.label}
                      </span>
                    </div>
                    <span style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>score {ev.score}</span>
                  </div>
                  <div style={{ fontSize: 13.5, color: '#f0ede8', marginBottom: 6, lineHeight: 1.4 }}>{ev.claim}</div>
                  <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                    <span>{ev.source}</span>
                    <span>p.{ev.page}</span>
                    <span>chunk {ev.chunk}</span>
                    <span>→ {ev.run}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Provenance Inspector */}
        {selected && (
          <div style={{ borderLeft: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 16px' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 16 }}>
              Provenance Chain
            </div>

            {[
              { label: 'Evidence', value: selected.id, color: '#3b9eff' },
              { label: 'Source', value: selected.source, color: '#60a5fa' },
              { label: 'Document', value: selected.doc, color: '#8b8897' },
              { label: 'Page', value: `Page ${selected.page}`, color: '#8b8897' },
              { label: 'Chunk', value: `Chunk ${String(selected.chunk).padStart(3, '0')}`, color: '#8b8897' },
              { label: 'Research Run', value: selected.run, color: '#55535d' },
            ].map((item, i) => (
              <div key={item.label}>
                <div style={{ padding: '10px 12px', background: '#111116', border: '1px solid #1e1e26', borderRadius: 5 }}>
                  <div style={{ fontSize: 9.5, color: '#55535d', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 3 }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: 12, color: item.color, fontFamily: 'var(--font-mono, monospace)' }}>{item.value}</div>
                </div>
                {i < 5 && <div style={{ display: 'flex', justifyContent: 'center', padding: '3px 0' }}><div style={{ width: 1, height: 10, background: '#1e1e26' }} /></div>}
              </div>
            ))}

            <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
            <div style={{ fontSize: 10, color: '#55535d', fontWeight: 600, marginBottom: 6 }}>Claim</div>
            <div style={{ fontSize: 12.5, color: '#8b8897', lineHeight: 1.6, fontStyle: 'italic' }}>
              "{selected.claim}"
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
