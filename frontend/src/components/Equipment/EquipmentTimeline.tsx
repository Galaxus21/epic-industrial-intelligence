/**
 * AI Operations Brain — Equipment Timeline Component
 * Vertical timeline showing installation, incidents, and maintenance history.
 */
import { format, parseISO } from "date-fns";
import { Wrench, AlertTriangle, Package, type LucideIcon } from "lucide-react";
import type { TimelineEvent } from "@/lib/types";

interface EquipmentTimelineProps {
  events: TimelineEvent[];
}

const EVENT_CONFIG: Record<string, { icon: LucideIcon; colorClass: string; bgClass: string }> = {
  installation: { icon: Package, colorClass: "text-blue-400", bgClass: "bg-blue-500/20 border-blue-500/40" },
  incident:     { icon: AlertTriangle, colorClass: "text-orange-400", bgClass: "bg-orange-500/20 border-orange-500/40" },
  maintenance:  { icon: Wrench, colorClass: "text-emerald-400", bgClass: "bg-emerald-500/20 border-emerald-500/40" },
};

const SEVERITY_BORDER: Record<string, string> = {
  critical: "border-l-red-500",
  high:     "border-l-orange-500",
  medium:   "border-l-amber-500",
  warning:  "border-l-orange-500",
  success:  "border-l-emerald-500",
  info:     "border-l-blue-500",
};

export function EquipmentTimeline({ events }: EquipmentTimelineProps) {
  if (events.length === 0) {
    return <p className="text-sm text-[#6b7280] text-center py-8">No timeline events found.</p>;
  }

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-4 top-0 bottom-0 w-px bg-[#2a2a2a]" />

      <div className="space-y-4">
        {events.slice().reverse().map((event, idx) => {
          const config = EVENT_CONFIG[event.type] ?? EVENT_CONFIG.maintenance;
          const Icon = config.icon;
          const borderColor = SEVERITY_BORDER[event.severity] ?? "border-l-[#2a2a2a]";

          return (
            <div key={idx} className="flex gap-3 pl-8 relative">
              {/* Icon */}
              <div className={`absolute left-0 flex items-center justify-center w-8 h-8 rounded-full border ${config.bgClass}`}>
                <Icon size={14} className={config.colorClass} />
              </div>

              {/* Content */}
              <div className={`flex-1 bg-[#1a1a1a] border border-[#2a2a2a] border-l-2 ${borderColor} rounded-r-lg p-3`}>
                <div className="flex items-start justify-between gap-2 mb-1">
                  <p className="text-xs font-semibold text-[#f9f9f9] leading-tight">{event.title}</p>
                  <p className="text-xs font-mono text-[#6b7280] flex-shrink-0">
                    {event.date ? format(parseISO(event.date), "MMM d, yyyy") : "—"}
                  </p>
                </div>
                <p className="text-xs text-[#a0a0a0] leading-relaxed">{event.description}</p>

                {event.detail && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {(() => {
                      const d = event.detail as Record<string, unknown>;
                      return (
                        <>
                          {d.downtime_hours != null && (
                            <span className="text-xs text-orange-400">⏱ {String(d.downtime_hours)}h downtime</span>
                          )}
                          {d.cost_usd != null && (
                            <span className="text-xs text-[#6b7280]">💰 ${Number(d.cost_usd).toLocaleString()}</span>
                          )}
                          {d.technician != null && (
                            <span className="text-xs text-emerald-400">👷 {String(d.technician)}</span>
                          )}
                          {d.vibration != null && (
                            <span className="text-xs text-blue-400">📈 {String(d.vibration)} mm/s</span>
                          )}
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
