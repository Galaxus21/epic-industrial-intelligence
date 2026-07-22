/**
 * AI Operations Brain — Plant Digital Twin
 * Phase 4 of the IndustrialGPT vision.
 *
 * Renders the living plant hierarchy: Plant → Area → Equipment.
 * Each node shows real-time health, alert count, and status colour.
 * Click equipment to open its detail page.
 */
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getPlantTree } from "@/lib/api";
import { usePageState } from "@/lib/page-state";
import {
  Factory, ChevronDown, ChevronUp, AlertTriangle,
  Loader2, Cog, Zap, Database, LayoutGrid, Activity, type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ─────────────────────────────────────────────────────────────────────

type EquipmentNode = {
  id: string;
  name: string;
  type: string;
  category: string;
  status: string;
  status_color: string;
  health_score: number | null;
  failure_probability: number | null;
  criticality: string;
  alerts: string[];
  maintenance_due_days: number | null;
};

type AreaNode = {
  id: string;
  name: string;
  full_name: string;
  icon: string;
  equipment_count: number;
  health: number | null;
  status: string;
  alert_count: number;
  equipment: EquipmentNode[];
};

type PlantTree = {
  id: string;
  name: string;
  site: string;
  equipment_count: number;
  health: number | null;
  status: string;
  alert_count: number;
  areas: AreaNode[];
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  green: "#10b981", amber: "#f59e0b", orange: "#f97316", red: "#ef4444", gray: "#6b7280",
};
const AREA_STATUS_BADGE: Record<string, { cls: string; label: string }> = {
  normal:   { cls: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20", label: "Normal" },
  warning:  { cls: "bg-amber-500/10 text-amber-400 border-amber-500/20",       label: "Warning" },
  degraded: { cls: "bg-orange-500/10 text-orange-400 border-orange-500/20",    label: "Degraded" },
  alarm:    { cls: "bg-red-500/10 text-red-400 border-red-500/20",             label: "Alarm" },
  offline:  { cls: "bg-[#2a2a2a] text-[#4b5563] border-[#333]",               label: "Offline" },
  empty:    { cls: "bg-[#2a2a2a] text-[#4b5563] border-[#333]",               label: "Empty" },
};

const AREA_ICON: Record<string, LucideIcon> = {
  factory: Factory,
  cog: Cog,
  zap: Zap,
  database: Database,
};

function HealthRing({ score, size = 36 }: { score: number | null; size?: number }) {
  if (score == null) return <div style={{ width: size, height: size }} className="rounded-full bg-[#252525] flex items-center justify-center"><span className="text-[10px] text-[#4b5563]">—</span></div>;
  const color = score >= 85 ? "#10b981" : score >= 65 ? "#f59e0b" : score >= 45 ? "#f97316" : "#ef4444";
  const r = (size - 4) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width={size} height={size}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#252525" strokeWidth={3} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={3}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x={size / 2} y={size / 2 + 4} textAnchor="middle" fill={color} fontSize="9" fontWeight="700">{score}</text>
    </svg>
  );
}

// ── Equipment card ─────────────────────────────────────────────────────────────

function EquipmentCard({ eq }: { eq: EquipmentNode }) {
  const dotColor = STATUS_COLOR[eq.status_color] ?? "#6b7280";
  const hasAlerts = eq.alerts.length > 0;
  return (
    <Link
      href={`/equipment/${eq.id}`}
      className={clsx(
        "block bg-[#141414] border rounded-xl p-3 hover:border-amber-500/30 transition-all group",
        hasAlerts ? "border-orange-500/30" : "border-[#252525]"
      )}
    >
      <div className="flex items-start gap-2.5">
        <HealthRing score={eq.health_score} size={34} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span
              className="w-1.5 h-1.5 rounded-full flex-shrink-0"
              style={{ background: dotColor }}
            />
            <span className="text-[10px] font-mono text-[#6b7280] truncate">{eq.id}</span>
            {hasAlerts && <AlertTriangle size={9} className="text-orange-400 flex-shrink-0" />}
          </div>
          <p className="text-xs text-[#e0e0e0] font-medium truncate group-hover:text-[#f9f9f9] transition-colors">{eq.name}</p>
          <p className="text-[10px] text-[#4b5563] truncate">{eq.type}</p>
        </div>
      </div>

      {hasAlerts && (
        <div className="mt-2 space-y-0.5">
          {eq.alerts.slice(0, 2).map((a, i) => (
            <p key={i} className="text-[10px] text-orange-400 truncate">⚠ {a}</p>
          ))}
          {eq.alerts.length > 2 && (
            <p className="text-[10px] text-[#4b5563]">+{eq.alerts.length - 2} more</p>
          )}
        </div>
      )}

      {!hasAlerts && eq.maintenance_due_days !== null && eq.maintenance_due_days <= 14 && (
        <p className="mt-1.5 text-[10px] text-amber-400">
          {eq.maintenance_due_days <= 0 ? "⚠ Maintenance overdue" : `Maint. due in ${eq.maintenance_due_days}d`}
        </p>
      )}
    </Link>
  );
}

// ── Area panel ────────────────────────────────────────────────────────────────

function AreaPanel({ area }: { area: AreaNode }) {
  const { plant: plantState, updatePlant } = usePageState();
  const defaultOpen = area.alert_count > 0 || area.equipment_count > 0;
  const storedOpen = plantState.areaOpenStates[area.id];
  const [open, setOpen] = useState(storedOpen !== undefined ? storedOpen : defaultOpen);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    updatePlant({ areaOpenStates: { ...plantState.areaOpenStates, [area.id]: next } });
  };
  const badge = AREA_STATUS_BADGE[area.status] ?? AREA_STATUS_BADGE.normal;
  const AreaIcon = AREA_ICON[area.icon] ?? Factory;

  return (
    <div className="bg-[#0f0f0f] border border-[#252525] rounded-2xl overflow-hidden">
      {/* Area header */}
      <button
        onClick={toggle}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-[#141414] transition-colors"
      >
        <AreaIcon size={16} className="text-amber-400 flex-shrink-0" />
        <div className="flex-1 text-left min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] truncate">{area.name}</p>
          <p className="text-[10px] text-[#4b5563] truncate">{area.full_name}</p>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
          {area.health !== null && <HealthRing score={area.health} size={30} />}
          <span className={clsx("text-[10px] px-2 py-0.5 rounded-full border font-semibold", badge.cls)}>
            {badge.label}
          </span>
          {area.alert_count > 0 && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
              {area.alert_count} alert{area.alert_count !== 1 ? "s" : ""}
            </span>
          )}
          <span className="text-[10px] text-[#4b5563]">{area.equipment_count} equip.</span>
          {open ? <ChevronUp size={13} className="text-[#4b5563]" /> : <ChevronDown size={13} className="text-[#4b5563]" />}
        </div>
      </button>

      {/* Equipment grid */}
      {open && (
        <div className="px-5 pb-5">
          {area.equipment.length === 0 ? (
            <p className="text-xs text-[#4b5563] italic">No equipment in this area.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5 gap-3">
              {area.equipment.map(eq => <EquipmentCard key={eq.id} eq={eq} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PlantPage() {
  const [tree, setTree] = useState<PlantTree | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    getPlantTree()
      .then(d => setTree(d as PlantTree))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-full py-24 gap-3 text-[#4b5563]">
      <Loader2 size={18} className="animate-spin text-amber-400" />
      <span className="text-sm">Loading plant model…</span>
    </div>
  );

  if (error || !tree) return (
    <div className="flex items-center justify-center h-full py-24 gap-2 text-red-400">
      <AlertTriangle size={16} /> <span className="text-sm">Failed to load plant data.</span>
    </div>
  );

  const plantStatusColor = tree.status === "alarm" ? "text-red-400" : "text-emerald-400";

  return (
    <div className="p-6">
      {/* Plant header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <Factory size={22} className="text-amber-400" />
          <div>
            <h1 className="text-xl font-bold text-[#f9f9f9]">{tree.name}</h1>
            <p className="text-xs text-[#6b7280] mt-0.5">{tree.site} — Digital Twin</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <HealthRing score={tree.health} size={42} />
          <div className="text-right">
            <p className={clsx("text-sm font-semibold", plantStatusColor)}>
              {tree.status === "alarm" ? "⚠ Alarm Condition" : "✓ Normal Operation"}
            </p>
            <p className="text-xs text-[#4b5563]">
              {tree.equipment_count} equipment · {tree.alert_count} alert{tree.alert_count !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* Plant KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Areas", value: tree.areas.length, icon: LayoutGrid, color: "text-sky-400" },
          { label: "Equipment", value: tree.equipment_count, icon: Cog, color: "text-amber-400" },
          { label: "Active Alarms", value: tree.alert_count, icon: AlertTriangle, color: tree.alert_count > 0 ? "text-red-400" : "text-emerald-400" },
          { label: "Plant Health", value: tree.health != null ? `${tree.health}%` : "—", icon: Activity, color: "text-emerald-400" },
        ].map(kpi => (
          <div key={kpi.label} className="bg-[#141414] border border-[#252525] rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <kpi.icon size={13} className={kpi.color} />
              <span className="text-xs text-[#6b7280]">{kpi.label}</span>
            </div>
            <p className={clsx("text-2xl font-bold", kpi.color)}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Areas */}
      <div className="space-y-4">
        {tree.areas.map(area => (
          <AreaPanel key={area.id} area={area} />
        ))}
      </div>
    </div>
  );
}
