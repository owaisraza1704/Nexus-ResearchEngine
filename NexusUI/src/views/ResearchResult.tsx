'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ChevronLeft, FileText, CheckCircle2, X, ArrowRight, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useResearch } from '@/components/ResearchStore';

const CITATIONS = [
  {
    id: 'C1', source: 'architecture.pdf', page: 7, chunk: 18, score: 0.94,
    excerpt: 'Encoder-only architectures use bidirectional attention, processing all tokens simultaneously. This enables full context awareness but prevents autoregressive generation.',
  },
  {
    id: 'C3', source: 'architecture.pdf', page: 14, chunk: 42, score: 0.91,
    excerpt: 'Decoder-only models apply causal masking to the attention mechanism, restricting each token to attend only to preceding positions. This constraint enables token-by-token generation at inference time.',
  },
  {
    id: 'C5', source: 'research-paper.pdf', page: 3, chunk: 7, score: 0.88,
    excerpt: 'The cross-attention mechanism in encoder-decoder architectures creates a bridge between the encoded representation and the autoregressive decoder, allowing the model to condition generation on the full source context.',
  },
  {
    id: 'C7', source: 'research-paper.pdf', page: 11, chunk: 31, score: 0.85,
    excerpt: 'Scaling laws suggest that decoder-only models achieve competitive performance on understanding tasks despite the architectural constraint, provided sufficient parameter count and training data.',
  },
];

const ANSWER = `Transformer attention mechanisms differ fundamentally between encoder-only and decoder-only architectures in two dimensions: **directionality** and **purpose**.

Encoder-only architectures (e.g., BERT) apply **bidirectional self-attention** [C1], allowing each token to attend to all other tokens in the sequence simultaneously. This full-context attention produces rich contextual representations optimal for classification and extraction tasks, but cannot generate sequences autoregressively.

Decoder-only architectures (e.g., GPT) apply **causal (masked) self-attention** [C3], where each token can only attend to positions that precede it in the sequence. This constraint is enforced via an attention mask that sets future positions to −∞ before softmax, effectively preventing information flow from future tokens.

Encoder-decoder architectures (e.g., T5, BART) combine both mechanisms: the encoder uses bidirectional attention to encode the source, while the decoder uses causal self-attention plus cross-attention [C5] to attend to the encoder output.

Despite the architectural constraint, decoder-only models have demonstrated competitive performance on understanding tasks at sufficient scale [C7], which has contributed to their dominance in large language model research.`;

const EVIDENCE = [
  { id: 'E1', citation: 'C1', claim: 'Encoder-only architectures use bidirectional attention', status: 'SUPPORTED', source: 'architecture.pdf', page: 7, chunk: 18, score: 0.94 },
  { id: 'E3', citation: 'C3', claim: 'Decoder-only models apply causal masking', status: 'SUPPORTED', source: 'architecture.pdf', page: 14, chunk: 42, score: 0.91 },
  { id: 'E5', citation: 'C5', claim: 'Cross-attention bridges encoder and decoder', status: 'SUPPORTED', source: 'research-paper.pdf', page: 3, chunk: 7, score: 0.88 },
  { id: 'E7', citation: 'C7', claim: 'Decoder-only models achieve competitive understanding performance', status: 'PARTIALLY_SUPPORTED', source: 'research-paper.pdf', page: 11, chunk: 31, score: 0.85 },
];

const STATUS_STYLE = {
  SUPPORTED: { color: '#22c55e', label: 'SUPPORTED' },
  PARTIALLY_SUPPORTED: { color: '#f59e0b', label: 'PARTIAL' },
  CONTRADICTED: { color: '#ef4444', label: 'CONTRADICTED' },
  UNRESOLVED: { color: '#55535d', label: 'UNRESOLVED' },
};

function renderAnswer(text: string, activeCitation: string | null, onCite: (id: string) => void) {
  const parts = text.split(/(\[C\d+\])/g);
  return parts.map((part, i) => {
    const match = part.match(/^\[C(\d+)\]$/);
    if (match) {
      const id = `C${match[1]}`;
      return (
        <button
          key={i}
          onClick={() => onCite(id)}
          style={{
            display: 'inline-flex', alignItems: 'center',
            background: activeCitation === id ? 'rgba(59,158,255,0.18)' : 'rgba(59,158,255,0.1)',
            border: `1px solid ${activeCitation === id ? 'rgba(59,158,255,0.5)' : 'rgba(59,158,255,0.25)'}`,
            borderRadius: 4, padding: '0 5px', fontSize: 11,
            color: '#3b9eff', cursor: 'pointer', fontWeight: 600,
            margin: '0 1px', verticalAlign: 'middle',
            transition: 'all 120ms',
          }}
        >
          {part}
        </button>
      );
    }
    return <span key={i} dangerouslySetInnerHTML={{ __html: part.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }} />;
  });
}

export default function ResearchResult() {
  const { runId } = useParams<{ runId: string }>();
  const research = useResearch();
  const router = useRouter();
  const [tab, setTab] = useState<'answer' | 'evidence' | 'sources'>('answer');
  const [activeCitation, setActiveCitation] = useState<string | null>(null);

  const activeCite = activeCitation ? CITATIONS.find(c => c.id === activeCitation) : null;
  const run = research.runs.find(item => item.id === runId);

  if (!run) {
    return (
      <section className="research-empty">
        <h1>Run not found</h1>
        <p>This run does not belong to this research.</p>
        <Link className="ui-button" href={`/research/${research.id}/runs`}>Back to research runs</Link>
      </section>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div className="preview-notice">Sample result for this research · not generated from your current draft</div>
      {/* Header */}
      <div style={{
        borderBottom: '1px solid #1e1e26', padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      }}>
        <button
          onClick={() => router.push(`/research/${research.id}/runs`)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d', display: 'flex', gap: 4, alignItems: 'center' }}
        >
          <ChevronLeft size={14} />
          <span style={{ fontSize: 12 }}>Research runs</span>
        </button>
        <span style={{ color: '#2c2c3a' }}>/</span>
        <span style={{ fontSize: 12, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{run.id}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, color: '#22c55e', background: 'rgba(34,197,94,0.1)', padding: '2px 6px', borderRadius: 3 }}>
            COMPLETED
          </span>
          <span style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>3.2s · 3 src · 4 citations</span>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: activeCitation ? '1fr 320px' : '1fr', overflow: 'hidden' }}>

        {/* Main */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Research question */}
          <div style={{ padding: '28px 40px 0', borderBottom: '1px solid #1e1e26' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, color: '#55535d', textTransform: 'uppercase', marginBottom: 10 }}>
              Research Question
            </div>
            <h2 style={{ fontSize: 20, fontWeight: 400, letterSpacing: -0.4, color: '#f0ede8', margin: '0 0 20px', lineHeight: 1.3 }}>
              {run.question}
            </h2>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 0 }}>
              {(['answer', 'evidence', 'sources'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  style={{
                    padding: '10px 16px', background: 'none', border: 'none',
                    borderBottom: tab === t ? '2px solid #3b9eff' : '2px solid transparent',
                    cursor: 'pointer', fontSize: 13,
                    color: tab === t ? '#3b9eff' : '#55535d',
                    textTransform: 'capitalize', fontFamily: 'inherit',
                    marginBottom: -1,
                  }}
                >
                  {t === 'answer' ? 'Answer' : t === 'evidence' ? `Evidence (${EVIDENCE.length})` : `Sources (3)`}
                </button>
              ))}
            </div>
          </div>

          <div style={{ padding: '28px 40px', flex: 1 }}>
            {tab === 'answer' && (
              <>
                <div style={{ fontSize: 14.5, color: '#c8c4be', lineHeight: 1.9, letterSpacing: -0.05, maxWidth: 680 }}>
                  {renderAnswer(ANSWER, activeCitation, (id) => setActiveCitation(c => c === id ? null : id))}
                </div>

                <div style={{ marginTop: 28, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: '#55535d' }}>Citations:</span>
                  {CITATIONS.map(c => (
                    <button
                      key={c.id}
                      onClick={() => setActiveCitation(a => a === c.id ? null : c.id)}
                      style={{
                        padding: '3px 8px', borderRadius: 4, fontSize: 11.5, cursor: 'pointer',
                        background: activeCitation === c.id ? 'rgba(59,158,255,0.15)' : 'rgba(59,158,255,0.07)',
                        border: `1px solid ${activeCitation === c.id ? 'rgba(59,158,255,0.4)' : 'rgba(59,158,255,0.15)'}`,
                        color: '#3b9eff', fontWeight: 600,
                      }}
                    >
                      [{c.id}]
                    </button>
                  ))}
                </div>
              </>
            )}

            {tab === 'evidence' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {EVIDENCE.map(ev => {
                  const sc = STATUS_STYLE[ev.status as keyof typeof STATUS_STYLE];
                  return (
                    <div key={ev.id} style={{
                      padding: '14px 16px', background: '#111116',
                      border: '1px solid #1e1e26', borderRadius: 7,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, color: '#3b9eff' }}>{ev.id}</span>
                          <span style={{ fontSize: 10, fontWeight: 700, color: sc.color, background: `${sc.color}18`, padding: '2px 5px', borderRadius: 3 }}>
                            {sc.label}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          score {ev.score}
                        </div>
                      </div>
                      <div style={{ fontSize: 13, color: '#f0ede8', marginBottom: 8 }}>{ev.claim}</div>
                      <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                        <span>{ev.source}</span>
                        <span>p.{ev.page}</span>
                        <span>chunk {ev.chunk}</span>
                        <span>→ [{ev.citation}]</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {tab === 'sources' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  { name: 'architecture.pdf', type: 'PDF', pages: 42, hits: 3, used: true },
                  { name: 'research-paper.pdf', type: 'PDF', pages: 28, hits: 2, used: true },
                  { name: 'design-notes.docx', type: 'DOCX', pages: 15, hits: 0, used: false },
                ].map(src => (
                  <div key={src.name} style={{
                    padding: '12px 16px', background: '#111116',
                    border: '1px solid #1e1e26', borderRadius: 7,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <FileText size={14} color={src.used ? '#60a5fa' : '#2c2c3a'} />
                      <div>
                        <div style={{ fontSize: 13, color: src.used ? '#f0ede8' : '#55535d' }}>{src.name}</div>
                        <div style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          {src.pages} pages · {src.hits} retrieval hits
                        </div>
                      </div>
                    </div>
                    <span style={{
                      fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                      color: src.used ? '#22c55e' : '#55535d',
                      background: src.used ? 'rgba(34,197,94,0.1)' : '#1e1e27',
                      padding: '2px 6px', borderRadius: 3,
                    }}>
                      {src.used ? 'USED' : 'SEARCHED'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right — Evidence Inspector */}
        {activeCite && (
          <div style={{ borderLeft: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 18px', background: '#0c0c0e' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase' }}>
                Evidence Inspector
              </span>
              <button
                onClick={() => setActiveCitation(null)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d' }}
              >
                <X size={13} />
              </button>
            </div>

            {/* Provenance chain */}
            {[
              { label: 'Citation', value: `[${activeCite.id}]`, color: '#3b9eff' },
              { label: 'Source', value: activeCite.source, color: '#60a5fa' },
              { label: 'Page', value: `Page ${activeCite.page}`, color: '#8b8897' },
              { label: 'Chunk', value: `Chunk ${String(activeCite.chunk).padStart(3, '0')}`, color: '#8b8897' },
            ].map((item, i) => (
              <div key={item.label}>
                <div style={{
                  padding: '12px 14px', background: '#111116',
                  border: '1px solid #1e1e26', borderRadius: 6,
                }}>
                  <div style={{ fontSize: 9.5, color: '#55535d', fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 4 }}>
                    {item.label}
                  </div>
                  <div style={{ fontSize: 13, color: item.color, fontFamily: 'var(--font-mono, monospace)', fontWeight: 500 }}>
                    {item.value}
                  </div>
                </div>
                {i < 3 && (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
                    <div style={{ width: 1, height: 12, background: '#1e1e26' }} />
                  </div>
                )}
              </div>
            ))}

            <div style={{ height: 1, background: '#1e1e26', margin: '16px 0' }} />

            <div style={{ fontSize: 10, color: '#55535d', fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 8 }}>
              Relevant Excerpt
            </div>
            <div style={{
              fontSize: 12.5, color: '#8b8897', lineHeight: 1.7,
              padding: 12, background: '#17171d',
              border: '1px solid #1e1e26', borderRadius: 6,
              fontStyle: 'italic',
            }}>
              "{activeCite.excerpt}"
            </div>

            <div style={{ marginTop: 12, display: 'flex', gap: 6 }}>
              <div style={{ flex: 1, padding: '8px 10px', background: '#111116', border: '1px solid #1e1e26', borderRadius: 5, textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: '#55535d', marginBottom: 2 }}>Retrieval Score</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#22c55e', fontFamily: 'var(--font-mono, monospace)' }}>
                  {activeCite.score}
                </div>
              </div>
              <div style={{ flex: 1, padding: '8px 10px', background: '#111116', border: '1px solid #1e1e26', borderRadius: 5, textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: '#55535d', marginBottom: 2 }}>Status</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#22c55e', letterSpacing: 0.4 }}>VALIDATED</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
