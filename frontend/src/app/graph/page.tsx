/**
 * AI Operations Brain — Knowledge Graph Page
 * Wraps the dynamic ForceGraph (no SSR) in a server-rendered page.
 */
import { GraphView } from "@/components/KnowledgeGraph/GraphView";

export default function GraphPage() {
  return (
    <div className="p-6 h-full flex flex-col" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      <div className="mb-4">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Plant Knowledge Graph</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          Every entity — equipment, incidents, work orders, feedback, and lessons learned — connected in one interactive graph.
          Click a node to explore.
        </p>
      </div>
      <GraphView />
    </div>
  );
}
