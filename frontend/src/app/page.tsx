/**
 * AI Operations Brain — Dashboard Page (/)
 * Shows all plant equipment health scores and plant-level KPI summary.
 */
import { listEquipment } from "@/lib/api";
import { EquipmentGrid } from "@/components/Dashboard/EquipmentGrid";
import { AlertTriangle, CheckCircle2, Gauge, Activity } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const equipment = await listEquipment().catch(() => []);

  const criticalCount = equipment.filter(e => (e.failure_probability ?? 0) >= 15).length;
  const avgHealth = equipment.length
    ? Math.round(equipment.filter(e => e.health_score != null).reduce((s, e) => s + (e.health_score ?? 0), 0) / (equipment.filter(e => e.health_score != null).length || 1))
    : 0;
  const overdueMaint = equipment.filter(e => (e.maintenance_due_days ?? 99) <= 0).length;
  const compliantCount = equipment.filter(e => (e.compliance_score ?? 0) >= 90).length;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-[#f9f9f9]">Plant Operations Dashboard</h1>
        <p className="text-sm text-[#6b7280] mt-1">
          {equipment.length} equipment across{" "}
          {new Set(equipment.map(e => e.location).filter(Boolean)).size || "all"} locations
          {" "}— Real-time health &amp; AI insights
        </p>
      </div>

      {/* KPI Summary Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <KpiCard
          icon={<Gauge size={18} className="text-amber-500" />}
          label="Avg. Health Score"
          value={`${avgHealth}%`}
          sub="across all equipment"
          color={avgHealth >= 85 ? "#10b981" : avgHealth >= 65 ? "#f59e0b" : "#ef4444"}
        />
        <KpiCard
          icon={<AlertTriangle size={18} className="text-orange-400" />}
          label="At-Risk Equipment"
          value={`${criticalCount}`}
          sub="failure probability >15%"
          color={criticalCount > 0 ? "#f97316" : "#10b981"}
        />
        <KpiCard
          icon={<CheckCircle2 size={18} className="text-emerald-400" />}
          label="Compliance Rate"
          value={`${Math.round((compliantCount / equipment.length) * 100)}%`}
          sub={`${compliantCount} / ${equipment.length} compliant`}
          color="#10b981"
        />
        <KpiCard
          icon={<Activity size={18} className="text-blue-400" />}
          label="Maintenance Overdue"
          value={`${overdueMaint}`}
          sub="immediate attention"
          color={overdueMaint > 0 ? "#ef4444" : "#10b981"}
        />
      </div>

      {/* Equipment Grid */}
      <EquipmentGrid equipment={equipment} />
    </div>
  );
}

function KpiCard({
  icon, label, value, sub, color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <p className="text-xs text-[#6b7280]">{label}</p>
      </div>
      <p className="text-2xl font-bold" style={{ color }}>{value}</p>
      <p className="text-xs text-[#6b7280] mt-1">{sub}</p>
    </div>
  );
}
