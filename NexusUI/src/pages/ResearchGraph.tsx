import { useState } from 'react';

type NodeType = 'SOURCE' | 'DOCUMENT' | 'CHUNK' | 'EVIDENCE' | 'CLAIM' | 'CITATION' | 'REPORT';

interface GraphNode {
  id: string; label: string; type: NodeType;
  x: number; y: number; rel?: string;
}

const NODE_COLORS: Record<NodeType, { bg: string; border: string; text: string }> = {
  SOURCE: { bg: 'rgba(96,165,250,0.12)', border: 'rgba(96,165,250,0.4)', text: '#60a5fa' },
  DOCUMENT: { bg: 'rgba(59,158,255,0.1)', border: 'rgba(59,158,255,0.35)', text: '#3b9eff' },
  CHUNK: { bg: '#17171d', border: '#2c2c3a', text: '#8b8897' },
  EVIDENCE: { bg: 'rgba(124,90,240,0.1)', border: 'rgba(124,90,240,0.35)', text: '#7c5af0' },
  CLAIM: { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.3)', text: '#f59e0b' },
  CITATION: { bg: 'rgba(34,197,94,0.08)', border: 'rgba(34,197,94,0.3)', text: '#22c55e' },
  REPORT: { bg: '#17171d', border: '#2c2c3a', text: '#f0ede8' },
};

const NODES: GraphNode[] = [
  { id: 'src-a', label: 'architecture.pdf', type: 'SOURCE', x: 60, y: 40 },
  { id: 'src-b', label: 'research-paper.pdf', type: 'SOURCE', x: 420, y: 40 },
  { id: 'doc-a', label: 'architecture.pdf', type: 'DOCUMENT', x: 60, y: 140 },
  { id: 'doc-b', label: 'research-paper.pdf', type: 'DOCUMENT', x: 420, y: 140 },
  { id: 'chunk-18', label: 'Chunk 018', type: 'CHUNK', x: 20, y: 240 },
  { id: 'chunk-42', label: 'Chunk 042', type: 'CHUNK', x: 140, y: 240 },
  { id: 'chunk-07', label: 'Chunk 007', type: 'CHUNK', x: 380, y: 240 },
  { id: 'chunk-31', label: 'Chunk 031', type: 'CHUNK', x: 490, y: 240 },
  { id: 'ev-01', label: 'E001', type: 'EVIDENCE', x: 60, y: 340 },
  { id: 'ev-02', label: 'E002', type: 'EVIDENCE', x: 200, y: 340 },
  { id: 'ev-03', label: 'E003', type: 'EVIDENCE', x: 340, y: 340 },
  { id: 'ev-04', label: 'E004', type: 'EVIDENCE', x: 480, y: 340 },
  { id: 'claim-01', label: 'Bidirectional attn', type: 'CLAIM', x: 120, y: 440 },
  { id: 'claim-02', label: 'Causal masking', type: 'CLAIM', x: 340, y: 440 },
  { id: 'cite-c1', label: '[C1]', type: 'CITATION', x: 60, y: 540 },
  { id: 'cite-c3', label: '[C3]', type: 'CITATION', x: 200, y: 540 },
  { id: 'cite-c5', label: '[C5]', type: 'CITATION', x: 340, y: 540 },
  { id: 'report-s1', label: 'Report §2', type: 'REPORT', x: 210, y: 630 },
];

const EDGES: [string, string][] = [
  ['src-a', 'doc-a'], ['src-b', 'doc-b'],
  ['doc-a', 'chunk-18'], ['doc-a', 'chunk-42'],
  ['doc-b', 'chunk-07'], ['doc-b', 'chunk-31'],
  ['chunk-18', 'ev-01'], ['chunk-42', 'ev-02'],
  ['chunk-07', 'ev-03'], ['chunk-31', 'ev-04'],
  ['ev-01', 'claim-01'], ['ev-02', 'claim-02'],
  ['ev-03', 'claim-02'],
  ['claim-01', 'cite-c1'], ['claim-01', 'cite-c3'],
  ['claim-02', 'cite-c5'],
  ['cite-c1', 'report-s1'], ['cite-c3', 'report-s1'], ['cite-c5', 'report-s1'],
];

const NODE_W = 120, NODE_H = 40;

function getCenter(n: GraphNode) {
  return { x: n.x + NODE_W / 2, y: n.y + NODE_H / 2 };
}

export default function ResearchGraph() {
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const nodeMap = Object.fromEntries(NODES.map(n => [n.id, n]));
  const highlightedIds = selected ? new Set<string>([selected.id, ...EDGES.filter(([a, b]) => a === selected.id || b === selected.id).flatMap(([a, b]) => [a, b])]) : null;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e1e26', flexShrink: 0 }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 1.2, color: '#55535d', textTransform: 'uppercase', marginBottom: 6 }}>Research Graph</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
          <h1 style={{ fontSize: 22, fontWeight: 300, letterSpacing: -0.5, color: '#f0ede8', margin: 0 }}>Provenance Graph</h1>
          <span style={{ fontSize: 12, color: '#55535d' }}>Source → Document → Chunk → Evidence → Claim → Citation → Report</span>
        </div>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: selected ? '1fr 280px' : '1fr', overflow: 'hidden' }}>
        {/* Graph canvas */}
        <div style={{ overflowY: 'auto', overflowX: 'auto', padding: '24px' }}>
          {/* Legend */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            {(Object.keys(NODE_COLORS) as NodeType[]).map(type => {
              const c = NODE_COLORS[type];
              return (
                <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: 2, background: c.bg, border: `1px solid ${c.border}` }} />
                  <span style={{ fontSize: 10, color: '#55535d', fontFamily: 'var(--font-mono, monospace)' }}>{type}</span>
                </div>
              );
            })}
          </div>

          <div style={{ position: 'relative', width: 640, height: 700 }}>
            <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width={640} height={700}>
              {EDGES.map(([from, to], i) => {
                const f = nodeMap[from], t = nodeMap[to];
                if (!f || !t) return null;
                const fc = getCenter(f), tc = getCenter(t);
                const isHighlighted = highlightedIds
                  ? highlightedIds.has(from) && highlightedIds.has(to)
                  : false;
                return (
                  <path
                    key={i}
                    d={`M${fc.x},${fc.y + NODE_H / 2 - 5} C${fc.x},${fc.y + 60} ${tc.x},${tc.y - 60} ${tc.x},${tc.y - NODE_H / 2 + 5}`}
                    fill="none"
                    stroke={isHighlighted ? '#3b9eff' : '#1e1e26'}
                    strokeWidth={isHighlighted ? 1.5 : 1}
                    strokeOpacity={highlightedIds ? (isHighlighted ? 0.7 : 0.2) : 0.6}
                  />
                );
              })}
            </svg>

            {NODES.map(node => {
              const c = NODE_COLORS[node.type];
              const isSelected = selected?.id === node.id;
              const isHighlighted = highlightedIds ? highlightedIds.has(node.id) : false;
              const isActive = isSelected || isHighlighted;
              return (
                <div
                  key={node.id}
                  onClick={() => setSelected(s => s?.id === node.id ? null : node)}
                  onMouseEnter={() => setHovered(node.id)}
                  onMouseLeave={() => setHovered(null)}
                  style={{
                    position: 'absolute', left: node.x, top: node.y,
                    width: NODE_W, height: NODE_H, cursor: 'pointer',
                    background: isSelected ? `rgba(59,158,255,0.12)` : c.bg,
                    border: `1px solid ${isSelected ? '#3b9eff' : isActive && highlightedIds ? c.border : c.border}`,
                    borderRadius: 6, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center', padding: '0 8px',
                    opacity: highlightedIds && !isActive ? 0.3 : 1,
                    transition: 'all 150ms',
                    boxShadow: isSelected ? '0 0 14px rgba(59,158,255,0.2)' : 'none',
                  }}
                >
                  <div style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: 0.6, color: c.text, textTransform: 'uppercase', marginBottom: 1 }}>
                    {node.type}
                  </div>
                  <div style={{ fontSize: 10.5, fontFamily: 'var(--font-mono, monospace)', color: isSelected ? '#f0ede8' : c.text, textAlign: 'center', lineHeight: 1.2 }}>
                    {node.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Node inspector */}
        {selected && (
          <div style={{ borderLeft: '1px solid #1e1e26', overflowY: 'auto', padding: '20px 16px' }}>
            <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.8, color: '#55535d', textTransform: 'uppercase', marginBottom: 14 }}>Node Inspector</div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 9.5, color: '#55535d', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>Type</div>
              <span style={{
                fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
                color: NODE_COLORS[selected.type].text,
                background: NODE_COLORS[selected.type].bg,
                border: `1px solid ${NODE_COLORS[selected.type].border}`,
                padding: '3px 8px', borderRadius: 4,
              }}>{selected.type}</span>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 9.5, color: '#55535d', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>ID</div>
              <div style={{ fontSize: 12, fontFamily: 'var(--font-mono, monospace)', color: '#8b8897' }}>{selected.id}</div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 9.5, color: '#55535d', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 4 }}>Label</div>
              <div style={{ fontSize: 13, color: '#f0ede8' }}>{selected.label}</div>
            </div>

            <div style={{ height: 1, background: '#1e1e26', margin: '14px 0' }} />
            <div style={{ fontSize: 10, fontWeight: 600, color: '#55535d', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 10 }}>Connections</div>

            {EDGES.filter(([a, b]) => a === selected.id || b === selected.id).map(([a, b]) => {
              const other = a === selected.id ? b : a;
              const direction = a === selected.id ? '→' : '←';
              const otherNode = nodeMap[other];
              if (!otherNode) return null;
              return (
                <div
                  key={`${a}-${b}`}
                  onClick={() => setSelected(otherNode)}
                  style={{
                    padding: '8px 10px', background: '#111116', borderRadius: 5,
                    border: '1px solid #1e1e26', marginBottom: 4, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8,
                  }}
                >
                  <span style={{ fontSize: 11, color: '#55535d' }}>{direction}</span>
                  <div>
                    <div style={{ fontSize: 10, color: NODE_COLORS[otherNode.type].text, fontWeight: 600 }}>{otherNode.type}</div>
                    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono, monospace)', color: '#8b8897' }}>{otherNode.label}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
