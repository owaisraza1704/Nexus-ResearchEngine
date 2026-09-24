import { useState } from 'react';
import { useNavigate } from 'react-router';
import { FileText, Upload, CheckCircle2, Loader2, AlertCircle, Plus, Search, Filter, X } from 'lucide-react';

const SOURCES = [
  { id: 'src-001', name: 'architecture.pdf', type: 'PDF', pages: 42, chunks: 128, status: 'READY', version: 'v1', date: '2026-09-22', size: '2.4 MB', parser: 'pypdf2', parserVersion: '3.0.1', embeddingStatus: 'COMPLETE' },
  { id: 'src-002', name: 'research-paper.pdf', type: 'PDF', pages: 28, chunks: 84, status: 'READY', version: 'v1', date: '2026-09-21', size: '1.1 MB', parser: 'pypdf2', parserVersion: '3.0.1', embeddingStatus: 'COMPLETE' },
  { id: 'src-003', name: 'design-notes.docx', type: 'DOCX', pages: 15, chunks: 47, status: 'READY', version: 'v2', date: '2026-09-20', size: '0.8 MB', parser: 'python-docx', parserVersion: '0.8.11', embeddingStatus: 'COMPLETE' },
  { id: 'src-004', name: 'retrieval-eval.pdf', type: 'PDF', pages: 61, chunks: 0, status: 'PROCESSING', version: 'v1', date: '2026-09-24', size: '3.2 MB', parser: 'pypdf2', parserVersion: '3.0.1', embeddingStatus: 'PENDING' },
  { id: 'src-005', name: 'legacy-spec.docx', type: 'DOCX', pages: 8, chunks: 0, status: 'FAILED', version: 'v1', date: '2026-09-19', size: '0.3 MB', parser: 'python-docx', parserVersion: '0.8.11', embeddingStatus: 'FAILED' },
];

const STATUS_MAP = {
  READY: { label: 'READY', color: '#22c55e', bg: 'rgba(34,197,94,0.1)', icon: CheckCircle2 },
  PROCESSING: { label: 'PROCESSING', color: '#3b9eff', bg: 'rgba(59,158,255,0.1)', icon: Loader2 },
  FAILED: { label: 'FAILED', color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: AlertCircle },
};

export default function SourceLibrary() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('ALL');

  const filtered = SOURCES.filter(s => {
    const matchSearch = s.name.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'ALL' || s.status === filter;
    return matchSearch && matchFilter;
  });

  const stats = {
    total: SOURCES.length,
    ready: SOURCES.filter(s => s.status === 'READY').length,
    totalChunks: SOURCES.reduce((a, s) => a + s.chunks, 0),
    totalPages: SOURCES.reduce((a, s) => a + s.pages, 0),
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ maxWidth: 1100, width: '100%', margin: '0 auto', padding: '36px 32px 80px' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 32 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#55535d', textTransform: 'uppercase', marginBottom: 6 }}>
              Sources
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 300, letterSpacing: -0.5, color: '#f0ede8', margin: 0 }}>
              Research Corpus
            </h1>
          </div>
          <button style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '8px 16px', borderRadius: 6,
            background: 'linear-gradient(135deg, #3b9eff 0%, #2a7fdf 100%)',
            border: 'none', cursor: 'pointer', color: '#fff', fontSize: 13, fontWeight: 600,
          }}>
            <Upload size={13} />
            Upload Document
          </button>
        </div>

        {/* Stats */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 28 }}>
          {[
            { label: 'Documents', value: stats.total },
            { label: 'Ready', value: stats.ready },
            { label: 'Total Pages', value: stats.totalPages },
            { label: 'Total Chunks', value: stats.totalChunks },
          ].map(({ label, value }) => (
            <div key={label} style={{
              background: '#111116', border: '1px solid #1e1e26', borderRadius: 7,
              padding: '14px 18px',
            }}>
              <div style={{ fontSize: 10, color: '#55535d', fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 6 }}>
                {label}
              </div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#f0ede8', fontFamily: 'var(--font-mono, monospace)', letterSpacing: -0.5 }}>
                {value.toLocaleString()}
              </div>
            </div>
          ))}
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
          <div style={{
            flex: 1, display: 'flex', alignItems: 'center', gap: 8,
            background: '#111116', border: '1px solid #1e1e26', borderRadius: 6, padding: '8px 12px',
          }}>
            <Search size={13} color="#55535d" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Filter documents..."
              style={{ flex: 1, background: 'none', border: 'none', outline: 'none', fontSize: 13, color: '#f0ede8', fontFamily: 'inherit' }}
            />
            {search && <button onClick={() => setSearch('')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d' }}><X size={13} /></button>}
          </div>

          <div style={{ display: 'flex', gap: 4 }}>
            {['ALL', 'READY', 'PROCESSING', 'FAILED'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '6px 12px', borderRadius: 5, fontSize: 11.5, cursor: 'pointer',
                  background: filter === f ? '#1e1e27' : 'transparent',
                  border: `1px solid ${filter === f ? '#2c2c3a' : 'transparent'}`,
                  color: filter === f ? '#f0ede8' : '#55535d',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Source table */}
        <div style={{ background: '#111116', border: '1px solid #1e1e26', borderRadius: 8, overflow: 'hidden' }}>
          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '2fr 80px 80px 80px 120px 80px 100px',
            padding: '10px 18px', borderBottom: '1px solid #1e1e26',
          }}>
            {['Document', 'Type', 'Pages', 'Chunks', 'Status', 'Version', 'Created'].map(h => (
              <div key={h} style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.6, color: '#55535d', textTransform: 'uppercase' }}>
                {h}
              </div>
            ))}
          </div>

          {/* Rows */}
          {filtered.map((src, i) => {
            const sc = STATUS_MAP[src.status as keyof typeof STATUS_MAP];
            const Icon = sc.icon;
            return (
              <div
                key={src.id}
                onClick={() => navigate(`/sources/${src.id}`)}
                style={{
                  display: 'grid', gridTemplateColumns: '2fr 80px 80px 80px 120px 80px 100px',
                  padding: '14px 18px', cursor: 'pointer', transition: 'background 120ms',
                  borderBottom: i < filtered.length - 1 ? '1px solid #1e1e26' : 'none',
                  alignItems: 'center',
                }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#17171d'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 5,
                    background: src.type === 'PDF' ? 'rgba(239,68,68,0.1)' : 'rgba(96,165,250,0.1)',
                    border: `1px solid ${src.type === 'PDF' ? 'rgba(239,68,68,0.2)' : 'rgba(96,165,250,0.2)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    <FileText size={14} color={src.type === 'PDF' ? '#ef4444' : '#60a5fa'} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13.5, color: '#f0ede8', fontWeight: 400 }}>{src.name}</div>
                    <div style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{src.id}</div>
                  </div>
                </div>

                <div style={{ fontSize: 11.5, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{src.type}</div>
                <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{src.pages}</div>
                <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>
                  {src.chunks > 0 ? src.chunks : '—'}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Icon size={11} color={sc.color} style={src.status === 'PROCESSING' ? { animation: 'spin 1s linear infinite' } : {}} />
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                    color: sc.color, background: sc.bg,
                    padding: '2px 6px', borderRadius: 3,
                  }}>{sc.label}</span>
                </div>

                <div style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{src.version}</div>
                <div style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{src.date}</div>
              </div>
            );
          })}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
