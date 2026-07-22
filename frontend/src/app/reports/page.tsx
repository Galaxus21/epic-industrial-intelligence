/**
 * AI Operations Brain — Reports & Analytics
 * Six pre-built reports: Overview · Equipment · Maintenance · Incidents · Work Orders · Safety
 */
"use client";

import { useState, useEffect } from "react";
import {
  getReportOverview, getReportEquipment, getReportMaintenance,
  getReportIncidents, getReportWorkOrders, getReportSafety,
  listIncidentReports, listPermits,
} from "@/lib/api";
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  BarChart3, Loader2, Factory, Cog, Wrench, AlertTriangle,
  ClipboardCheck, Shield, TrendingUp, TrendingDown, Minus, RefreshCw, GitBranch, type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

// ── Types ─────────────────────────────────────────────────────────────────────

type Overview = {
  plant_health: number | null; equipment_count: number;
  equipment_in_alarm: number; overdue_maintenance: number; compliance_issues: number;
  work_orders: { total: number; open: number; completed: number; completion_rate: number };
  incidents: { total: number; high_critical: number };
  checklists: { open: number; completed: number; completion_rate: number };
  active_permits: number;
  open_inspections: number;
  active_procedures: number;
  audit_events_7d: number;
};

// ── Palette ───────────────────────────────────────────────────────────────────

const PALETTE = ["#f59e0b", "#10b981", "#ef4444", "#3b82f6", "#8b5cf6", "#06b6d4", "#f97316"];
const SEV_COLOR: Record<string, string> = {
  Critical: "#ef4444", High: "#f97316", Medium: "#f59e0b", Low: "#10b981",
};

// ── Shared components ─────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, color, icon: Icon, trend }: {
  label: string; value: string | number; sub?: string; color?: string;
  icon?: LucideIcon; trend?: "up" | "down" | "stable";
}) {
  return (
    <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-2">
        {Icon && <Icon size={13} className="text-[#4b5563]" />}
        <span className="text-xs text-[#6b7280]">{label}</span>
        {trend === "up" && <TrendingUp size={10} className="text-orange-400 ml-auto" />}
        {trend === "down" && <TrendingDown size={10} className="text-emerald-400 ml-auto" />}
        {trend === "stable" && <Minus size={10} className="text-[#4b5563] ml-auto" />}
      </div>
      <p className={clsx("text-2xl font-bold font-mono", color ?? "text-[#f9f9f9]")}>{value}</p>
      {sub && <p className="text-[10px] text-[#4b5563] mt-0.5">{sub}</p>}
    </div>
  );
}

function SectionHeader({ title, icon: Icon }: { title: string; icon: LucideIcon }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={15} className="text-amber-400" />
      <h2 className="text-sm font-semibold text-[#f9f9f9]">{title}</h2>
    </div>
  );
}

// ── Tab renderers ─────────────────────────────────────────────────────────────

function OverviewTab({ data }: { data: Overview }) {
  const kpis = [
    { label: "Plant Health", value: data.plant_health != null ? `${data.plant_health}%` : "—", color: (data.plant_health ?? 100) >= 75 ? "text-emerald-400" : "text-orange-400", icon: Factory },
    { label: "Equipment in Alarm", value: data.equipment_in_alarm, color: data.equipment_in_alarm > 0 ? "text-red-400" : "text-emerald-400", icon: AlertTriangle },
    { label: "Overdue Maintenance", value: data.overdue_maintenance, color: data.overdue_maintenance > 0 ? "text-orange-400" : "text-emerald-400", icon: Wrench },
    { label: "Compliance Issues", value: data.compliance_issues, color: data.compliance_issues > 0 ? "text-orange-400" : "text-emerald-400", icon: Shield },
    { label: "Open Work Orders", value: data.work_orders.open, color: "text-purple-400", icon: ClipboardCheck },
    { label: "WO Completion Rate", value: `${data.work_orders.completion_rate}%`, color: "text-sky-400", icon: ClipboardCheck },
    { label: "High/Critical Incidents", value: data.incidents.high_critical, color: data.incidents.high_critical > 0 ? "text-red-400" : "text-emerald-400", icon: AlertTriangle },
    { label: "Total Incidents", value: data.incidents.total, color: "text-orange-400", icon: AlertTriangle },
    { label: "Active Permits (PTW)", value: data.active_permits ?? 0, color: (data.active_permits ?? 0) > 0 ? "text-yellow-400" : "text-emerald-400", icon: Shield },
    { label: "Open Inspections", value: data.open_inspections ?? 0, color: "text-teal-400", icon: ClipboardCheck },
    { label: "Active Procedures", value: data.active_procedures ?? 0, color: "text-sky-400", icon: BarChart3 },
    { label: "Audit Events (7d)", value: data.audit_events_7d, color: "text-amber-400", icon: BarChart3 },
  ];
  const pieData = [
    { name: "Open WOs", value: data.work_orders.open },
    { name: "Completed WOs", value: data.work_orders.completed },
    { name: "Open Checklists", value: data.checklists.open },
    { name: "Done Checklists", value: data.checklists.completed },
  ].filter(d => d.value > 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {kpis.map(k => <KpiCard key={k.label} {...k} />)}
      </div>
      {pieData.length > 0 && (
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
          <SectionHeader title="Work Orders & Checklists Distribution" icon={BarChart3} />
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                {pieData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 11, color: "#6b7280" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function EquipmentTab() {
  const [data, setData] = useState<{ equipment: unknown[] } | null>(null);
  useEffect(() => { getReportEquipment().then(d => setData(d as { equipment: unknown[] })).catch(() => {}); }, []);
  if (!data) return <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-amber-400" /></div>;

  type EqRow = { id: string; name: string; type: string; health_score: number | null; failure_probability: number | null; compliance_score: number | null; maintenance_due_days: number | null; status: string; criticality: string; alarm_sensors: string[]; open_work_orders: number };
  const rows = data.equipment as EqRow[];
  const chartData = rows.slice(0, 10).map(e => ({ name: e.id, health: e.health_score ?? 0, fp: e.failure_probability ?? 0 }));

  return (
    <div className="space-y-5">
      <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
        <SectionHeader title="Health Score vs Failure Probability (Top 10, worst first)" icon={Cog} />
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
            <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} />
            <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
            <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#6b7280" }} />
            <Bar dataKey="health" fill="#10b981" name="Health %" radius={[3, 3, 0, 0]} />
            <Bar dataKey="fp" fill="#ef4444" name="Fail Prob %" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[#1e1e1e] grid grid-cols-8 gap-2 text-[10px] font-semibold text-[#4b5563] uppercase">
          {["ID","Name","Type","Health","Fail Prob","Compliance","Maint Due","Open WOs"].map(h => <span key={h}>{h}</span>)}
        </div>
        {rows.map(eq => (
          <div key={eq.id} className="px-4 py-2 border-b border-[#0f0f0f] grid grid-cols-8 gap-2 text-xs hover:bg-[#161616] transition-colors">
            <span className="font-mono text-amber-400">{eq.id}</span>
            <span className="text-[#e0e0e0] truncate">{eq.name}</span>
            <span className="text-[#6b7280] truncate">{eq.type}</span>
            <span className={clsx("font-mono", (eq.health_score ?? 100) < 65 ? "text-red-400" : (eq.health_score ?? 100) < 80 ? "text-amber-400" : "text-emerald-400")}>
              {eq.health_score ?? "—"}%
            </span>
            <span className={clsx("font-mono", (eq.failure_probability ?? 0) > 30 ? "text-red-400" : (eq.failure_probability ?? 0) > 15 ? "text-orange-400" : "text-emerald-400")}>
              {eq.failure_probability ?? "—"}%
            </span>
            <span className={clsx("font-mono", (eq.compliance_score ?? 100) < 90 ? "text-orange-400" : "text-emerald-400")}>
              {eq.compliance_score ?? "—"}%
            </span>
            <span className={clsx("font-mono", (eq.maintenance_due_days ?? 999) <= 0 ? "text-red-400" : (eq.maintenance_due_days ?? 999) <= 7 ? "text-amber-400" : "text-[#6b7280]")}>
              {eq.maintenance_due_days != null ? (eq.maintenance_due_days <= 0 ? "OVERDUE" : `${eq.maintenance_due_days}d`) : "—"}
            </span>
            <span className={clsx("font-mono", eq.open_work_orders > 0 ? "text-purple-400" : "text-[#333]")}>{eq.open_work_orders}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MaintenanceTab() {
  const [data, setData] = useState<{ kpis: Record<string, number>; by_type: Record<string, number>; by_equipment: { equipment_id: string; total: number; completed: number; overdue: number }[]; recent_activity: Record<string, number> } | null>(null);
  useEffect(() => { getReportMaintenance().then(d => setData(d as typeof data)).catch(() => {}); }, []);
  if (!data) return <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-amber-400" /></div>;

  const kpis = data.kpis;
  const byTypeData = Object.entries(data.by_type).map(([name, value]) => ({ name, value }));
  const byEqData = data.by_equipment.slice(0, 8).map(e => ({ name: e.equipment_id, completed: e.completed, overdue: e.overdue, total: e.total }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Total Records" value={kpis.total_records} icon={Wrench} />
        <KpiCard label="Compliance Rate" value={`${kpis.compliance_rate_pct}%`} color={(kpis.compliance_rate_pct ?? 0) >= 80 ? "text-emerald-400" : "text-orange-400"} icon={Wrench} />
        <KpiCard label="Overdue" value={kpis.overdue} color={kpis.overdue > 0 ? "text-red-400" : "text-emerald-400"} icon={AlertTriangle} />
        <KpiCard label="Scheduled" value={kpis.scheduled} color="text-sky-400" icon={Wrench} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
          <SectionHeader title="By Maintenance Type" icon={Wrench} />
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={byTypeData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine>
                {byTypeData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
          <SectionHeader title="By Equipment (Overdue vs Completed)" icon={Cog} />
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={byEqData} layout="vertical" margin={{ top: 0, right: 8, left: 30, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
              <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 9 }} />
              <YAxis type="category" dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} />
              <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
              <Bar dataKey="completed" fill="#10b981" name="Completed" stackId="a" />
              <Bar dataKey="overdue" fill="#ef4444" name="Overdue" stackId="a" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function IncidentsTab() {
  const [data, setData] = useState<{
    summary: {
      total: number; high_critical: number; avg_downtime_hours: number;
      total_cost_usd: number; lessons_learned_count: number; ptw_conflict_checks: number;
      reported_count: number; legacy_count: number;
    };
    by_severity: Record<string, number>;
    by_equipment: { equipment_id: string; count: number }[];
    by_root_cause: Record<string, number>;
    monthly_trend: { month: string; count: number }[];
    recent_incidents: {
      id: string; incident_number?: string; equipment_id: string;
      title: string; severity: string; date: string;
      status?: string; incident_type?: string;
    }[];
  } | null>(null);
  useEffect(() => { getReportIncidents().then(d => setData(d as typeof data)).catch(() => {}); }, []);
  if (!data) return <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-amber-400" /></div>;

  const sevData = Object.entries(data.by_severity || {}).map(([name, value]) => ({ name, value, fill: SEV_COLOR[name] ?? "#6b7280" }));
  const eqData  = (data.by_equipment || []).slice(0, 8).map(e => ({ name: e.equipment_id, incidents: e.count }));
  const rcData  = Object.entries(data.by_root_cause || {})
    .filter(([k]) => k !== "Unknown")
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));
  const recent  = data.recent_incidents || [];

  const STATUS_COLOR: Record<string, string> = {
    reported: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    investigation: "bg-blue-500/10 text-blue-400 border-blue-500/20",
    root_cause_analysis: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    capa: "bg-sky-500/10 text-sky-400 border-sky-500/20",
    closed: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <KpiCard label="Total Incidents" value={data.summary.total} color="text-red-400" icon={AlertTriangle} />
        <KpiCard label="High + Critical" value={data.summary.high_critical} color={data.summary.high_critical > 0 ? "text-red-400" : "text-emerald-400"} icon={AlertTriangle} />
        <KpiCard label="Avg Downtime" value={`${data.summary.avg_downtime_hours}h`} color="text-orange-400" icon={Wrench} />
        <KpiCard label="Reported (Workflow)" value={data.summary.reported_count ?? 0} color="text-purple-400" icon={AlertTriangle} sub="via incident reports" />
        <KpiCard label="Total Cost (USD)" value={data.summary.total_cost_usd > 0 ? `$${data.summary.total_cost_usd.toLocaleString()}` : "—"} color="text-amber-400" icon={BarChart3} />
        <KpiCard label="Lessons Learned" value={data.summary.lessons_learned_count} color="text-sky-400" icon={BarChart3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {sevData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="By Severity" icon={AlertTriangle} />
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={sevData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine>
                  {sevData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
        {(data.monthly_trend || []).length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="Monthly Trend" icon={TrendingUp} />
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.monthly_trend} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                <XAxis dataKey="month" tick={{ fill: "#6b7280", fontSize: 9 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
                <Line type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2} dot={{ fill: "#f59e0b", r: 3 }} name="Incidents" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {rcData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="By Root Cause Category" icon={GitBranch} />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={rcData} layout="vertical" margin={{ top: 0, right: 8, left: 60, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 9 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} width={56} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="value" fill="#f97316" name="Incidents" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {eqData.length > 0 && (
          <div className={clsx("bg-[#141414] border border-[#252525] rounded-xl p-5", rcData.length === 0 ? "lg:col-span-2" : "")}>
            <SectionHeader title="Top Equipment by Incident Count" icon={Cog} />
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={eqData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="incidents" fill="#ef4444" name="Incidents" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Recent Incidents — live from IncidentReport table only (no demo seed data) */}
      <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-[#1e1e1e] flex items-center gap-2">
          <p className="text-xs font-semibold text-[#6b7280] flex-1">Recent Incident Reports</p>
          <span className="text-[10px] text-[#4b5563]">live · user-reported only</span>
        </div>
        {recent.length === 0 ? (
          <div className="px-4 py-6 text-xs text-[#4b5563] italic text-center">
            No incident reports submitted yet. Use the Incidents workflow or Forms → Incident Report to log one.
          </div>
        ) : (
          recent.map(inc => (
            <div key={inc.id} className="px-4 py-2.5 border-b border-[#0f0f0f] flex items-center gap-2 hover:bg-[#161616] transition-colors">
              <span className="text-[10px] font-mono text-amber-400/80 flex-shrink-0 w-24 truncate">
                {inc.incident_number || inc.id.slice(0, 12)}
              </span>
              <span className="text-[10px] font-mono text-[#4b5563] flex-shrink-0 w-14">{inc.equipment_id || "—"}</span>
              <span className="text-xs text-[#a0a0a0] truncate flex-1">{inc.title}</span>
              <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border flex-shrink-0",
                inc.severity === "Critical" ? "bg-red-500/10 text-red-400 border-red-500/20"
                : inc.severity === "High" ? "bg-orange-500/10 text-orange-400 border-orange-500/20"
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              )}>{inc.severity}</span>
              {inc.status && (
                <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border flex-shrink-0",
                  STATUS_COLOR[inc.status] ?? "bg-[#252525] text-[#6b7280] border-[#2a2a2a]"
                )}>{inc.status.replace("_", " ")}</span>
              )}
              <span className="text-[10px] text-[#4b5563] flex-shrink-0">{inc.date || "—"}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function WorkOrdersTab() {
  const [data, setData] = useState<{
    summary: { total: number; open: number; completed: number; solution_rate: number; avg_duration_h: number; created_last_30d: number };
    by_status: Record<string, number>;
    by_type: Record<string, number>;
    by_equipment: { equipment_id: string; count: number }[];
    recent: { id: string; equipment_id: string; type: string; status: string; risk_level: string; description: string; created_at: string }[];
  } | null>(null);
  useEffect(() => { getReportWorkOrders().then(d => setData(d as typeof data)).catch(() => {}); }, []);
  if (!data) return <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-amber-400" /></div>;

  const statusData = Object.entries(data.by_status || {}).map(([name, value]) => ({ name, value }));
  const typeData = Object.entries(data.by_type || {}).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <KpiCard label="Total WOs" value={data.summary.total} icon={ClipboardCheck} />
        <KpiCard label="Open" value={data.summary.open} color={data.summary.open > 0 ? "text-orange-400" : "text-emerald-400"} icon={ClipboardCheck} />
        <KpiCard label="Solution Rate" value={`${data.summary.solution_rate}%`} color={data.summary.solution_rate >= 70 ? "text-emerald-400" : "text-amber-400"} icon={TrendingUp} />
        <KpiCard label="Avg Duration" value={`${data.summary.avg_duration_h}h`} icon={Wrench} />
        <KpiCard label="Completed" value={data.summary.completed} color="text-emerald-400" icon={ClipboardCheck} />
        <KpiCard label="Created (30d)" value={data.summary.created_last_30d} color="text-sky-400" icon={BarChart3} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {statusData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="By Status" icon={ClipboardCheck} />
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={statusData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine>
                  {statusData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
        {typeData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="By Type" icon={Wrench} />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={typeData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {typeData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      {(data.recent || []).length > 0 && (
        <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#1e1e1e]"><p className="text-xs font-semibold text-[#6b7280]">Recent Work Orders</p></div>
          {(data.recent || []).map(wo => (
            <div key={wo.id} className="px-4 py-2 border-b border-[#0f0f0f] flex items-center gap-3 hover:bg-[#161616] transition-colors">
              <span className="text-[10px] font-mono text-purple-400 flex-shrink-0">{wo.id}</span>
              <span className="text-[10px] font-mono text-amber-400/70 flex-shrink-0">{wo.equipment_id}</span>
              <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border flex-shrink-0",
                wo.status === "completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                : wo.status === "in_progress" ? "bg-sky-500/10 text-sky-400 border-sky-500/20"
                : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              )}>{wo.status}</span>
              <span className="text-xs text-[#a0a0a0] truncate flex-1">{wo.description}</span>
              <span className="text-[10px] text-[#4b5563] flex-shrink-0">{wo.created_at?.slice(0, 10)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SafetyTab() {
  const [data, setData] = useState<{
    summary: { avg_compliance_pct: number | null; equipment_below_90_pct: number; equipment_below_75_pct: number; total_ptw_checks: number; ptw_active: number; ptw_blocked: number; ptw_conditional: number; active_procedures: number; procedures_in_review: number };
    compliance_by_equipment: { id: string; name: string; compliance_score: number | null; status: string }[];
    ptw_by_clearance: Record<string, number>;
    procedures_by_status: Record<string, number>;
    ptw_by_equipment: { equipment_id: string; count: number }[];
    recent_ptw_checks: { id: string; equipment_id: string; date: string; title: string; action: string; permit_type?: string; status?: string }[];
  } | null>(null);
  useEffect(() => { getReportSafety().then(d => setData(d as typeof data)).catch(() => {}); }, []);
  if (!data) return <div className="flex justify-center py-10"><Loader2 size={16} className="animate-spin text-amber-400" /></div>;

  const ptwData = Object.entries(data.ptw_by_clearance).map(([name, value]) => ({
    name, value,
    fill: name === "BLOCKED" ? "#ef4444" : name === "CONDITIONAL" ? "#f97316" : "#10b981",
  }));
  const procData = Object.entries(data.procedures_by_status || {}).map(([name, value]) => ({ name, value }));
  const ptwByEqData = (data.ptw_by_equipment || []).slice(0, 8).map(e => ({ name: e.equipment_id, count: e.count }));

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <KpiCard label="Avg Compliance" value={data.summary.avg_compliance_pct != null ? `${data.summary.avg_compliance_pct}%` : "—"} color={(data.summary.avg_compliance_pct ?? 100) >= 90 ? "text-emerald-400" : "text-orange-400"} icon={Shield} />
        <KpiCard label="Below 90%" value={data.summary.equipment_below_90_pct} color={data.summary.equipment_below_90_pct > 0 ? "text-orange-400" : "text-emerald-400"} icon={AlertTriangle} />
        <KpiCard label="Below 75% (Critical)" value={data.summary.equipment_below_75_pct} color={data.summary.equipment_below_75_pct > 0 ? "text-red-400" : "text-emerald-400"} icon={AlertTriangle} />
        <KpiCard label="PTW Total" value={data.summary.total_ptw_checks} icon={Shield} />
        <KpiCard label="PTW Active / Clear" value={data.summary.ptw_active ?? 0} color={(data.summary.ptw_active ?? 0) > 0 ? "text-emerald-400" : "text-[#4b5563]"} icon={Shield} />
        <KpiCard label="PTW Blocked" value={data.summary.ptw_blocked} color={data.summary.ptw_blocked > 0 ? "text-red-400" : "text-emerald-400"} icon={Shield} />
        <KpiCard label="Active Procedures" value={data.summary.active_procedures ?? 0} color="text-sky-400" icon={BarChart3} />
        <KpiCard label="Procedures in Review" value={data.summary.procedures_in_review ?? 0} color="text-amber-400" icon={BarChart3} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {ptwData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="PTW Clearance Distribution" icon={Shield} />
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={ptwData} cx="50%" cy="50%" outerRadius={70} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine>
                  {ptwData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", color: "#ffffff", borderRadius: 8, fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
        {procData.length > 0 && (
          <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
            <SectionHeader title="Safety Procedures by Status" icon={BarChart3} />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={procData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
                <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 8 }} />
                <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {procData.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className={`bg-[#141414] border border-[#252525] rounded-xl p-5${procData.length === 0 ? " lg:col-span-2" : ""}`}>
          <SectionHeader title="Compliance by Equipment" icon={Cog} />
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {data.compliance_by_equipment.map(eq => (
              <div key={eq.id} className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-amber-400/80 w-16 flex-shrink-0">{eq.id}</span>
                <div className="flex-1 h-1.5 bg-[#252525] rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{
                    width: `${eq.compliance_score ?? 0}%`,
                    background: (eq.compliance_score ?? 0) >= 90 ? "#10b981" : (eq.compliance_score ?? 0) >= 75 ? "#f59e0b" : "#ef4444",
                  }} />
                </div>
                <span className="text-[10px] font-mono w-10 text-right" style={{
                  color: (eq.compliance_score ?? 0) >= 90 ? "#10b981" : (eq.compliance_score ?? 0) >= 75 ? "#f59e0b" : "#ef4444",
                }}>{eq.compliance_score ?? "—"}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* PTW by equipment — live from PermitToWork table */}
      {ptwByEqData.length > 0 && (
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-5">
          <SectionHeader title="Permits to Work by Equipment" icon={Shield} />
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={ptwByEqData} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
              <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 9 }} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
              <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }} />
              <Bar dataKey="count" fill="#f59e0b" name="PTW Count" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {(data.recent_ptw_checks || []).length > 0 && (
        <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#1e1e1e]"><p className="text-xs font-semibold text-[#6b7280]">Recent Permits to Work</p></div>
          {(data.recent_ptw_checks || []).map(p => (
            <div key={p.id} className="px-4 py-2 border-b border-[#0f0f0f] hover:bg-[#161616] transition-colors">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-orange-400/80">{p.equipment_id || p.id.slice(0, 10)}</span>
                <span className="text-[10px] text-[#4b5563]">{p.date}</span>
                {p.status && <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border",
                  p.status === "active" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : p.status === "cancelled" ? "bg-red-500/10 text-red-400 border-red-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                )}>{p.status}</span>}
                <span className="text-xs text-[#a0a0a0] truncate flex-1">{p.title}</span>
              </div>
              <p className="text-[10px] text-[#4b5563] mt-0.5 truncate">{p.action}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const TABS = [
  { key: "overview",     label: "Overview",     icon: BarChart3 },
  { key: "equipment",    label: "Equipment",    icon: Cog },
  { key: "maintenance",  label: "Maintenance",  icon: Wrench },
  { key: "incidents",    label: "Incidents",    icon: AlertTriangle },
  { key: "work-orders",  label: "Work Orders",  icon: ClipboardCheck },
  { key: "safety",       label: "Safety",       icon: Shield },
] as const;

type TabKey = typeof TABS[number]["key"];

export default function ReportsPage() {
  const [tab, setTab] = useState<TabKey>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);

  useEffect(() => {
    getReportOverview().then(d => setOverview(d as Overview)).catch(() => {}).finally(() => setOverviewLoading(false));
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center gap-3 px-5 py-3 border-b border-[#1e1e1e] bg-[#0a0a0a]">
        <BarChart3 size={18} className="text-amber-400" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-[#f9f9f9]">Reports & Analytics</p>
          <p className="text-[10px] text-[#4b5563] mt-0.5">Plant KPIs · Equipment health · Maintenance · Incidents · Safety</p>
        </div>
        <button onClick={() => { setOverviewLoading(true); getReportOverview().then(d => setOverview(d as Overview)).finally(() => setOverviewLoading(false)); }}
          className="flex items-center gap-1 text-xs text-[#4b5563] hover:text-amber-400 transition-colors">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
      {/* Tabs */}
      <div className="flex-shrink-0 flex border-b border-[#1e1e1e] bg-[#0a0a0a] px-5 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={clsx("flex items-center gap-1.5 px-3 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap",
              tab === t.key ? "border-amber-500 text-amber-400" : "border-transparent text-[#4b5563] hover:text-[#a0a0a0]")}>
            <t.icon size={11} /> {t.label}
          </button>
        ))}
      </div>
      {/* Body */}
      <div className="flex-1 min-h-0 overflow-y-auto p-5">
        {tab === "overview" && (overviewLoading ? <div className="flex justify-center py-16"><Loader2 size={20} className="animate-spin text-amber-400" /></div> : overview ? <OverviewTab data={overview} /> : <p className="text-xs text-red-400">Failed to load</p>)}
        {tab === "equipment"   && <EquipmentTab />}
        {tab === "maintenance" && <MaintenanceTab />}
        {tab === "incidents"   && <IncidentsTab />}
        {tab === "work-orders" && <WorkOrdersTab />}
        {tab === "safety"      && <SafetyTab />}
      </div>
    </div>
  );
}
