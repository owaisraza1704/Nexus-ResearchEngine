import { useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { ChevronLeft, FileText, Hash, Layers, Copy, Cpu } from 'lucide-react';

const CHUNKS = Array.from({ length: 24 }, (_, i) => ({
  id: `chunk-${String(i + 1).padStart(3, '0')}`,
  index: i,
  page: Math.floor(i / 3) + 1,
  sequence: i + 1,
  tokenCount: 180 + Math.floor(Math.random() * 80),
  text: [
    'The attention mechanism computes queries, keys, and values from the input embeddings, enabling the model to selectively attend to relevant positions.',
    'Document chunking strategies must balance retrieval precision against context completeness. Overlapping chunks improve recall at the cost of redundancy.',
    'Vector similarity search relies on approximate nearest neighbor algorithms. HNSW and IVF-PQ are the dominant approaches for high-dimensional embeddings.',
    'Grounded answer generation requires strict citation validation. Each claim must be traceable to a specific document chunk via the evidence chain.',
    'The retrieval pipeline consists of query embedding, vector search, chunk retrieval, context assembly, and structured generation with citation constraints.',
    'Source coverage analysis determines which documents contributed evidence to the final answer. Sources with zero retrieval hits are flagged as searched but unused.',
  ][i % 6],
  highlighted: [2, 5, 11].includes(i),
}));

export default function DocumentInspector() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [selectedChunk, setSelectedChunk] = useState<number | null>(2);
  const [tab, setTab] = useState<'content' | 'chunks'>('chunks');

  const doc = {
    id: id || 'src-001',
    name: 'architecture.pdf',
    type: 'PDF',
    pages: 42,
    chunks: 128,
    version: 'v1',
    parser: 'pypdf2',
    parserVersion: '3.0.1',
    contentHash: 'sha256:a3f7c1d9e2b8...',
    normalizedText: 'COMPLETE',
    embeddingModel: 'text-embedding-ada-002',
    chunkSize: 256,
    chunkOverlap: 32,
    created: '2026-09-22T14:31:00Z',
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        borderBottom: '1px solid #1e1e26', padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
        background: '#0c0c0e',
      }}>
        <button
          onClick={() => navigate('/sources')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d', display: 'flex', gap: 4, alignItems: 'center' }}
        >
          <ChevronLeft size={14} />
          <span style={{ fontSize: 12 }}>Sources</span>
        </button>
        <span style={{ color: '#2c2c3a' }}>/</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={14} color="#60a5fa" />
          <span style={{ fontSize: 13.5, fontWeight: 500, color: '#f0ede8' }}>{doc.name}</span>
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color: '#22c55e',
            background: 'rgba(34,197,94,0.1)', padding: '2px 6px', borderRadius: 3,
          }}>READY</span>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '240px 1fr 280px', overflow: 'hidden' }}>

        {/* Left — Document Metadata */}
        <div style={{ borderRight: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 16px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 14 }}>
            Document Metadata
          </div>

          {[
            { label: 'Source ID', value: doc.id },
            { label: 'Version', value: doc.version },
            { label: 'Parser', value: doc.parser },
            { label: 'Parser Version', value: doc.parserVersion },
            { label: 'Pages', value: doc.pages },
            { label: 'Chunks', value: doc.chunks },
            { label: 'Chunk Size', value: `${doc.chunkSize} tokens` },
            { label: 'Overlap', value: `${doc.chunkOverlap} tokens` },
            { label: 'Normalized Text', value: doc.normalizedText },
            { label: 'Content Hash', value: doc.contentHash, mono: true, truncate: true },
            { label: 'Embedding Model', value: doc.embeddingModel },
            { label: 'Created', value: '2026-09-22 14:31' },
          ].map(({ label, value, mono, truncate }) => (
            <div key={label} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: '#55535d', fontWeight: 500, letterSpacing: 0.4, marginBottom: 2 }}>
                {label}
              </div>
              <div style={{
                fontSize: mono ? 11 : 12,
                fontFamily: mono ? 'var(--font-mono, monospace)' : 'inherit',
                color: '#8b8897',
                overflow: truncate ? 'hidden' : undefined,
                textOverflow: truncate ? 'ellipsis' : undefined,
                whiteSpace: truncate ? 'nowrap' : undefined,
              }}>
                {String(value)}
              </div>
            </div>
          ))}
        </div>

        {/* Center — Content / Chunks List */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Tabs */}
          <div style={{
            display: 'flex', borderBottom: '1px solid #1e1e26', padding: '0 20px', flexShrink: 0,
          }}>
            {(['chunks', 'content'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: '12px 14px', background: 'none', border: 'none',
                  borderBottom: tab === t ? '2px solid #3b9eff' : '2px solid transparent',
                  cursor: 'pointer', fontSize: 13,
                  color: tab === t ? '#3b9eff' : '#55535d',
                  textTransform: 'capitalize', fontFamily: 'inherit',
                  marginBottom: -1,
                }}
              >
                {t === 'chunks' ? `Chunks (${doc.chunks})` : 'Content Preview'}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
            {tab === 'chunks' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {CHUNKS.map(chunk => (
                  <div
                    key={chunk.id}
                    onClick={() => setSelectedChunk(chunk.index)}
                    style={{
                      padding: '12px 14px', borderRadius: 6, cursor: 'pointer',
                      border: `1px solid ${selectedChunk === chunk.index ? 'rgba(59,158,255,0.3)' : chunk.highlighted ? 'rgba(59,158,255,0.15)' : '#1e1e26'}`,
                      background: selectedChunk === chunk.index ? 'rgba(59,158,255,0.06)' : chunk.highlighted ? 'rgba(59,158,255,0.03)' : '#111116',
                      transition: 'all 120ms',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, color: '#3b9eff' }}>
                          Chunk {String(chunk.index + 1).padStart(3, '0')}
                        </span>
                        <span style={{ fontSize: 10, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          Page {chunk.page} · Seq {chunk.sequence}
                        </span>
                      </div>
                      <span style={{ fontSize: 10, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                        {chunk.tokenCount}t
                      </span>
                    </div>
                    <div style={{
                      fontSize: 12, color: '#8b8897', lineHeight: 1.55,
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                    }}>
                      {chunk.text}
                    </div>
                    {chunk.highlighted && (
                      <div style={{ marginTop: 6, fontSize: 10, color: '#3b9eff' }}>
                        ↳ Referenced in 3 retrievals
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: '#8b8897', lineHeight: 1.8 }}>
                <p>Page 1 — Document content preview would appear here. The normalized text extracted from the PDF is shown with page boundaries and section markers preserved.</p>
                <p>The document parser extracts text while preserving structural metadata including page numbers, section headings, and content type classifications.</p>
              </div>
            )}
          </div>
        </div>

        {/* Right — Chunk Inspector */}
        <div style={{ borderLeft: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 16px' }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 14 }}>
            Chunk Inspector
          </div>

          {selectedChunk !== null ? (
            <>
              {[
                { label: 'Chunk ID', value: CHUNKS[selectedChunk].id },
                { label: 'Page', value: CHUNKS[selectedChunk].page },
                { label: 'Sequence', value: CHUNKS[selectedChunk].sequence },
                { label: 'Tokens', value: CHUNKS[selectedChunk].tokenCount },
              ].map(({ label, value }) => (
                <div key={label} style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 10, color: '#55535d', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{value}</div>
                </div>
              ))}

              <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
              <div style={{ fontSize: 10, color: '#55535d', marginBottom: 8 }}>Excerpt</div>
              <div style={{
                fontSize: 12, color: '#8b8897', lineHeight: 1.65,
                padding: 12, background: '#17171d', borderRadius: 5,
                border: '1px solid #1e1e26',
              }}>
                "{CHUNKS[selectedChunk].text}"
              </div>

              {CHUNKS[selectedChunk].highlighted && (
                <>
                  <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
                  <div style={{ fontSize: 10, color: '#3b9eff', fontWeight: 600, marginBottom: 8, letterSpacing: 0.5 }}>
                    RETRIEVAL HITS
                  </div>
                  {['run-001', 'run-003'].map(r => (
                    <div key={r} style={{
                      fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)',
                      padding: '6px 8px', background: '#17171d', borderRadius: 4, marginBottom: 4,
                    }}>
                      {r} · score 0.91
                    </div>
                  ))}
                </>
              )}
            </>
          ) : (
            <div style={{ color: '#55535d', fontSize: 13 }}>Select a chunk to inspect</div>
          )}
        </div>
      </div>
    </div>
  );
}
