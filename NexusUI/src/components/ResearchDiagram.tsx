'use client';
import { useMemo } from 'react';
import { Background, Controls, ReactFlow, Position, type Edge, type Node } from '@xyflow/react';
import dagre from '@dagrejs/dagre';
import '@xyflow/react/dist/style.css';

export type DiagramItem = {
  id: string;
  label: string;
  detail: string;
  state?: string;
};
export default function ResearchDiagram({
  items,
  connections,
  onSelect,
}: {
  items: DiagramItem[];
  connections: { source: string; target: string; label?: string }[];
  onSelect?: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
    graph.setGraph({
      rankdir: 'LR',
      nodesep: 28,
      ranksep: 65,
      marginx: 20,
      marginy: 20,
    });
    items.forEach((item) => graph.setNode(item.id, { width: 205, height: 85 }));
    connections.forEach((edge) => graph.setEdge(edge.source, edge.target));
    dagre.layout(graph);
    const nodes: Node[] = items.map((item) => ({
      id: item.id,
      position: {
        x: graph.node(item.id).x - 102.5,
        y: graph.node(item.id).y - 42.5,
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      className: 'research-node state-' + (item.state || 'ready'),
      data: {
        label: (
          <>
            <strong>{item.label}</strong>
            <span>{item.detail}</span>
          </>
        ),
      },
      style: { width: 205, minHeight: 85 },
    }));
    const edges: Edge[] = connections.map((edge, index) => ({
      ...edge,
      id: 'edge-' + index,
      type: 'smoothstep',
      style: { stroke: '#596d8d' },
      labelStyle: { fill: '#d6d1e1', fontSize: 10 },
      labelBgStyle: { fill: '#17171d' },
    }));
    return { nodes, edges };
  }, [items, connections]);
  return (
    <div className="research-diagram" aria-label="Research dependency graph">
      <ReactFlow
        key={items.map((item) => item.id).join(',')}
        nodes={nodes}
        edges={edges}
        fitView
        minZoom={0.15}
        maxZoom={1.8}
        nodesConnectable={false}
        nodesDraggable={false}
        onNodeClick={(_, node) => onSelect?.(node.id)}
        colorMode="dark"
      >
        <Background color="#31313e" gap={24} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
