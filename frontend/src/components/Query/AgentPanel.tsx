/**
 * AI Operations Brain — Agent Panel
 * Shows 5+ agents activating/completing with animated status indicators.
 */
import { CheckCircle2, Loader2, Clock } from "lucide-react";
import type { AgentEvent } from "@/lib/types";
import { THEME } from "@/lib/theme";
import clsx from "clsx";

interface AgentPanelProps {
  events: AgentEvent[];
  isRunning: boolean;
}

const AGENT_ORDER: AgentEvent["agent"][] = [
  "equipment_brain",
  "maintenance_advisor",
  "compliance_agent",
  "lessons_learned",
  "document_intelligence",
  "synthesizer",
];

export function AgentPanel({ events, isRunning }: AgentPanelProps) {
  const eventMap = new Map(events.map(e => [e.agent, e]));

  return (
    <div className="space-y-2.5">
      {AGENT_ORDER.map((agentId, idx) => {
        const event = eventMap.get(agentId);
        const color = THEME.agentColor[agentId] ?? "#6b7280";
        const label = THEME.agentLabel[agentId] ?? agentId;
        const isActive = event?.status === "active";
        const isDone = event?.status === "done";
        const isPending = !event;
        const isCurrentlyActive = isActive && isRunning;

        return (
          <div
            key={agentId}
            className="flex items-start gap-2.5 transition-opacity"
            style={{ opacity: isPending ? 0.35 : 1 }}
            title={isPending ? `${label} — waiting` : isDone ? `${label} — completed` : `${label} — analysing…`}
          >
            {/* Status indicator */}
            <div className="flex-shrink-0 mt-0.5">
              {isDone ? (
                <CheckCircle2 size={16} style={{ color }} />
              ) : isCurrentlyActive ? (
                <Loader2 size={16} className="animate-spin" style={{ color }} />
              ) : (
                <Clock size={16} className="text-[#4b5563]" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold" style={{ color: isDone || isCurrentlyActive ? color : "#4b5563" }}>
                  {label}
                </p>
                {isDone && <span className="text-xs text-[#6b7280] font-mono">✓</span>}
              </div>
              {event?.message && (
                <p className="text-xs text-[#6b7280] mt-0.5 leading-relaxed">{event.message}</p>
              )}

              {/* Summary data for non-synthesizer agents */}
              {isDone && agentId !== "synthesizer" && event?.data != null && (
                <AgentDataSummary data={event.data} color={color} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgentDataSummary({ data, color }: { data: unknown; color: string }) {
  const highlights = (data as Record<string, unknown>)?.highlights as
    Array<{ label: string; value: string; level: "info" | "warn" | "critical" }> | undefined;

  if (!highlights?.length) return null;

  return (
    <div className="flex flex-wrap gap-1 mt-1.5">
      {highlights.map((h, i) => (
        <span
          key={i}
          className={clsx(
            "px-1.5 py-0.5 rounded text-xs font-medium",
            h.level === "critical" && "bg-red-500/15 text-red-400",
            h.level === "warn"     && "bg-amber-500/15 text-amber-400",
          )}
          style={h.level === "info" ? { background: `${color}20`, color } : undefined}
          title={`${h.label}: ${h.value}`}
        >
          {h.label}: {h.value}
        </span>
      ))}
    </div>
  );
}
