/**
 * AI Operations Brain — Knowledge Graph Visualizer
 * D3 force-directed graph using react-force-graph-2d.
 * Loaded dynamically (client-only) to avoid SSR errors.
 *
 * Fixes:
 *  - Nodes no longer disappear on hold/drag: canvas callbacks use refs so
 *    they never hold stale closure values; NaN/undefined position guard added.
 *  - Full light-mode support: canvas bg, link colour and label colour are
 *    derived from the active theme.
 */
"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useCallback } from "react";
import { getFullGraph } from "@/lib/api";
import { THEME } from "@/lib/theme";
import { useTheme } from "@/lib/theme-context";
import type { GraphData, GraphNode } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";

// Dynamic import — ForceGraph uses browser-only APIs
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const NODE_TYPE_LABELS: Record<string, string> = {
  equipment:          "Equipment",
  incident:           "Incident",
  defect:             "Defect",
  maintenance:        "Maintenance",
  maintenance_overdue:"Overdue",
  document:           "Document",
  regulation:         "Regulation",
  technician:         "Technician",
  spare_part:         "Spare Part",
  component:          "Component",
  location:           "Location",
  project:            "Project",
  plant:              "Plant",
  work_order:         "Work Order",
  inspection:         "Inspection",
  safety_procedure:   "Safety Procedure",
};

export function GraphView() {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Canvas-level colours that CSS selectors cannot reach
  const canvasBg    = isDark ? "#1a1a1a" : "#ffffff";
  const linkColorStr = isDark ? "#3a3a3a" : "#c8cdd5";
  const labelColor   = isDark ? "#a0a0a0" : "#374151";
  const selectRing   = isDark ? "#f9f9f9" : "#111827";

  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightedNodes, setHighlightedNodes] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ w: 800, h: 600 });

  // Refs so canvas callbacks always read current values without stale closures
  const selectedNodeRef   = useRef<GraphNode | null>(null);
  const highlightedRef    = useRef<Set<string>>(new Set());
  const labelColorRef     = useRef(labelColor);
  const selectRingRef     = useRef(selectRing);
  const draggingRef       = useRef(false);

  // Keep refs in sync with state/theme
  useEffect(() => { selectedNodeRef.current   = selectedNode;   }, [selectedNode]);
  useEffect(() => { highlightedRef.current    = highlightedNodes; }, [highlightedNodes]);
  useEffect(() => { labelColorRef.current     = labelColor;      }, [labelColor]);
  useEffect(() => { selectRingRef.current     = selectRing;      }, [selectRing]);

  useEffect(() => {
    getFullGraph().then(setGraphData).catch(console.error);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ w: width, h: height });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const handleNodeClick = useCallback((node: GraphNode) => {
    // Ignore clicks that are the tail-end of a drag gesture
    if (draggingRef.current) return;
    setSelectedNode(prev => {
      if (prev?.id === (node as GraphNode).id) {
        // Deselect on second click
        setHighlightedNodes(new Set());
        return null;
      }
      const connected = new Set<string>([(node as GraphNode).id]);
      graphData.links.forEach(l => {
        const src = typeof l.source === "object" ? (l.source as GraphNode).id : l.source;
        const tgt = typeof l.target === "object" ? (l.target as GraphNode).id : l.target;
        if (src === (node as GraphNode).id) connected.add(tgt);
        if (tgt === (node as GraphNode).id) connected.add(src);
      });
      setHighlightedNodes(connected);
      return node as GraphNode;
    });
  }, [graphData.links]);

  // onNodeDrag fires continuously during drag — set flag on first call
  const handleNodeDrag    = useCallback(() => { draggingRef.current = true; }, []);
  const handleNodeDragEnd = useCallback(() => {
    // Small delay so the click event (fired after pointerup) sees dragging=true
    setTimeout(() => { draggingRef.current = false; }, 100);
  }, []);

  // Stable canvas callback — reads everything through refs, never stale
  const nodeCanvasObject = useCallback((
    node: object,
    ctx: CanvasRenderingContext2D,
    globalScale: number,
  ) => {
    const n = node as GraphNode & { x?: number; y?: number };
    const x = n.x ?? 0;
    const y = n.y ?? 0;
    // Guard: skip nodes whose positions haven't been assigned yet by D3
    if (!isFinite(x) || !isFinite(y)) return;

    const baseColor = THEME.graphNodeColor[n.type] ?? "#6b7280";
    const highlighted = highlightedRef.current;
    let color: string;
    if (highlighted.size === 0) {
      color = baseColor;
    } else {
      // Dim non-highlighted nodes to 44% opacity (visible but clearly inactive)
      color = highlighted.has(n.id) ? baseColor : `${baseColor}55`;
    }

    const radius = Math.sqrt(Math.max(1, n.val ?? 10)) * 2;

    // Circle fill
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Selection ring
    if (selectedNodeRef.current?.id === n.id) {
      ctx.strokeStyle = selectRingRef.current;
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Label (only draw at zoom levels where text is legible)
    const fontSize = Math.max(6, 10 / globalScale);
    if (fontSize < 16) {
      const label = n.name.split("\n")[0];
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.fillStyle = highlighted.size === 0 || highlighted.has(n.id)
        ? labelColorRef.current
        : `${labelColorRef.current}88`;
      ctx.textAlign = "center";
      ctx.fillText(label, x, y + radius + fontSize + 1);
    }
  }, []); // stable — uses refs only

  // Stable pointer-area callback keeps drag hit zones consistent
  const nodePointerAreaPaint = useCallback((
    node: object,
    colour: string,
    ctx: CanvasRenderingContext2D,
  ) => {
    const n = node as GraphNode & { x?: number; y?: number };
    const x = n.x ?? 0;
    const y = n.y ?? 0;
    if (!isFinite(x) || !isFinite(y)) return;
    ctx.fillStyle = colour;
    ctx.beginPath();
    ctx.arc(x, y, Math.sqrt(Math.max(1, n.val ?? 10)) * 2, 0, 2 * Math.PI);
    ctx.fill();
  }, []);

  const getLinkColor = useCallback(() => linkColorStr, [linkColorStr]);
  const getNodeLabel = useCallback(
    (n: object) => `${(n as GraphNode).name}\n[${NODE_TYPE_LABELS[(n as GraphNode).type] ?? (n as GraphNode).type}]`,
    [],
  );
  const getLinkLabel = useCallback((l: object) => (l as { label?: string }).label ?? "", []);

  return (
    <div className="flex gap-4 flex-1 min-h-0">
      {/* Legend */}
      <div className="w-48 flex-shrink-0 bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-3 overflow-y-auto">
        <p className="text-xs font-semibold text-[#a0a0a0] mb-3">Node Types</p>
        {Object.entries(NODE_TYPE_LABELS).map(([type, label]) => (
          <div key={type} className="flex items-center gap-2 mb-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full flex-shrink-0"
              style={{ background: THEME.graphNodeColor[type] ?? "#6b7280" }}
            />
            <span className="text-xs text-[#6b7280]">{label}</span>
          </div>
        ))}

        {selectedNode && (
          <div className="mt-4 pt-4 border-t border-[#2a2a2a]">
            <p className="text-xs font-semibold text-[#a0a0a0] mb-2">Selected</p>
            <div className="space-y-1">
              <p className="text-xs font-mono text-amber-400">{selectedNode.id}</p>
              <p className="text-xs text-[#f9f9f9] leading-tight">{selectedNode.name}</p>
              <Badge variant="muted">{NODE_TYPE_LABELS[selectedNode.type] ?? selectedNode.type}</Badge>
            </div>
            <button
              onClick={() => { setSelectedNode(null); setHighlightedNodes(new Set()); }}
              className="mt-2 text-xs text-[#6b7280] hover:text-[#a0a0a0] underline"
            >
              Clear selection
            </button>
          </div>
        )}

        <div className="mt-4 pt-4 border-t border-[#2a2a2a]">
          <p className="text-xs text-[#6b7280]">{graphData.nodes.length} nodes</p>
          <p className="text-xs text-[#6b7280]">{graphData.links.length} relationships</p>
          {graphData.nodes.length > 0 && (
            <p className="text-xs text-[#4b5563] mt-1">Click node to explore · drag to reposition</p>
          )}
        </div>
      </div>

      {/* Graph Canvas */}
      <div ref={containerRef} className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl overflow-hidden">
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            graphData={graphData as never}
            width={dimensions.w}
            height={dimensions.h}
            backgroundColor={canvasBg}
            nodeVal={((n: object) => (n as GraphNode).val ?? 10) as never}
            nodeLabel={getNodeLabel as never}
            linkColor={getLinkColor as never}
            linkWidth={1.5}
            linkLabel={getLinkLabel as never}
            onNodeClick={handleNodeClick as never}
            onNodeDrag={handleNodeDrag as never}
            onNodeDragEnd={handleNodeDragEnd as never}
            enableNodeDrag
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            warmupTicks={40}
            nodeCanvasObject={nodeCanvasObject as never}
            nodePointerAreaPaint={nodePointerAreaPaint as never}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-[#6b7280]">Loading knowledge graph…</p>
          </div>
        )}
      </div>
    </div>
  );
}
