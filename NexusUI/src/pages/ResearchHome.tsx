import { useState, useRef } from 'react';
import { useNavigate } from 'react-router';
import {
  Upload, X, ChevronDown, FileText, Loader2,
  CheckCircle2, AlertCircle, Clock, BookOpen, ArrowRight, Plus
} from 'lucide-react';

const RECENT: {
  id: string; question: string; status: 'COMPLETED' | 'INSUFFICIENT_CONTEXT' | 'RUNNING' | 'FAILED';
  sources: number; evidence: number; citations?: number; gaps?: number; duration?: string; ts: string;
}[] = [
  {
    id: 'run-001', question: 'How does the transformer attention mechanism differ between encoder-only and decoder-only architectures?',
    status: 'COMPLETED', sources: 3, evidence: 12, citations: 7, duration: '3.2s', ts: '2 hours ago',
  },
  {
    id: 'run-002', question: 'Evaluate the proposed retrieval architecture against dense passage retrieval benchmarks.',
    status: 'INSUFFICIENT_CONTEXT', sources: 2, evidence: 1, gaps: 2, ts: '4 hours ago',
  },
  {
    id: 'run-003', question: 'What are the primary failure modes of vector similarity search at scale?',
    status: 'COMPLETED', sources: 4, evidence: 9, citations: 11, duration: '5.1s', ts: 'Yesterday',
  },
  {
    id: 'run-004', question: 'Summarize the key contributions of the document chunking strategy.',
    status: 'RUNNING', sources: 1, evidence: 0, ts: 'Just now',
  },
];

const MODES = ['Grounded Answer', 'Multi-Document', 'Evidence Only'];

const STAT_COLOR = {
  COMPLETED: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: 'COMPLETED' },
  INSUFFICIENT_CONTEXT: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'INSUFFICIENT CONTEXT' },
  RUNNING: { color: '#3b9eff', bg: 'rgba(59,158,255,0.1)', label: 'RUNNING' },
  FAILED: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: 'FAILED' },
};

const StatusIcon = ({ s }: { s: string }) => {
  if (s === 'COMPLETED') return <CheckCircle2 size={13} color="#22c55e" />;
  if (s === 'INSUFFICIENT_CONTEXT') return <AlertCircle size={13} color="#f59e0b" />;
  if (s === 'RUNNING') return <Loader2 size={13} color="#3b9eff" style={{ animation: 'spin 1s linear infinite' }} />;
  return <X size={13} color="#ef4444" />;
};

export default function ResearchHome() {
  const navigate = useNavigate();
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState('Grounded Answer');
  const [sources, setSources] = useState([
    { id: 'src-001', name: 'architecture.pdf', type: 'PDF' },
    { id: 'src-002', name: 'research-paper.pdf', type: 'PDF' },
  ]);
  const [topK, setTopK] = useState(8);
  const [dragging, setDragging] = useState(false);
  const [running, setRunning] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const removeSource = (id: string) => setSources(s => s.filter(x => x.id !== id));

  const handleRun = () => {
    if (!question.trim()) return;
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      navigate('/research/run-001');
    }, 1800);
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ maxWidth: 860, width: '100%', margin: '0 auto', padding: '40px 32px 80px' }}>

        {/* Header */}
        <div style={{ marginBottom: 36 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#55535d', textTransform: 'uppercase', marginBottom: 6 }}>
            Research
          </div>
          <h1 style={{ fontSize: 28, fontWeight: 300, letterSpacing: -0.8, color: '#f0ede8', margin: 0, lineHeight: 1.2 }}>
            Turn complex questions into<br />
            <span style={{ color: '#3b9eff', fontWeight: 600 }}>evidence-grounded research.</span>
          </h1>
        </div>

        {/* Composer */}
        <div style={{
          background: '#111116', border: '1px solid #1e1e26',
          borderRadius: 10, overflow: 'hidden',
          boxShadow: '0 2px 24px rgba(0,0,0,0.3)',
        }}>
          {/* Question area */}
          <div style={{ padding: '20px 24px 0' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 10 }}>
              Research Question
            </div>
            <textarea
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="Ask Nexus anything... What do you want to research?"
              rows={4}
              style={{
                width: '100%', background: 'none', border: 'none', outline: 'none', resize: 'none',
                fontSize: 15.5, fontWeight: 300, color: '#f0ede8', fontFamily: 'inherit',
                lineHeight: 1.65, letterSpacing: -0.1,
              }}
            />
          </div>

          {/* Divider */}
          <div style={{ height: 1, background: '#1e1e26', margin: '12px 0' }} />

          {/* Sources section */}
          <div style={{ padding: '0 24px 16px' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 10 }}>
              Sources · {sources.length} selected
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {sources.map(s => (
                <div key={s.id} style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  background: '#1e1e27', border: '1px solid #2c2c3a',
                  borderRadius: 5, padding: '4px 8px',
                }}>
                  <FileText size={11} color="#60a5fa" />
                  <span style={{ fontSize: 12, color: '#f0ede8' }}>{s.name}</span>
                  <span style={{ fontSize: 9.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{s.type}</span>
                  <button
                    onClick={() => removeSource(s.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 1, display: 'flex', color: '#55535d' }}
                  >
                    <X size={10} />
                  </button>
                </div>
              ))}

              <button
                onClick={() => fileRef.current?.click()}
                style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  background: 'none', border: '1px dashed #2c2c3a',
                  borderRadius: 5, padding: '4px 10px', cursor: 'pointer', color: '#55535d',
                }}
              >
                <Plus size={11} />
                <span style={{ fontSize: 12 }}>Add Source</span>
              </button>
              <input ref={fileRef} type="file" accept=".pdf,.docx" hidden multiple />
            </div>

            {/* Drop zone hint */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); }}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `1px dashed ${dragging ? '#3b9eff' : '#1e1e26'}`,
                borderRadius: 6, padding: '10px 16px',
                display: 'flex', alignItems: 'center', gap: 8,
                cursor: 'pointer',
                background: dragging ? 'rgba(59,158,255,0.04)' : 'transparent',
                transition: 'all 150ms ease',
              }}
            >
              <Upload size={13} color={dragging ? '#3b9eff' : '#55535d'} />
              <span style={{ fontSize: 12, color: '#55535d' }}>
                Drop PDF or DOCX files here, or click to upload
              </span>
            </div>
          </div>

          {/* Configuration row */}
          <div style={{ borderTop: '1px solid #1e1e26', padding: '12px 24px', display: 'flex', gap: 24, alignItems: 'center' }}>
            {/* Mode selector */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 10, color: '#55535d', alignSelf: 'center', marginRight: 4, fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>Mode</span>
              {MODES.map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  style={{
                    padding: '4px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12,
                    background: mode === m ? 'rgba(59,158,255,0.12)' : 'transparent',
                    border: `1px solid ${mode === m ? 'rgba(59,158,255,0.3)' : '#1e1e26'}`,
                    color: mode === m ? '#3b9eff' : '#55535d',
                    transition: 'all 120ms',
                  }}
                >
                  {m}
                </button>
              ))}
            </div>

            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
              {/* Top-K */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 10.5, color: '#55535d' }}>Top-K</span>
                <select
                  value={topK}
                  onChange={e => setTopK(Number(e.target.value))}
                  style={{
                    background: '#1e1e27', border: '1px solid #2c2c3a',
                    borderRadius: 4, color: '#8b8897', fontSize: 12, padding: '3px 6px',
                    fontFamily: 'inherit', cursor: 'pointer', outline: 'none',
                  }}
                >
                  {[4, 8, 12, 16, 24].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>

              {/* Run button */}
              <button
                onClick={handleRun}
                disabled={!question.trim() || running}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 20px', borderRadius: 6,
                  background: question.trim() && !running
                    ? 'linear-gradient(135deg, #3b9eff 0%, #2a7fdf 100%)'
                    : '#1e1e27',
                  border: 'none', cursor: question.trim() && !running ? 'pointer' : 'default',
                  color: question.trim() && !running ? '#fff' : '#55535d',
                  fontSize: 13.5, fontWeight: 600, transition: 'all 150ms',
                  boxShadow: question.trim() && !running ? '0 0 20px rgba(59,158,255,0.25)' : 'none',
                }}
              >
                {running ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : null}
                {running ? 'Retrieving...' : 'Run Research'}
                {!running && <ArrowRight size={14} />}
              </button>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div style={{ marginTop: 48 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 16,
          }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, color: '#55535d', textTransform: 'uppercase' }}>
              Recent Research
            </div>
            <button style={{ fontSize: 11.5, color: '#55535d', background: 'none', border: 'none', cursor: 'pointer' }}>
              View all runs →
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {RECENT.map((run, i) => {
              const sc = STAT_COLOR[run.status];
              return (
                <div
                  key={run.id}
                  onClick={() => navigate(run.status !== 'RUNNING' ? `/research/${run.id}` : '/jobs')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 16,
                    padding: '14px 18px', borderRadius: 7, cursor: 'pointer',
                    background: 'transparent', border: '1px solid transparent',
                    transition: 'all 120ms',
                    position: 'relative',
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLElement).style.background = '#111116';
                    (e.currentTarget as HTMLElement).style.borderColor = '#1e1e26';
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.background = 'transparent';
                    (e.currentTarget as HTMLElement).style.borderColor = 'transparent';
                  }}
                >
                  <div style={{ flexShrink: 0 }}>
                    <StatusIcon s={run.status} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13.5, color: '#f0ede8', fontWeight: 400,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      marginBottom: 4,
                    }}>
                      {run.question}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: 0.6,
                        color: sc.color, background: sc.bg,
                        padding: '2px 6px', borderRadius: 3,
                      }}>{sc.label}</span>
                      <span style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                        {run.sources} src
                      </span>
                      {run.evidence > 0 && (
                        <span style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          {run.evidence} evidence
                        </span>
                      )}
                      {run.citations && (
                        <span style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          {run.citations} citations
                        </span>
                      )}
                      {run.gaps && (
                        <span style={{ fontSize: 11.5, color: '#f59e0b', fontFamily: 'var(--font-mono, monospace)' }}>
                          {run.gaps} gaps
                        </span>
                      )}
                      {run.duration && (
                        <span style={{ fontSize: 11.5, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>
                          {run.duration}
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                    <span style={{ fontSize: 11.5, color: '#55535d' }}>{run.ts}</span>
                    <ArrowRight size={13} color="#2c2c3a" />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Capability footer */}
        <div style={{
          marginTop: 48, padding: '20px 24px',
          background: '#111116', border: '1px solid #1e1e26', borderRadius: 8,
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20,
        }}>
          {[
            { phase: 'MVP-1 · Available', label: 'Grounded Answer', desc: 'Single-document retrieval with citation validation', color: '#22c55e' },
            { phase: 'MVP-2 · In Development', label: 'Multi-Document Research', desc: 'Evidence relationships, gaps, and contradiction detection', color: '#f59e0b' },
            { phase: 'MVP-3 · Planned', label: 'Async Research Jobs', desc: 'Validated plans, parallel task graphs, durable execution', color: '#55535d' },
          ].map(c => (
            <div key={c.phase}>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.6, color: c.color, marginBottom: 4 }}>
                {c.phase}
              </div>
              <div style={{ fontSize: 13, fontWeight: 500, color: '#f0ede8', marginBottom: 4 }}>
                {c.label}
              </div>
              <div style={{ fontSize: 12, color: '#55535d', lineHeight: 1.5 }}>
                {c.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
