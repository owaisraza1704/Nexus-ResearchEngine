import { useState } from 'react';

const METRICS = [
  { label: 'Report Generation Latency', value: '3.2s', delta: '-0.8s', trend: 'up', unit: 'avg', color: '#22c55e' },
  { label: 'Retrieval Relevance', value: '0.89', delta: '+0.04', trend: 'up', unit: 'score', color: '#22c55e' },
  { label: 'Citation Correctness', value: '94.2%', delta: '+1.1%', trend: 'up', unit: 'rate', color: '#22c55e' },
  { label: 'Groundedness', value: '91.7%', delta: '+2.3%', trend: 'up', unit: 'rate', color: '#22c55e' },
  { label: 'Cache Hit Rate', value: '38.4%', delta: '-4.1%', trend: 'down', unit: 'rate', color: '#f59e0b' },
  { label: 'Token Consumption', value: '1,847', delta: '+112', trend: 'down', unit: 'avg/run', color: '#f59e0b' },
];

const RUNS = [
  { id: 'run-001', q: 'Encoder vs decoder attention...', latency: 3.2, retrieval: 0.91, citations: 4, groundedness: 95, tokens: 1821, status: 'COMPLETED' },
  { id: 'run-003', q: 'Failure modes of vector search...', latency: 5.1, retrieval: 0.87, citations: 11, groundedness: 89, tokens: 2104, status: 'COMPLETED' },
  { id: 'run-002', q: 'Retrieval architecture evaluation...', latency: 1.4, retrieval: 0.44, citations: 0, groundedness: 0, tokens: 612, status: 'INSUFFICIENT_CONTEXT' },
];

const BAR_DATA = [
  { label: 'run-001', retrieval: 0.91, groundedness: 0.95 },
  { label: 'run-002', retrieval: 0.44, groundedness: 0 },
  { label: 'run-003', retrieval: 0.87, groundedness: 0.89 },
];

function SparkBar({ value, max = 1, color }: { value: number; max?: number; color: string }) {
  return (
    <div style={{ flex: 1, height: 6, background: '#1e1e26', borderRadius: 3, overflow: 'hidden' }}>
      <div style={{ width: `${(value / max) * 100}%`, height: '100%', background: color, borderRadius: 3 }} />
    </div>
  );
}

export default function Evaluation() {
  const [activeTab, setActiveTab] = useState<'overview' | 'runs'>('overview');

  return (
    <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
      <div style={{ maxWidth: 1100, width: '100%', margin: '0 auto', padding: '36px 32px 80px' }}>

        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#55535d', textTransform: 'uppercase', marginBottom: 6 }}>Evaluation</div>
          <h1 style={{ fontSize: 22, fontWeight: 300, letterSpacing: -0.5, color: '#f0ede8', margin: 0 }}>Research Quality Metrics</h1>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid #1e1e26', marginBottom: 24 }}>
          {(['overview', 'runs'] as const).map(t => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              style={{
                padding: '10px 16px', background: 'none', border: 'none',
                borderBottom: activeTab === t ? '2px solid #3b9eff' : '2px solid transparent',
                cursor: 'pointer', fontSize: 13,
                color: activeTab === t ? '#3b9eff' : '#55535d',
                textTransform: 'capitalize', fontFamily: 'inherit', marginBottom: -1,
              }}
            >
              {t === 'overview' ? 'Overview' : 'Run Analysis'}
            </button>
          ))}
        </div>

        {activeTab === 'overview' && (
          <>
            {/* Metric grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 32 }}>
              {METRICS.map(m => (
                <div key={m.label} style={{
                  background: '#111116', border: '1px solid #1e1e26', borderRadius: 7, padding: '16px 18px',
                }}>
                  <div style={{ fontSize: 10.5, color: '#55535d', fontWeight: 500, marginBottom: 10 }}>{m.label}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                    <span style={{ fontSize: 26, fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', color: m.color, letterSpacing: -0.5 }}>
                      {m.value}
                    </span>
                    <span style={{ fontSize: 10.5, color: m.trend === 'up' ? '#22c55e' : '#f59e0b' }}>
                      {m.delta}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{m.unit}</div>
                </div>
              ))}
            </div>

            {/* Retrieval vs groundedness chart */}
            <div style={{ background: '#111116', border: '1px solid #1e1e26', borderRadius: 8, padding: '20px 24px', marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#55535d', letterSpacing: 0.6, textTransform: 'uppercase', marginBottom: 20 }}>
                Retrieval Relevance vs Groundedness
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {BAR_DATA.map(d => (
                  <div key={d.label}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', color: '#8b8897', width: 60, flexShrink: 0 }}>{d.label}</span>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 9.5, color: '#55535d', width: 70 }}>Retrieval</span>
                          <SparkBar value={d.retrieval} color="#3b9eff" />
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', color: '#3b9eff', width: 36, textAlign: 'right' }}>{d.retrieval}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 9.5, color: '#55535d', width: 70 }}>Groundedness</span>
                          <SparkBar value={d.groundedness} color={d.groundedness > 0.7 ? '#22c55e' : d.groundedness > 0 ? '#f59e0b' : '#ef4444'} />
                          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', color: d.groundedness > 0 ? '#22c55e' : '#ef4444', width: 36, textAlign: 'right' }}>
                            {d.groundedness > 0 ? d.groundedness : 'N/A'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Legend */}
              <div style={{ display: 'flex', gap: 16, marginTop: 16, paddingTop: 14, borderTop: '1px solid #1e1e26' }}>
                {[{ color: '#3b9eff', label: 'Retrieval Relevance' }, { color: '#22c55e', label: 'Groundedness' }].map(l => (
                  <div key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 10, height: 3, borderRadius: 2, background: l.color }} />
                    <span style={{ fontSize: 11, color: '#55535d' }}>{l.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Future metrics */}
            <div style={{
              padding: '16px 20px', background: '#111116', border: '1px solid #1e1e26', borderRadius: 7,
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: '#2c2c3a', flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: 12, color: '#55535d', marginBottom: 2 }}>Task Parallelism · Failure Recovery · Sequential vs Parallel Latency</div>
                <div style={{ fontSize: 11, color: '#2c2c3a' }}>Available in MVP-3 — Async Research Jobs</div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'runs' && (
          <div style={{ background: '#111116', border: '1px solid #1e1e26', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 80px 80px 80px 100px 80px', padding: '10px 18px', borderBottom: '1px solid #1e1e26' }}>
              {['Question', 'Latency', 'Retrieval', 'Citations', 'Groundedness', 'Tokens'].map(h => (
                <div key={h} style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.6, color: '#55535d', textTransform: 'uppercase' }}>{h}</div>
              ))}
            </div>
            {RUNS.map((run, i) => (
              <div key={run.id} style={{
                display: 'grid', gridTemplateColumns: '2fr 80px 80px 80px 100px 80px',
                padding: '14px 18px', borderBottom: i < RUNS.length - 1 ? '1px solid #1e1e26' : 'none',
                alignItems: 'center',
              }}>
                <div>
                  <div style={{ fontSize: 13, color: '#f0ede8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: 16 }}>
                    {run.q}
                  </div>
                  <div style={{ fontSize: 11, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{run.id}</div>
                </div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: '#f0ede8' }}>{run.latency}s</div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: run.retrieval > 0.7 ? '#22c55e' : '#f59e0b' }}>{run.retrieval}</div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: '#8b8897' }}>{run.citations}</div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: run.groundedness > 0 ? '#22c55e' : '#55535d' }}>
                  {run.groundedness > 0 ? `${run.groundedness}%` : '—'}
                </div>
                <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: '#8b8897' }}>{run.tokens.toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
