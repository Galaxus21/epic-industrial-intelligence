/**
 * AI Operations Brain — Equipment Grid
 * Dashboard cards showing health score, risk, and maintenance status.
 */
"use client";

import Link from "next/link";
import { AlertTriangle, Clock, Activity, Sparkles, Plus } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import type { Equipment } from "@/lib/types";
import { accentClass, accentStyle } from "@/lib/accentStyle";

interface EquipmentGridProps {
  equipment: Equipment[];
}

function getRiskVariant(score: number | null): "critical" | "high" | "medium" | "low" {
  if (score == null) return "low";
  if (score >= 80) return "critical";
  if (score >= 50) return "high";
  if (score >= 25) return "medium";
  return "low";
}

function HealthBar({ value }: { value: number }) {
  const color = value >= 85 ? "#10b981" : value >= 65 ? "#f59e0b" : value >= 45 ? "#f97316" : "#ef4444";
  return (
    <div className="h-1.5 w-full bg-[#2a2a2a] rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${value}%`, backgroundColor: color }}
      />
    </div>
  );
}

function EquipmentCard({ eq }: { eq: Equipment }) {
  const riskVariant = getRiskVariant(eq.failure_probability ?? null);
  const maintenanceUrgent = eq.maintenance_due_days != null && eq.maintenance_due_days <= 7;
  const isDiscovered = eq.discovered === true;
  const sourceDocs = eq.source_documents ?? [];
  const healthColor =
    eq.health_score == null ? "#6b7280" :
    eq.health_score >= 85 ? "#10b981" : eq.health_score >= 65 ? "#f59e0b" : eq.health_score >= 45 ? "#f97316" : "#ef4444";

  return (
    <Link href={`/equipment/${eq.id}`}>
      <div className={`bg-[#1f1f1f] border rounded-xl p-4 hover:bg-[#242424] transition-all cursor-pointer group ${isDiscovered ? "border-purple-500/30 hover:border-purple-500/50" : "border-[#2a2a2a] hover:border-[#444]"}`}>
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <p className="text-xs font-mono text-[#6b7280]">{eq.id}</p>
              {isDiscovered && (
                <span className="flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  <Sparkles size={9} /> AI Discovered
                </span>
              )}
            </div>
            <h3 className="text-sm font-semibold text-[#f9f9f9] truncate group-hover:text-amber-400 transition-colors">
              {eq.name}
            </h3>
            <p className="text-xs text-[#6b7280] truncate mt-0.5">{eq.type}</p>
          </div>
          {eq.failure_probability != null ? (
            <Badge
              variant={(eq.failure_probability ?? 0) >= 15 ? "high" : "low"}
              title={`Failure probability: ${eq.failure_probability}% — estimated likelihood of failure in the next 30 days`}
            >
              {eq.failure_probability}% risk
            </Badge>
          ) : (
            <Badge variant="muted" title="Failure probability not yet calculated">Pending</Badge>
          )}
        </div>

        {/* Health Score */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-[#6b7280]">Health Score</span>
            <span
              className={`text-sm font-bold ${accentClass}`}
              style={accentStyle(healthColor)}
              title={eq.health_score != null ? `Health score ${eq.health_score}% — ${eq.health_score >= 85 ? 'Good condition' : eq.health_score >= 65 ? 'Monitor closely' : eq.health_score >= 45 ? 'Needs attention' : 'Critical condition'}` : 'Health score not yet available'}
            >
              {eq.health_score != null ? `${eq.health_score}%` : "—"}
            </span>
          </div>
          <div title={eq.health_score != null ? `Health score: ${eq.health_score}%` : 'Not yet measured'}>
            <HealthBar value={eq.health_score ?? 0} />
          </div>
        </div>

        {/* Metrics Row */}
        {isDiscovered ? (
          <div className="mt-3 pt-3 border-t border-[#2a2a2a] space-y-1">
            <p className="text-xs text-purple-400 flex items-center gap-1">
              <Sparkles size={10} /> Auto-discovered from document
            </p>
            {sourceDocs.slice(0, 1).map(d => (
              <p key={d} className="text-xs text-[#4b5563] truncate">{d}</p>
            ))}
            <p className="text-xs text-[#4b5563]">Add details → Equipment page</p>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-[#2a2a2a]">
            <div
              className="text-center"
              title={eq.compliance_score != null ? `Compliance score: ${eq.compliance_score}% — regulatory, maintenance & safety compliance` : 'Compliance score not yet calculated'}
            >
              <p className="text-xs text-[#6b7280]">Compliance</p>
              <p className={`text-xs font-semibold ${accentClass}`} style={accentStyle(eq.compliance_score != null && eq.compliance_score >= 90 ? "#10b981" : "#f59e0b")}>
                {eq.compliance_score != null ? `${eq.compliance_score}%` : "—"}
              </p>
            </div>
            <div
              className="text-center"
              title={eq.maintenance_due_days != null ? `Maintenance due in ${eq.maintenance_due_days} day${eq.maintenance_due_days !== 1 ? 's' : ''}${maintenanceUrgent ? ' — URGENT: overdue or due within 7 days' : ''}` : 'Maintenance schedule not available'}
            >
              <p className="text-xs text-[#6b7280]">Maint. Due</p>
              <p className={`text-xs font-semibold ${maintenanceUrgent ? "text-orange-400" : "text-[#a0a0a0]"}`}>
                {eq.maintenance_due_days != null ? `${eq.maintenance_due_days}d` : "—"}
              </p>
            </div>
            <div
              className="text-center"
              title={`Criticality: ${eq.criticality} — plant impact if this equipment fails`}
            >
              <p className="text-xs text-[#6b7280]">Criticality</p>
              <p className={`text-xs font-semibold ${eq.criticality === "Critical" ? "text-red-400" : eq.criticality === "High" ? "text-orange-400" : "text-[#a0a0a0]"}`}>
                {eq.criticality}
              </p>
            </div>
          </div>
        )}

        {/* Status Bar */}
        <div className="flex items-center gap-1.5 mt-3">
          <span
            className={`h-1.5 w-1.5 rounded-full ${eq.status.includes("Alert") ? "bg-orange-500 animate-pulse" : "bg-emerald-500"}`}
            title={`Operational status: ${eq.status}`}
          />
          <span className="text-xs text-[#6b7280]">{eq.status}</span>
          {maintenanceUrgent && (
            <span className="ml-auto text-xs text-orange-400 flex items-center gap-1">
              <Clock size={10} /> Maint. urgent
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

export function EquipmentGrid({ equipment }: EquipmentGridProps) {
  const alerts     = equipment.filter(e => !e.discovered && e.health_score != null && (e.health_score < 80 || (e.failure_probability ?? 0) > 15));
  const ok         = equipment.filter(e => !e.discovered && (e.health_score == null || (e.health_score >= 80 && (e.failure_probability ?? 0) <= 15)));
  const discovered = equipment.filter(e => e.discovered);

  return (
    <div>
      {alerts.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={14} className="text-orange-400" />
            <h2 className="text-sm font-semibold text-orange-400">Requires Attention ({alerts.length})</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {alerts.map(eq => <EquipmentCard key={eq.id} eq={eq} />)}
          </div>
        </div>
      )}

      {ok.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Activity size={14} className="text-emerald-400" />
            <h2 className="text-sm font-semibold text-emerald-400">Normal Operation ({ok.length})</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {ok.map(eq => <EquipmentCard key={eq.id} eq={eq} />)}
          </div>
        </div>
      )}

      {discovered.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={14} className="text-purple-400" />
            <h2 className="text-sm font-semibold text-purple-400">AI Discovered from Documents ({discovered.length})</h2>
            <span className="text-xs text-[#6b7280] ml-1">— found in uploaded documents, awaiting full configuration</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {discovered.map(eq => <EquipmentCard key={eq.id} eq={eq} />)}
          </div>
        </div>
      )}
    </div>
  );
}
