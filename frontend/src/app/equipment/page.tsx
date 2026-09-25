/**
 * AI Operations Brain — Equipment List Page
 * Shows all registered equipment as a flat list.
 * Links to individual equipment detail pages.
 */
import Link from "next/link";
import { listEquipment } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { AlertTriangle, BrainCircuit, Activity, HardDrive } from "lucide-react";
import type { Equipment } from "@/lib/types";
import { accentClass, accentStyle } from "@/lib/accentStyle";

export const dynamic = "force-dynamic";

function healthColor(score: number | null): string {
  if (score == null) return "#6b7280";
  if (score >= 85) return "#10b981";
  if (score >= 65) return "#f59e0b";
  if (score >= 45) return "#f97316";
  return "#ef4444";
}

function EquipmentRow({ eq }: { eq: Equipment }) {
  const hc = healthColor(eq.health_score);
  const hasAlert = eq.status?.toLowerCase().includes("alert") || eq.status?.toLowerCase().includes("alarm");
  return (
    <Link
      href={`/equipment/${eq.id}`}
      className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#111] border-b border-[#1a1a1a] last:border-0 transition-colors group"
    >
      <HardDrive size={13} className="flex-shrink-0 text-[#4b5563] group-hover:text-amber-400 transition-colors" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[#6b7280]">{eq.id}</span>
          {hasAlert && <AlertTriangle size={10} className="text-orange-400 flex-shrink-0" />}
        </div>
        <p className="text-sm text-[#e0e0e0] truncate leading-tight">{eq.name}</p>
        <p className="text-[10px] text-[#4b5563]">{eq.type}</p>
      </div>
      <div className="flex-shrink-0 flex items-center gap-2">
        {eq.health_score != null && (
          <div className="flex items-center gap-1">
            <div className="w-12 h-1 bg-[#252525] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${eq.health_score}%`, background: hc }}
              />
            </div>
            <span className={`text-[10px] font-mono ${accentClass}`} style={accentStyle(hc)}>{eq.health_score}%</span>
          </div>
        )}
        <Badge variant={
          eq.criticality === "Critical" ? "critical" :
          eq.criticality === "High" ? "high" : "muted"
        }>
          {eq.criticality}
        </Badge>
      </div>
    </Link>
  );
}

export default async function EquipmentPage() {
  const allEquipment = await listEquipment().catch(() => [] as Equipment[]);

  const alertCount = allEquipment.filter(
    e => e.status?.toLowerCase().includes("alert") || e.status?.toLowerCase().includes("alarm")
  ).length;
  const lowHealthCount = allEquipment.filter(e => e.health_score != null && e.health_score < 75).length;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f9f9f9] flex items-center gap-2">
            <HardDrive size={20} className="text-amber-400" />
            Equipment Registry
          </h1>
          <p className="text-xs text-[#6b7280] mt-0.5">
            {allEquipment.length} assets
          </p>
        </div>
        <div className="flex items-center gap-3">
          {alertCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-orange-500/10 border border-orange-500/20">
              <AlertTriangle size={12} className="text-orange-400" />
              <span className="text-xs text-orange-400 font-medium">{alertCount} active alert{alertCount !== 1 ? "s" : ""}</span>
            </div>
          )}
          {lowHealthCount > 0 && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <Activity size={12} className="text-amber-400" />
              <span className="text-xs text-amber-400 font-medium">{lowHealthCount} low health</span>
            </div>
          )}
          <Link
            href="/query"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/25 text-xs text-amber-400 hover:bg-amber-500/25 transition-colors"
          >
            <BrainCircuit size={12} /> Ask AI
          </Link>
        </div>
      </div>

      {allEquipment.length > 0 && (
        <div className="border border-[#1e1e1e] rounded-xl overflow-hidden">
          {allEquipment.map(eq => <EquipmentRow key={eq.id} eq={eq} />)}
        </div>
      )}

      {allEquipment.length === 0 && (
        <div className="text-center py-12 text-[#4b5563]">
          <HardDrive size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No equipment found.</p>
          <p className="text-xs mt-1">
            Generate demo data from the sidebar or register equipment via the API.
          </p>
        </div>
      )}
    </div>
  );
}
