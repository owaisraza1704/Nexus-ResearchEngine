import { useState, useEffect } from 'react';
import { ChevronLeft, X } from 'lucide-react';
import { useNavigate } from 'react-router';

type TaskStatus = 'SUCCEEDED' | 'RUNNING' | 'READY' | 'FAILED' | 'BLOCKED' | 'PENDING';

interface Task {
  key: string; type: string; status: TaskStatus;
  deps: string[]; duration?: string; attempt: number;
  worker?: string; query?: string; chunks?: number; score?: number;
  evidence?: number; claims?: number;
  x: number; y: number;
}

const TASKS: Task[] = [
  { key: 'planner', type: 'PLANNER', status: 'SUCCEEDED', deps: [], duration: '0.8s', attempt: 1, worker: 'worker-01', x: 340, y: 40 },
  { key: 'retrieval-a', type: 'RETRIEVAL', status: 'SUCCEEDED', deps: ['planner'], duration: '1.2s', attempt: 1, worker: 'worker-01', query: 'attention mechanism encoder', chunks: 8, score: 0.91, x: 100, y: 140 },
  { key: 'retrieval-b', type: 'RETRIEVAL', status: 'SUCCEEDED', deps: ['planner'], duration: '1.4s', attempt: 1, worker: 'worker-02', query: 'decoder autoregressive generation', chunks: 6, score: 0.88, x: 340, y: 140 },
  { key: 'retrieval-c', type: 'RETRIEVAL', status: 'RUNNING', deps: ['planner'], duration: '—', attempt: 1, worker: 'worker-03', query: 'cross-attention encoder-decoder', chunks: 0, x: 580, y: 140 },
  { key: 'evidence-a', type: 'EVIDENCE', status: 'SUCCEEDED', deps: ['retrieval-a', 'retrieval-b'], duration: '0.6s', attempt: 1, worker: 'worker-01', evidence: 12, claims: 4, x: 220, y: 240 },
  { key: 'evidence-b', type: 'EVIDENCE', status: 'BLOCKED', deps: ['retrieval-c'], duration: '—', attempt: 0, x: 580, y: 240 },
  { key: 'synthesis', type: 'SYNTHESIS', status: 'BLOCKED', deps: ['evidence-a', 'evidence-b'], duration: '—', attempt: 0, x: 340, y: 340 },
  { key: 'validation', type: 'VALIDATION', status: 'PENDING', deps: ['synthesis'], duration: '—', attempt: 0, x: 340, y: 430 },
  { key: 'result', type: 'RESULT', status: 'PENDING', deps: ['validation'], duration: '—', attempt: 0, x: 340, y: 520 },
];

const STATUS_COLORS: Record<TaskStatus, { bg: string; border: string; text: string; dot: string }> = {
  SUCCEEDED: { bg: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.3)', text: '#22c55e', dot: '#22c55e' },
  RUNNING: { bg: 'rgba(59,158,255,0.1)', border: 'rgba(59,158,255,0.35)', text: '#3b9eff', dot: '#3b9eff' },
  READY: { bg: 'rgba(96,165,250,0.08)', border: 'rgba(96,165,250,0.25)', text: '#60a5fa', dot: '#60a5fa' },
  FAILED: { bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.3)', text: '#ef4444', dot: '#ef4444' },
  BLOCKED: { bg: '#17171d', border: '#2c2c3a', text: '#55535d', dot: '#2c2c3a' },
  PENDING: { bg: '#17171d', border: '#1e1e26', text: '#55535d', dot: '#1e1e26' },
};

function getEdges(tasks: Task[]) {
  const edges: { x1: number; y1: number; x2: number; y2: number; active: boolean }[] = [];
  const NODE_W = 140, NODE_H = 52;
  tasks.forEach(task => {
    task.deps.forEach(depKey => {
      const dep = tasks.find(t => t.key === depKey);
      if (!dep) return;
      const active = dep.status === 'SUCCEEDED' || dep.status === 'RUNNING';
      edges.push({
        x1: dep.x + NODE_W / 2, y1: dep.y + NODE_H,
        x2: task.x + NODE_W / 2, y2: task.y,
        active,
      });
    });
  });
  return edges;
}

export default function ResearchJob() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<Task | null>(TASKS.find(t => t.key === 'retrieval-b') || null);
  const [elapsed, setElapsed] = useState(73);

  useEffect(() => {
    const id = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const edges = getEdges(TASKS);
  const succeeded = TASKS.filter(t => t.status === 'SUCCEEDED').length;
  const running = TASKS.filter(t => t.status === 'RUNNING').length;

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{
        borderBottom: '1px solid #1e1e26', padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0,
      }}>
        <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d', display: 'flex', gap: 4, alignItems: 'center' }}>
          <ChevronLeft size={14} />
          <span style={{ fontSize: 12 }}>Research Runs</span>
        </button>
        <span style={{ color: '#2c2c3a' }}>/</span>
        <span style={{ fontSize: 12.5, fontWeight: 500, color: '#f0ede8' }}>
          Multi-Architecture Comparison
        </span>
        <span style={{ fontSize: 10, fontWeight: 700, color: '#3b9eff', background: 'rgba(59,158,255,0.1)', padding: '2px 6px', borderRadius: 3, letterSpacing: 0.5, animation: 'pulse 2s ease-in-out infinite' }}>
          RUNNING
        </span>

        {/* Stats row */}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 24, alignItems: 'center' }}>
          {[
            { label: 'Tasks', value: `${succeeded} / ${TASKS.length}` },
            { label: 'Workers', value: `${running} active` },
            { label: 'Elapsed', value: fmt(elapsed) },
            { label: 'Provider Calls', value: '8 / 20' },
            { label: 'Budget', value: '42%' },
          ].map(({ label, value }) => (
            <div key={label} style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: '#55535d', fontWeight: 500 }}>{label}</div>
              <div style={{ fontSize: 12.5, fontFamily: 'var(--font-mono, monospace)', color: '#f0ede8', fontWeight: 500 }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: selected ? '1fr 300px' : '1fr', overflow: 'hidden' }}>

        {/* DAG Canvas */}
        <div style={{ overflowY: 'auto', overflowX: 'auto', padding: '24px' }}>
          <div style={{ position: 'relative', width: 780, height: 620, margin: '0 auto' }}>
            {/* SVG edges */}
            <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width={780} height={620}>
              <defs>
                <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                  <path d="M0,0 L6,3 L0,6 Z" fill="#2c2c3a" />
                </marker>
                <marker id="arrow-active" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                  <path d="M0,0 L6,3 L0,6 Z" fill="#3b9eff" />
                </marker>
              </defs>
              {edges.map((e, i) => {
                const cx = (e.x1 + e.x2) / 2;
                const cy = (e.y1 + e.y2) / 2;
                return (
                  <path
                    key={i}
                    d={`M${e.x1},${e.y1} C${e.x1},${e.y1 + 40} ${e.x2},${e.y2 - 40} ${e.x2},${e.y2}`}
                    fill="none"
                    stroke={e.active ? '#3b9eff' : '#2c2c3a'}
                    strokeWidth={e.active ? 1.5 : 1}
                    strokeOpacity={e.active ? 0.5 : 0.6}
                    markerEnd={`url(#${e.active ? 'arrow-active' : 'arrow'})`}
                  />
                );
              })}
            </svg>

            {/* Task nodes */}
            {TASKS.map(task => {
              const sc = STATUS_COLORS[task.status];
              const isSelected = selected?.key === task.key;
              return (
                <div
                  key={task.key}
                  onClick={() => setSelected(s => s?.key === task.key ? null : task)}
                  style={{
                    position: 'absolute', left: task.x, top: task.y,
                    width: 140, cursor: 'pointer',
                    background: isSelected ? `rgba(59,158,255,0.08)` : sc.bg,
                    border: `1px solid ${isSelected ? '#3b9eff' : sc.border}`,
                    borderRadius: 6, padding: '10px 12px',
                    transition: 'all 150ms',
                    boxShadow: isSelected ? '0 0 16px rgba(59,158,255,0.15)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase' }}>
                      {task.type}
                    </span>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: sc.dot, flexShrink: 0,
                      boxShadow: task.status === 'RUNNING' ? `0 0 6px ${sc.dot}` : 'none',
                    }} />
                  </div>
                  <div style={{ fontSize: 11.5, fontFamily: 'var(--font-mono, monospace)', color: sc.text, fontWeight: 500 }}>
                    {task.key}
                  </div>
                  {task.duration && task.duration !== '—' && (
                    <div style={{ fontSize: 10, color: '#55535d', marginTop: 2 }}>{task.duration}</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Progress summary */}
          <div style={{ maxWidth: 780, margin: '16px auto 0', display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 8 }}>
            {[
              { label: 'Succeeded', count: succeeded, color: '#22c55e' },
              { label: 'Running', count: running, color: '#3b9eff' },
              { label: 'Blocked', count: TASKS.filter(t => t.status === 'BLOCKED').length, color: '#55535d' },
              { label: 'Pending', count: TASKS.filter(t => t.status === 'PENDING').length, color: '#55535d' },
              { label: 'Failed', count: TASKS.filter(t => t.status === 'FAILED').length, color: '#ef4444' },
            ].map(({ label, count, color }) => (
              <div key={label} style={{
                background: '#111116', border: '1px solid #1e1e26', borderRadius: 5, padding: '8px 12px',
              }}>
                <div style={{ fontSize: 18, fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', color }}>{count}</div>
                <div style={{ fontSize: 10, color: '#55535d' }}>{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Task Inspector */}
        {selected && (
          <div style={{ borderLeft: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 16px', background: '#0c0c0e' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
              <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase' }}>Task Inspector</span>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#55535d' }}>
                <X size={13} />
              </button>
            </div>

            {[
              { label: 'Task Key', value: selected.key },
              { label: 'Type', value: selected.type },
              { label: 'Status', value: selected.status },
              { label: 'Attempt', value: selected.attempt },
              { label: 'Worker', value: selected.worker || '—' },
              { label: 'Duration', value: selected.duration || '—' },
              { label: 'Dependencies', value: selected.deps.join(', ') || 'none' },
            ].map(({ label, value }) => (
              <div key={label} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: '#55535d', fontWeight: 500, letterSpacing: 0.4, marginBottom: 2 }}>{label}</div>
                <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{value}</div>
              </div>
            ))}

            {selected.type === 'RETRIEVAL' && selected.query && (
              <>
                <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
                <div style={{ fontSize: 10, fontWeight: 600, color: '#55535d', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 }}>Retrieval</div>
                {[
                  { label: 'Query', value: selected.query },
                  { label: 'Top K', value: 8 },
                  { label: 'Retrieved Chunks', value: selected.chunks ?? '—' },
                  { label: 'Best Score', value: selected.score ?? '—' },
                ].map(({ label, value }) => (
                  <div key={label} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: '#55535d', marginBottom: 2 }}>{label}</div>
                    <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{String(value)}</div>
                  </div>
                ))}
              </>
            )}

            {selected.type === 'EVIDENCE' && selected.evidence != null && (
              <>
                <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
                <div style={{ fontSize: 10, fontWeight: 600, color: '#55535d', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 }}>Evidence</div>
                {[
                  { label: 'Evidence Items', value: selected.evidence },
                  { label: 'Claims', value: selected.claims },
                  { label: 'Citation Validation', value: 'PASSED' },
                ].map(({ label, value }) => (
                  <div key={label} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: '#55535d', marginBottom: 2 }}>{label}</div>
                    <div style={{ fontSize: 12, color: '#8b8897', fontFamily: 'var(--font-mono, monospace)' }}>{value}</div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }`}</style>
    </div>
  );
}
