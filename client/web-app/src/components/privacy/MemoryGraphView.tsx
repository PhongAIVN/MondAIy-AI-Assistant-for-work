import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Minus, Network, Plus, RotateCcw } from 'lucide-react';
import { fetchMemoryGraph, type MemoryGraph, type MemoryGraphEdge, type MemoryGraphNode } from '../../lib/memoryApi';
import { useAuthStore } from '../../stores/useAuthStore';

type Props = { language: string };
type Point = { x: number; y: number };
type DragState = { id: string; offsetX: number; offsetY: number } | null;

const WIDTH = 760;
const HEIGHT = 430;

const palette: Record<string, string> = {
  memory: '#2F7186',
  source: '#B57A2B',
  conflict: '#B54D58',
};

const initialLayout = (nodes: MemoryGraphNode[]): Record<string, Point> => Object.fromEntries(nodes.map((node, index) => {
  const angle = (index / Math.max(nodes.length, 1)) * Math.PI * 2 - Math.PI / 2;
  const radius = Math.min(145, 52 + nodes.length * 11);
  return [node.id, { x: WIDTH / 2 + Math.cos(angle) * radius, y: HEIGHT / 2 + Math.sin(angle) * radius }];
}));

export const MemoryGraphView: React.FC<Props> = ({ language }) => {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [graph, setGraph] = useState<MemoryGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const dragRef = useRef<DragState>(null);

  useEffect(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(false);
    void fetchMemoryGraph(accessToken)
      .then((nextGraph) => {
        setGraph(nextGraph);
        setPositions(initialLayout(nextGraph.nodes));
        setSelectedNodeId(null);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [accessToken]);

  // Keep layout local to the existing API: nodes repel each other and connected
  // nodes gently attract, then settle into a readable arrangement.
  useEffect(() => {
    if (!graph || graph.nodes.length < 2) return;
    let frame = 0;
    let iteration = 0;
    let current = initialLayout(graph.nodes);
    const tick = () => {
      if (iteration >= 55) return;
      const next = Object.fromEntries(graph.nodes.map((node) => [node.id, { ...current[node.id] }])) as Record<string, Point>;
      graph.nodes.forEach((node, index) => {
        const point = next[node.id];
        let fx = (WIDTH / 2 - point.x) * 0.008;
        let fy = (HEIGHT / 2 - point.y) * 0.008;
        graph.nodes.forEach((other, otherIndex) => {
          if (index === otherIndex) return;
          const otherPoint = current[other.id];
          const dx = point.x - otherPoint.x;
          const dy = point.y - otherPoint.y;
          const distance = Math.max(Math.hypot(dx, dy), 18);
          const force = 1800 / (distance * distance);
          fx += (dx / distance) * force;
          fy += (dy / distance) * force;
        });
        graph.edges.forEach((edge) => {
          if (edge.source !== node.id && edge.target !== node.id) return;
          const otherPoint = current[edge.source === node.id ? edge.target : edge.source];
          if (!otherPoint) return;
          const dx = otherPoint.x - point.x;
          const dy = otherPoint.y - point.y;
          const distance = Math.max(Math.hypot(dx, dy), 1);
          const spring = (distance - 130) * 0.012;
          fx += (dx / distance) * spring;
          fy += (dy / distance) * spring;
        });
        next[node.id] = { x: Math.max(52, Math.min(WIDTH - 52, point.x + fx)), y: Math.max(48, Math.min(HEIGHT - 48, point.y + fy)) };
      });
      current = next;
      setPositions(next);
      iteration += 1;
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [graph]);

  if (loading) return <div className="flex items-center gap-2 py-6 text-xs text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />{language === 'vi' ? 'Đang dựng graph...' : 'Building graph...'}</div>;
  if (error) return <p role="alert" className="py-6 text-xs text-[var(--color-text-secondary)]">{language === 'vi' ? 'Không tải được đồ thị bộ nhớ.' : 'Could not load the memory graph.'}</p>;
  if (!graph || graph.nodes.length === 0) return null;

  const edgeColor = (edge: MemoryGraphEdge) => edge.type === 'conflict' ? palette.conflict : edge.type === 'supersedes' ? '#6A5A9A' : '#B8A97A';
  const label = (node: MemoryGraphNode) => node.nodeType === 'source'
    ? `${language === 'vi' ? 'Nguồn' : 'Source'}: ${node.label}`
    : node.label;
  const graphTitle = language === 'vi' ? 'Đồ thị bộ nhớ' : 'Memory graph';
  const graphMeta = language === 'vi'
    ? `${graph.nodes.length} nút · ${graph.edges.length} liên kết`
    : `${graph.nodes.length} nodes · ${graph.edges.length} links`;
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const connectedEdges = selectedNode ? graph.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id) : [];
  const toGraphPoint = (event: React.PointerEvent<SVGElement>) => {
    const svg = event.currentTarget.ownerSVGElement ?? event.currentTarget;
    const rect = svg.getBoundingClientRect();
    return { x: ((event.clientX - rect.left) / rect.width) * WIDTH, y: ((event.clientY - rect.top) / rect.height) * HEIGHT };
  };
  const handlePointerMove = (event: React.PointerEvent<SVGElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const point = toGraphPoint(event);
    setPositions((current) => ({ ...current, [drag.id]: { x: point.x - drag.offsetX, y: point.y - drag.offsetY } }));
  };

  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-4 space-y-3" aria-label={graphTitle}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
        <Network className="h-4 w-4 text-[var(--color-primary)]" />
        <h3 className="text-base font-extrabold text-[var(--color-text-primary)] font-heading">{graphTitle}</h3>
        <span className="text-xs text-[var(--color-text-secondary)]">{graphMeta}</span>
        </div>
        <div className="flex items-center gap-1" aria-label={language === 'vi' ? 'Điều khiển đồ thị' : 'Graph controls'}>
          <button type="button" className="app-icon-button" aria-label={language === 'vi' ? 'Thu nhỏ' : 'Zoom out'} onClick={() => setZoom((value) => Math.max(0.75, value - 0.15))}><Minus className="h-3.5 w-3.5" /></button>
          <span className="min-w-12 text-center text-[11px] tabular-nums text-[var(--color-text-secondary)]">{Math.round(zoom * 100)}%</span>
          <button type="button" className="app-icon-button" aria-label={language === 'vi' ? 'Phóng to' : 'Zoom in'} onClick={() => setZoom((value) => Math.min(1.5, value + 0.15))}><Plus className="h-3.5 w-3.5" /></button>
          <button type="button" className="app-icon-button" aria-label={language === 'vi' ? 'Đặt lại đồ thị' : 'Reset graph'} onClick={() => { setPositions(initialLayout(graph.nodes)); setZoom(1); setSelectedNodeId(null); }}><RotateCcw className="h-3.5 w-3.5" /></button>
        </div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="min-w-[680px] w-full touch-none"
          role="img"
          aria-label={language === 'vi' ? 'Đồ thị quan hệ bộ nhớ' : 'Interactive memory relationships graph'}
          onPointerMove={handlePointerMove}
          onPointerUp={() => { dragRef.current = null; }}
          onPointerLeave={() => { dragRef.current = null; }}
        >
          <g transform={`translate(${WIDTH / 2} ${HEIGHT / 2}) scale(${zoom}) translate(${-WIDTH / 2} ${-HEIGHT / 2})`}>
          {graph.edges.map((edge) => {
            const source = positions[edge.source];
            const target = positions[edge.target];
            if (!source || !target) return null;
            const active = selectedNodeId === edge.source || selectedNodeId === edge.target;
            return <g key={edge.id} opacity={selectedNodeId && !active ? 0.2 : 1}><line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke={edgeColor(edge)} strokeWidth={active ? 3 : edge.type === 'conflict' ? 2.5 : 1.5} strokeDasharray={edge.type === 'evidence' ? '5 5' : undefined} /><title>{edge.label ?? edge.type}</title></g>;
          })}
          {graph.nodes.map((node) => {
            const point = positions[node.id];
            if (!point) return null;
            const conflict = node.status === 'disputed';
            const selected = selectedNodeId === node.id;
            return <g key={node.id} transform={`translate(${point.x}, ${point.y})`} opacity={selectedNodeId && !selected ? 0.45 : 1} onPointerDown={(event) => { event.stopPropagation(); const local = toGraphPoint(event); dragRef.current = { id: node.id, offsetX: local.x - point.x, offsetY: local.y - point.y }; setSelectedNodeId(node.id); }} onClick={() => setSelectedNodeId(node.id)}>
              <circle r={selected ? 34 : node.nodeType === 'memory' ? 28 : 22} fill={conflict ? palette.conflict : palette[node.nodeType]} opacity="0.95" stroke={selected ? 'var(--color-text-primary)' : 'transparent'} strokeWidth="3" className="cursor-grab transition-all duration-200 active:cursor-grabbing" />
              <title>{label(node)}</title><text textAnchor="middle" y="5" fill="white" fontSize="12" fontWeight="700">{node.nodeType === 'memory' ? 'M' : 'S'}</text>
              <text textAnchor="middle" y="48" fill="currentColor" fontSize="12" fontWeight="600">{label(node).slice(0, 28)}</text>
            </g>;
          })}
          </g>
        </svg>
      </div>
      {selectedNode && <aside className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-xs" aria-label={language === 'vi' ? 'Chi tiết nút được chọn' : 'Selected node details'}><div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-[var(--color-text-primary)]">{label(selectedNode)}</p><p className="mt-1 text-[var(--color-text-secondary)]">{connectedEdges.length} {language === 'vi' ? 'liên kết' : 'connections'}</p></div><button type="button" className="text-[var(--color-text-secondary)] underline-offset-2 hover:underline" onClick={() => setSelectedNodeId(null)}>{language === 'vi' ? 'Đóng' : 'Close'}</button></div></aside>}
      <p className="text-xs leading-relaxed text-[var(--color-text-secondary)]">{language === 'vi' ? 'M = bộ nhớ · S = nguồn · đường đỏ = xung đột · đường tím = phiên bản mới thay phiên bản cũ' : 'M = memory · S = source · red = conflict · purple = newer version supersedes older'}</p>
    </section>
  );
};
