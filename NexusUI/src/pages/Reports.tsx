import { useState } from 'react';

const REPORT = {
  title: 'Attention Mechanism Comparison: Encoder-Only vs Decoder-Only Transformers',
  date: '2026-09-24',
  runId: 'run-001',
  sources: 3,
  citations: 7,
  sections: [
    {
      id: 'exec', title: 'Executive Summary', content: `Transformer attention mechanisms differ fundamentally between encoder-only and decoder-only architectures along two axes: directionality and generation capability. Encoder-only models apply bidirectional self-attention to build contextual representations, while decoder-only models apply causal masked attention to enable autoregressive token generation. These architectural constraints determine the optimal use cases for each paradigm. [C1][C3]`,
    },
    {
      id: 'findings', title: 'Key Findings', content: `1. Encoder-only architectures (BERT, RoBERTa) process tokens with full bidirectional context, making them optimal for classification and extraction tasks but incapable of generation. [C1]\n\n2. Decoder-only architectures (GPT family) restrict attention via causal masking, enabling autoregressive generation at the cost of full bidirectional context during encoding. [C3]\n\n3. Encoder-decoder architectures (T5, BART) combine both mechanisms through cross-attention, bridging source encoding with autoregressive decoding. [C5]\n\n4. At sufficient scale, decoder-only models have demonstrated competitive performance on traditional NLU benchmarks, reducing the architectural specialization advantage of encoder-only models. [C7]`,
    },
    {
      id: 'evidence', title: 'Evidence', content: `Four evidence items were retrieved and validated across three source documents. All primary claims are supported with retrieval scores above 0.85. One finding (decoder-only competitive performance) is classified as partially supported, as the supporting evidence is conditional on scale and training data quantity. [C7]`,
    },
    {
      id: 'gaps', title: 'Gaps', content: `The selected sources do not contain sufficient evidence on: (1) empirical benchmark comparisons at equivalent parameter counts between encoder-only and decoder-only models; (2) inference latency characteristics of each architecture class under production conditions. These gaps should be addressed in a follow-up research run with additional sources.`,
    },
    {
      id: 'conclusion', title: 'Conclusion', content: `The architectural divide between encoder-only and decoder-only transformers reflects a fundamental tradeoff between contextual representation quality and generative capability. The causal masking constraint in decoder-only models enables flexible generation but restricts the depth of bidirectional context available during encoding. As model scale increases, this distinction becomes less practically significant for understanding tasks, though the generative capability of decoder-only models remains an architectural property rather than an emergent one. [C1][C3][C5]`,
    },
  ],
};

const CITATIONS = [
  { id: 'C1', source: 'architecture.pdf', page: 7, chunk: 18, excerpt: 'Encoder-only architectures use bidirectional attention, processing all tokens simultaneously.' },
  { id: 'C3', source: 'architecture.pdf', page: 14, chunk: 42, excerpt: 'Decoder-only models apply causal masking to the attention mechanism, restricting each token to attend only to preceding positions.' },
  { id: 'C5', source: 'research-paper.pdf', page: 3, chunk: 7, excerpt: 'The cross-attention mechanism creates a bridge between the encoded representation and the autoregressive decoder.' },
  { id: 'C7', source: 'research-paper.pdf', page: 11, chunk: 31, excerpt: 'Scaling laws suggest that decoder-only models achieve competitive performance on understanding tasks despite the architectural constraint.' },
];

function renderContent(text: string, activeCite: string | null, onCite: (id: string) => void) {
  const parts = text.split(/(\[C\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[C(\d+)\]$/);
    if (m) {
      const id = `C${m[1]}`;
      return (
        <button key={i} onClick={() => onCite(id)} style={{
          display: 'inline', padding: '0 4px',
          background: activeCite === id ? 'rgba(59,158,255,0.18)' : 'rgba(59,158,255,0.08)',
          border: `1px solid ${activeCite === id ? 'rgba(59,158,255,0.5)' : 'rgba(59,158,255,0.2)'}`,
          borderRadius: 3, fontSize: 10.5, color: '#3b9eff', cursor: 'pointer', fontWeight: 700,
          verticalAlign: 'middle', margin: '0 1px',
        }}>{part}</button>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

export default function Reports() {
  const [activeSection, setActiveSection] = useState('exec');
  const [activeCite, setActiveCite] = useState<string | null>(null);

  const cite = activeCite ? CITATIONS.find(c => c.id === activeCite) : null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '180px 1fr', overflow: 'hidden' }}>
        {/* Sidebar — report TOC */}
        <div style={{ borderRight: '1px solid #1e1e26', overflowY: 'auto', padding: '24px 0' }}>
          <div style={{ padding: '0 16px', marginBottom: 12 }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase' }}>Report</div>
          </div>
          {REPORT.sections.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              style={{
                width: '100%', padding: '8px 16px',
                background: activeSection === s.id ? 'rgba(59,158,255,0.08)' : 'transparent',
                border: 'none', borderLeft: activeSection === s.id ? '2px solid #3b9eff' : '2px solid transparent',
                cursor: 'pointer', textAlign: 'left', fontSize: 12.5,
                color: activeSection === s.id ? '#f0ede8' : '#55535d',
                fontFamily: 'inherit',
              }}
            >
              {s.title}
            </button>
          ))}

          <div style={{ height: 1, background: '#1e1e26', margin: '12px 16px' }} />
          <div style={{ padding: '0 16px 4px' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 8 }}>Citations</div>
            {CITATIONS.map(c => (
              <button
                key={c.id}
                onClick={() => setActiveCite(a => a === c.id ? null : c.id)}
                style={{
                  display: 'block', width: '100%', padding: '5px 0',
                  background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left',
                  fontSize: 11.5, color: activeCite === c.id ? '#3b9eff' : '#55535d',
                  fontFamily: 'inherit',
                }}
              >
                [{c.id}]
              </button>
            ))}
          </div>
        </div>

        {/* Main report content */}
        <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Report header */}
          <div style={{ padding: '36px 48px 0', borderBottom: '1px solid #1e1e26' }}>
            <div style={{ fontSize: 10, color: '#55535d', fontFamily: 'var(--font-mono, monospace)', marginBottom: 10 }}>
              {REPORT.runId} · {REPORT.date} · {REPORT.sources} sources · {REPORT.citations} citations
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 400, letterSpacing: -0.6, color: '#f0ede8', margin: '0 0 24px', lineHeight: 1.3, maxWidth: 620 }}>
              {REPORT.title}
            </h1>
          </div>

          <div style={{ padding: '32px 48px', maxWidth: 720 }}>
            {REPORT.sections.map(section => (
              <div key={section.id} id={section.id} style={{ marginBottom: 40 }}>
                <h2 style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
                  color: '#55535d', margin: '0 0 14px', paddingBottom: 8,
                  borderBottom: '1px solid #1e1e26',
                }}>
                  {section.title}
                </h2>
                <div style={{ fontSize: 14, color: '#c8c4be', lineHeight: 1.85, whiteSpace: 'pre-line' }}>
                  {renderContent(section.content, activeCite, (id) => setActiveCite(a => a === id ? null : id))}
                </div>
              </div>
            ))}

            {/* Sources */}
            <div style={{ marginBottom: 40 }}>
              <h2 style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: '#55535d', margin: '0 0 14px', paddingBottom: 8, borderBottom: '1px solid #1e1e26' }}>
                Sources
              </h2>
              {['architecture.pdf — 42 pages · PDF', 'research-paper.pdf — 28 pages · PDF', 'design-notes.docx — 15 pages · DOCX'].map(s => (
                <div key={s} style={{ fontSize: 12.5, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)', marginBottom: 6 }}>
                  {s}
                </div>
              ))}
            </div>

            {/* Citation detail */}
            {cite && (
              <div style={{
                padding: 18, background: '#111116',
                border: '1px solid rgba(59,158,255,0.2)', borderRadius: 7, marginBottom: 24,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#3b9eff', fontFamily: 'var(--font-mono, monospace)' }}>
                    Citation {cite.id}
                  </span>
                  <span style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                    {cite.source} · p.{cite.page} · chunk {cite.chunk}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: '#8b8897', lineHeight: 1.65, fontStyle: 'italic' }}>
                  "{cite.excerpt}"
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
