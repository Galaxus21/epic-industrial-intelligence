/**
 * AI Operations Brain — Custom Dashboard Builder
 * Build, save, and view widget-based dashboards.
 *
 * Mode A (view): renders saved dashboards with live data per widget
 * Mode B (build): widget catalogue → add/configure → save
 */
"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listDashboards, getDashboard, getWidgetCatalogue, createDashboard,
  updateDashboard, deleteDashboard,
  getReportOverview, getReportMaintenance, getReportWorkOrders, getReportSafety, getReportIncidents,
  listAllSensors, getEquipmentSensorDashboard, getEquipment, listWorkOrders, listEquipment,
  getAuditLog,
} from "@/lib/api";
import {
  LayoutDashboard, Plus, Trash2, Save, Settings2, X, Loader2,
  CheckCircle2, AlertTriangle, Wrench, ClipboardCheck, Shield, Zap,
  Activity, Cog, Factory, BarChart3, Bell, Clock, type LucideIcon,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import clsx from "clsx";
import type { Equipment } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type WidgetConfig = { equipment_id?: string; sensor_key?: string; [k: string]: unknown };

type Widget = {
  id: string; type: string; title: string; col_span: 1 | 2;
  config: WidgetConfig;
};

type Dashboard = {
  id: string; name: string; description: string | null;
  widgets: Widget[]; columns: number;
  created_at: string | null; updated_at: string | null;
};

type CatalogueEntry = {
  type: string; label: string; description: string; icon: string;
  col_span: 1 | 2;
  config_fields: { id: string; label: string; type: string; required?: boolean }[];
};

// ── Widget icon map ────────────────────────────────────────────────────────────

const W_ICON: Record<string, LucideIcon> = {
  plant_health: Factory, equipment_health: Cog, sensor_chart: Activity,
  sensor_grid: Activity, work_order_kpi: ClipboardCheck, incident_kpi: AlertTriangle,
  maintenance_kpi: Wrench, safety_kpi: Shield, incident_list: AlertTriangle,
  work_order_list: ClipboardCheck, alert_feed: Bell, audit_feed: Clock,
};

// ── Live widget renderers ─────────────────────────────────────────────────────

function WidgetShell({ title, children, onRemove }: { title: string; children: React.ReactNode; onRemove?: () => void }) {
  return (
    <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden flex flex-col">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#1e1e1e] flex-shrink-0">
        <span className="flex-1 text-xs font-semibold text-[#a0a0a0]">{title}</span>
        {onRemove && (
          <button onClick={onRemove} className="text-[#333] hover:text-red-400 transition-colors">
            <X size={11} />
          </button>
        )}
      </div>
      <div className="p-4 flex-1 min-h-0">{children}</div>
    </div>
  );
}

function KVLine({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[10px] text-[#4b5563]">{label}</span>
      <span className={clsx("text-xs font-mono font-semibold", color ?? "text-[#f9f9f9]")}>{value}</span>
    </div>
  );
}

function PlantHealthWidget() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { getReportOverview().then(r => setD(r as Record<string, unknown>)).catch(() => {}); }, []);
  if (!d) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const wo = d.work_orders as Record<string, number>;
  return (
    <div className="space-y-1.5">
      <KVLine label="Plant Health" value={d.plant_health != null ? `${d.plant_health}%` : "—"} color={(d.plant_health as number) >= 75 ? "text-emerald-400" : "text-orange-400"} />
      <KVLine label="Equipment in Alarm" value={d.equipment_in_alarm as number} color={(d.equipment_in_alarm as number) > 0 ? "text-red-400" : "text-emerald-400"} />
      <KVLine label="Overdue Maintenance" value={d.overdue_maintenance as number} color={(d.overdue_maintenance as number) > 0 ? "text-orange-400" : "text-emerald-400"} />
      <KVLine label="Open Work Orders" value={wo?.open ?? "—"} color="text-purple-400" />
      <KVLine label="WO Completion Rate" value={wo ? `${wo.completion_rate}%` : "—"} color="text-sky-400" />
    </div>
  );
}

function EquipmentHealthWidget({ config }: { config: WidgetConfig }) {
  const [eq, setEq] = useState<Equipment | null>(null);
  useEffect(() => { if (config.equipment_id) getEquipment(config.equipment_id).then(r => setEq(r as Equipment)).catch(() => {}); }, [config.equipment_id]);
  if (!eq) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const hs = eq.health_score ?? null;
  const color = hs == null ? "#6b7280" : hs >= 85 ? "#10b981" : hs >= 65 ? "#f59e0b" : "#ef4444";
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <svg width={44} height={44}>
          <circle cx={22} cy={22} r={19} fill="none" stroke="#252525" strokeWidth={4} />
          {hs != null && <circle cx={22} cy={22} r={19} fill="none" stroke={color} strokeWidth={4}
            strokeDasharray={`${(hs / 100) * 2 * Math.PI * 19} ${2 * Math.PI * 19}`}
            strokeLinecap="round" transform="rotate(-90 22 22)" />}
          <text x={22} y={26} textAnchor="middle" fill={color} fontSize="10" fontWeight="700">{hs ?? "—"}</text>
        </svg>
        <div>
          <p className="text-xs font-semibold text-[#f9f9f9]">{eq.name}</p>
          <p className="text-[10px] text-[#4b5563]">{eq.type}</p>
          <p className="text-[10px]" style={{ color }}>{eq.status}</p>
        </div>
      </div>
      <KVLine label="Fail Probability" value={eq.failure_probability != null ? `${eq.failure_probability}%` : "—"} color={(eq.failure_probability ?? 0) > 20 ? "text-orange-400" : "text-emerald-400"} />
      <KVLine label="Compliance" value={eq.compliance_score != null ? `${eq.compliance_score}%` : "—"} color={(eq.compliance_score ?? 100) < 90 ? "text-orange-400" : "text-emerald-400"} />
    </div>
  );
}

function SensorChartWidget({ config }: { config: WidgetConfig }) {
  const [sensor, setSensor] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    if (config.equipment_id && config.sensor_key)
      getEquipmentSensorDashboard(config.equipment_id as string)
        .then(d => { const dash = d as Record<string, Record<string, unknown>>; const s = dash.sensors?.[config.sensor_key as string]; setSensor(s ? (s as Record<string, unknown>) : null); })
        .catch(() => {});
  }, [config.equipment_id, config.sensor_key]);

  if (!sensor) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const history = (sensor.history as { ts: string; value: number }[]) || [];
  const downsampled = history.filter((_, i) => i % 3 === 0 || i === history.length - 1).slice(-40);
  const color = sensor.status_color as string ?? "#f59e0b";

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold" style={{ color }}>{sensor.current as number} {sensor.unit as string}</span>
        <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border font-semibold",
          sensor.status === "alarm" ? "bg-orange-500/10 text-orange-400 border-orange-500/20"
          : sensor.status === "normal" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
        )}>{sensor.status as string}</span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={downsampled} margin={{ top: 2, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
          <XAxis dataKey="ts" tick={{ fill: "#4b5563", fontSize: 8 }} tickFormatter={ts => { try { return format(parseISO(ts), "MMM d"); } catch { return ts; } }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: "#4b5563", fontSize: 8 }} />
          <Tooltip contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 6, fontSize: 10 }} />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={1.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function SensorGridWidget({ config }: { config: WidgetConfig }) {
  const [sensors, setSensors] = useState<Record<string, unknown>[] | null>(null);
  useEffect(() => {
    if (!config.equipment_id) return;
    getEquipmentSensorDashboard(config.equipment_id as string)
      .then(d => { const dash = d as Record<string, Record<string, unknown>>; setSensors(Object.values(dash.sensors ?? {}) as Record<string, unknown>[] as Record<string, unknown>[]); })
      .catch(() => {});
  }, [config.equipment_id]);
  if (!sensors) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  return (
    <div className="grid grid-cols-2 gap-2">
      {sensors.map((s, i) => (
        <div key={i} className="bg-[#0f0f0f] rounded-lg px-2.5 py-2">
          <p className="text-[10px] text-[#4b5563] truncate">{s.label as string}</p>
          <p className="text-sm font-mono font-bold" style={{ color: s.status_color as string }}>
            {s.current as number}<span className="text-[9px] text-[#333] ml-0.5">{s.unit as string}</span>
          </p>
        </div>
      ))}
    </div>
  );
}

function WorkOrderKpiWidget() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { getReportWorkOrders().then(r => setD(r as Record<string, unknown>)).catch(() => {}); }, []);
  if (!d) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const s = d.summary as Record<string, number>;
  return (
    <div className="space-y-1.5">
      <KVLine label="Open WOs" value={s.open} color={s.open > 0 ? "text-orange-400" : "text-emerald-400"} />
      <KVLine label="Completed" value={s.completed} color="text-emerald-400" />
      <KVLine label="Solution Rate" value={`${s.solution_rate}%`} color={s.solution_rate >= 70 ? "text-emerald-400" : "text-amber-400"} />
      <KVLine label="Avg Duration" value={`${s.avg_duration_h}h`} />
    </div>
  );
}

function IncidentKpiWidget() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { getReportIncidents().then(r => setD(r as Record<string, unknown>)).catch(() => {}); }, []);
  if (!d) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const s = d.summary as Record<string, number>;
  return (
    <div className="space-y-1.5">
      <KVLine label="Total Incidents" value={s.total} color="text-red-400" />
      <KVLine label="High + Critical" value={s.high_critical} color={s.high_critical > 0 ? "text-red-400" : "text-emerald-400"} />
      <KVLine label="Avg Downtime" value={`${s.avg_downtime_hours}h`} color="text-orange-400" />
      <KVLine label="Lessons Learned" value={s.lessons_learned_count} color="text-sky-400" />
    </div>
  );
}

function MaintenanceKpiWidget() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { getReportMaintenance().then(r => setD(r as Record<string, unknown>)).catch(() => {}); }, []);
  if (!d) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const k = d.kpis as Record<string, number>;
  return (
    <div className="space-y-1.5">
      <KVLine label="Total Records" value={k.total_records} />
      <KVLine label="Compliance Rate" value={`${k.compliance_rate_pct}%`} color={k.compliance_rate_pct >= 80 ? "text-emerald-400" : "text-orange-400"} />
      <KVLine label="Overdue" value={k.overdue} color={k.overdue > 0 ? "text-red-400" : "text-emerald-400"} />
    </div>
  );
}

function SafetyKpiWidget() {
  const [d, setD] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { getReportSafety().then(r => setD(r as Record<string, unknown>)).catch(() => {}); }, []);
  if (!d) return <Loader2 size={14} className="animate-spin text-amber-400" />;
  const s = d.summary as Record<string, number | null>;
  return (
    <div className="space-y-1.5">
      <KVLine label="Avg Compliance" value={s.avg_compliance_pct != null ? `${s.avg_compliance_pct}%` : "—"} color={(s.avg_compliance_pct as number ?? 100) >= 90 ? "text-emerald-400" : "text-orange-400"} />
      <KVLine label="Below 90%" value={s.equipment_below_90_pct as number} color={(s.equipment_below_90_pct as number) > 0 ? "text-orange-400" : "text-emerald-400"} />
      <KVLine label="PTW Blocked" value={s.ptw_blocked as number} color={(s.ptw_blocked as number) > 0 ? "text-red-400" : "text-emerald-400"} />
    </div>
  );
}

function AlertFeedWidget() {
  const [alarms, setAlarms] = useState<{ equipment_id: string; label: string; value: number; unit: string; alarm: number; excess_pct: number }[]>([]);
  useEffect(() => {
    listAllSensors().then(data => {
      const all: typeof alarms = [];
      (data as { equipment_id: string; sensors: { label: string; value: number; unit: string; status: string; alarm: number | null }[] }[]).forEach(eq => {
        eq.sensors.filter(s => s.status === "alarm" || s.status === "trip").forEach(s => {
          all.push({ equipment_id: eq.equipment_id, label: s.label, value: s.value, unit: s.unit, alarm: s.alarm ?? 0, excess_pct: s.alarm ? Math.round((s.value - s.alarm) / s.alarm * 100) : 0 });
        });
      });
      setAlarms(all);
    }).catch(() => {});
  }, []);
  if (alarms.length === 0) return <p className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> No active sensor alarms.</p>;
  return (
    <div className="space-y-1.5">
      {alarms.slice(0, 6).map((a, i) => (
        <div key={i} className="flex items-center gap-2 bg-orange-500/5 border border-orange-500/15 rounded-lg px-3 py-1.5">
          <span className="text-[10px] font-mono text-amber-400/80 flex-shrink-0">{a.equipment_id}</span>
          <span className="text-[10px] text-[#6b7280] flex-1 truncate">{a.label}</span>
          <span className="text-xs font-mono font-bold text-orange-400">{a.value}{a.unit}</span>
          <span className="text-[9px] text-red-400">+{a.excess_pct}%</span>
        </div>
      ))}
    </div>
  );
}

function WorkOrderListWidget() {
  const [wos, setWos] = useState<{ id: string; equipment_id: string; wo_type: string; status: string; description: string }[]>([]);
  useEffect(() => {
    listWorkOrders().then((data: unknown) => {
      const all = data as typeof wos;
      setWos(all.filter(w => w.status !== "completed").slice(0, 6));
    }).catch(() => {});
  }, []);
  if (wos.length === 0) return <p className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 size={12} /> No open work orders.</p>;
  return (
    <div className="space-y-1.5">
      {wos.map(wo => (
        <div key={wo.id} className="flex items-start gap-2 bg-[#0f0f0f] rounded-lg px-2.5 py-1.5">
          <span className="text-[10px] font-mono text-purple-400 flex-shrink-0">{wo.id.slice(0, 10)}</span>
          <span className="text-[10px] font-mono text-amber-400/70 flex-shrink-0">{wo.equipment_id}</span>
          <span className="text-[10px] text-[#a0a0a0] truncate">{wo.description}</span>
        </div>
      ))}
    </div>
  );
}

function IncidentListWidget() {
  const [items, setItems] = useState<{ id: string; equipment_id: string; title: string; severity: string; date: string }[]>([]);
  useEffect(() => {
    getReportIncidents().then((d: unknown) => {
      const rpt = d as { recent_incidents?: typeof items };
      setItems((rpt.recent_incidents || []).slice(0, 5));
    }).catch(() => {});
  }, []);
  if (items.length === 0) return <p className="text-xs text-[#4b5563] italic">No recent incidents.</p>;
  return (
    <div className="space-y-1.5">
      {items.map(inc => (
        <div key={inc.id} className="flex items-center gap-2 text-[10px]">
          <span className="font-mono text-amber-400/80">{inc.equipment_id}</span>
          <span className="text-[#4b5563]">{inc.date?.slice(0, 10)}</span>
          <span className="text-[#a0a0a0] truncate flex-1">{inc.title}</span>
          <span className={inc.severity === "Critical" || inc.severity === "High" ? "text-red-400 font-semibold" : "text-amber-400"}>{inc.severity}</span>
        </div>
      ))}
    </div>
  );
}

function AuditFeedWidget() {
  const [entries, setEntries] = useState<{ id: number; timestamp: string; object_type: string; object_id: string; action: string; actor: string; icon: string }[]>([]);
  useEffect(() => {
    getAuditLog({ days: 7, limit: 8 }).then((d: unknown) => {
      const res = d as { entries: typeof entries };
      setEntries(res.entries || []);
    }).catch(() => {});
  }, []);
  if (entries.length === 0) return <p className="text-xs text-[#4b5563] italic">No recent audit events.</p>;
  return (
    <div className="space-y-1 max-h-40 overflow-y-auto">
      {entries.map(e => (
        <div key={e.id} className="flex items-center gap-2 text-[10px]">
          <span>{e.icon}</span>
          <span className="text-[#4b5563] flex-shrink-0">{format(parseISO(e.timestamp), "MMM d HH:mm")}</span>
          <span className="text-[#6b7280] truncate flex-1">{e.object_type} · {e.object_id.slice(0, 12)}</span>
          <span className="text-amber-400/80 flex-shrink-0">{e.action}</span>
        </div>
      ))}
    </div>
  );
}

function LiveWidget({ widget, onRemove }: { widget: Widget; onRemove?: () => void }) {
  const content = (() => {
    switch (widget.type) {
      case "plant_health":     return <PlantHealthWidget />;
      case "equipment_health": return <EquipmentHealthWidget config={widget.config} />;
      case "sensor_chart":     return <SensorChartWidget config={widget.config} />;
      case "sensor_grid":      return <SensorGridWidget config={widget.config} />;
      case "work_order_kpi":   return <WorkOrderKpiWidget />;
      case "incident_kpi":     return <IncidentKpiWidget />;
      case "maintenance_kpi":  return <MaintenanceKpiWidget />;
      case "safety_kpi":       return <SafetyKpiWidget />;
      case "alert_feed":       return <AlertFeedWidget />;
      case "work_order_list":  return <WorkOrderListWidget />;
      case "incident_list":    return <IncidentListWidget />;
      case "audit_feed":       return <AuditFeedWidget />;
      default:                 return <p className="text-xs text-[#4b5563]">Unknown widget type: {widget.type}</p>;
    }
  })();
  return <WidgetShell title={widget.title} onRemove={onRemove}>{content}</WidgetShell>;
}

// ── Dashboard viewer ──────────────────────────────────────────────────────────

function DashboardViewer({ dash, onEdit }: { dash: Dashboard; onEdit: () => void }) {
  const cols = dash.columns ?? 2;
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <div className="flex-1">
          <p className="text-base font-bold text-[#f9f9f9]">{dash.name}</p>
          {dash.description && <p className="text-xs text-[#4b5563]">{dash.description}</p>}
        </div>
        <button onClick={onEdit} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-[#6b7280] hover:text-amber-400 border border-[#252525] hover:border-amber-500/30 transition-colors">
          <Settings2 size={11} /> Edit
        </button>
      </div>
      <div className={clsx("grid gap-4", cols === 1 ? "grid-cols-1" : cols === 3 ? "grid-cols-1 md:grid-cols-3" : "grid-cols-1 md:grid-cols-2")}>
        {(dash.widgets || []).map(w => (
          <div key={w.id} className={w.col_span === 2 ? "md:col-span-2" : ""}>
            <LiveWidget widget={w} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Dashboard builder ─────────────────────────────────────────────────────────

function DashboardBuilder({
  dash, catalogue, equipmentList,
  onSave, onCancel,
}: {
  dash: Dashboard | null; catalogue: CatalogueEntry[]; equipmentList: Equipment[];
  onSave: (updated: Partial<Dashboard>) => void; onCancel: () => void;
}) {
  const [name, setName] = useState(dash?.name ?? "New Dashboard");
  const [description, setDescription] = useState(dash?.description ?? "");
  const [columns, setColumns] = useState<number>(dash?.columns ?? 2);
  const [widgets, setWidgets] = useState<Widget[]>(dash?.widgets ?? []);
  const [configuring, setConfiguring] = useState<{ entry: CatalogueEntry; draft: WidgetConfig; title: string } | null>(null);
  const [sensorKeys, setSensorKeys] = useState<string[]>([]);

  const startAdd = (entry: CatalogueEntry) => {
    setConfiguring({ entry, draft: {}, title: entry.label });
  };

  // When equipment changes in config form, load sensor keys
  useEffect(() => {
    const eqId = configuring?.draft.equipment_id as string | undefined;
    if (!eqId) { setSensorKeys([]); return; }
    getEquipmentSensorDashboard(eqId)
      .then((d: unknown) => { const dash = d as Record<string, Record<string, unknown>>; setSensorKeys(Object.keys(dash.sensors ?? {})); })
      .catch(() => setSensorKeys([]));
  }, [configuring?.draft.equipment_id]);

  const confirmAdd = () => {
    if (!configuring) return;
    const w: Widget = {
      id: `w-${Date.now()}`, type: configuring.entry.type, title: configuring.title,
      col_span: configuring.entry.col_span, config: configuring.draft,
    };
    setWidgets(prev => [...prev, w]);
    setConfiguring(null);
  };

  const removeWidget = (id: string) => setWidgets(prev => prev.filter(w => w.id !== id));

  return (
    <div className="space-y-5">
      {/* Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Dashboard Name</label>
          <input value={name} onChange={e => setName(e.target.value)} className="w-full bg-[#141414] border border-[#252525] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/50" />
        </div>
        <div className="md:col-span-2">
          <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Description</label>
          <input value={description} onChange={e => setDescription(e.target.value)} className="w-full bg-[#141414] border border-[#252525] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/50" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-xs text-[#6b7280]">Columns:</span>
        {[1, 2, 3].map(c => (
          <button key={c} onClick={() => setColumns(c)} className={clsx("w-8 h-8 rounded-lg text-xs font-semibold border transition-colors",
            columns === c ? "bg-amber-500/15 border-amber-500/30 text-amber-400" : "border-[#252525] text-[#4b5563] hover:text-[#a0a0a0]")}>
            {c}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Widget catalogue */}
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Widget Catalogue — Click to Add</p>
          <div className="grid grid-cols-2 gap-2">
            {catalogue.map(entry => {
              const Icon = W_ICON[entry.type] ?? BarChart3;
              return (
                <button key={entry.type} onClick={() => startAdd(entry)}
                  className="flex items-start gap-2 p-2.5 bg-[#0f0f0f] border border-[#1e1e1e] rounded-xl hover:border-amber-500/30 hover:bg-[#181818] transition-colors text-left">
                  <Icon size={13} className="text-amber-400 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-[#e0e0e0] truncate">{entry.label}</p>
                    <p className="text-[10px] text-[#4b5563] line-clamp-2">{entry.description}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Current widgets */}
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Current Widgets ({widgets.length})</p>
          {widgets.length === 0 ? (
            <p className="text-xs text-[#333] italic text-center py-8">Add widgets from the catalogue →</p>
          ) : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {widgets.map(w => {
                const Icon = W_ICON[w.type] ?? BarChart3;
                return (
                  <div key={w.id} className="flex items-center gap-2 bg-[#0f0f0f] rounded-lg px-3 py-2">
                    <Icon size={12} className="text-amber-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-[#e0e0e0] truncate">{w.title}</p>
                      {w.config.equipment_id && <p className="text-[10px] text-[#4b5563]">{w.config.equipment_id as string}{w.config.sensor_key ? ` / ${w.config.sensor_key as string}` : ""}</p>}
                    </div>
                    <span className="text-[9px] text-[#333] flex-shrink-0">{w.col_span}col</span>
                    <button onClick={() => removeWidget(w.id)} className="text-[#333] hover:text-red-400 transition-colors flex-shrink-0"><X size={11} /></button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Config modal */}
      {configuring && (
        <div className="bg-[#141414] border border-amber-500/30 rounded-2xl p-5">
          <p className="text-xs font-semibold text-amber-400 mb-3">Configure: {configuring.entry.label}</p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] text-[#4b5563] block mb-1">Widget Title</label>
              <input value={configuring.title} onChange={e => setConfiguring(c => c ? { ...c, title: e.target.value } : c)}
                className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/50" />
            </div>
            {configuring.entry.config_fields.map(field => (
              <div key={field.id}>
                <label className="text-[10px] text-[#4b5563] block mb-1">{field.label}{field.required === false ? " (optional)" : ""}</label>
                {field.type === "equipment_select" ? (
                  <select value={(configuring.draft[field.id] as string) ?? ""}
                    onChange={e => setConfiguring(c => c ? { ...c, draft: { ...c.draft, [field.id]: e.target.value } } : c)}
                    className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50">
                    <option value="">— select —</option>
                    {equipmentList.map(eq => <option key={eq.id} value={eq.id}>{eq.id} — {eq.name}</option>)}
                  </select>
                ) : field.type === "sensor_select" ? (
                  <select value={(configuring.draft[field.id] as string) ?? ""}
                    onChange={e => setConfiguring(c => c ? { ...c, draft: { ...c.draft, [field.id]: e.target.value } } : c)}
                    className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50">
                    <option value="">— select sensor —</option>
                    {sensorKeys.map(k => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
                  </select>
                ) : (
                  <input value={(configuring.draft[field.id] as string) ?? ""}
                    onChange={e => setConfiguring(c => c ? { ...c, draft: { ...c.draft, [field.id]: e.target.value } } : c)}
                    className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/50" />
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-4">
            <button onClick={confirmAdd} className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-500 text-black text-sm font-semibold hover:bg-amber-400 transition-colors">
              <Plus size={13} /> Add Widget
            </button>
            <button onClick={() => setConfiguring(null)} className="px-4 py-2 rounded-xl border border-[#252525] text-xs text-[#6b7280] hover:text-[#a0a0a0] transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button onClick={() => onSave({ name, description: description || null, widgets, columns })}
          className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-amber-500 text-black text-sm font-semibold hover:bg-amber-400 transition-colors">
          <Save size={13} /> Save Dashboard
        </button>
        <button onClick={onCancel} className="px-4 py-2 rounded-xl border border-[#252525] text-xs text-[#6b7280] hover:text-[#a0a0a0] transition-colors">Cancel</button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function DashboardsPage() {
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [catalogue, setCatalogue] = useState<CatalogueEntry[]>([]);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeDash, setActiveDash] = useState<Dashboard | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState("");
  const [backendStatus, setBackendStatus] = useState<{ neo4j_active: boolean; qdrant_active: boolean } | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const [dashes, cat, eqs] = await Promise.all([
        listDashboards() as Promise<Dashboard[]>,
        getWidgetCatalogue() as Promise<CatalogueEntry[]>,
        listEquipment(),
      ]);
      setDashboards(dashes);
      setCatalogue(cat);
      setEquipmentList(eqs.filter(e => !e._discovered));
      if (!activeDash && dashes.length > 0) setActiveDash(dashes[0]);
    } catch { } finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, []);

  // Fetch backend status (Neo4j + Qdrant)
  useEffect(() => {
    fetch("/api/v1/knowledge-graph/status")
      .then(r => r.ok ? r.json() : null)
      .then(d => setBackendStatus(d))
      .catch(() => {});
  }, []);

  const seedDemo = async () => {
    setSeeding(true); setSeedMsg("");
    try {
      const res = await fetch("/api/v1/admin/seed-demo", { method: "POST" });
      const data = await res.json();
      setSeedMsg(data.message || "Demo scenario loaded.");
      await reload();
    } catch {
      setSeedMsg("Failed to load demo scenario.");
    } finally {
      setSeeding(false);
    }
  };

  const handleSave = async (updates: Partial<Dashboard>) => {
    setSaving(true);
    try {
      if (activeDash && dashboards.find(d => d.id === activeDash.id)) {
        const updated = await updateDashboard(activeDash.id, updates) as Dashboard;
        setActiveDash(updated);
        setDashboards(prev => prev.map(d => d.id === updated.id ? updated : d));
      } else {
        const created = await createDashboard(updates) as Dashboard;
        setDashboards(prev => [...prev, created]);
        setActiveDash(created);
      }
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch { } finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this dashboard?")) return;
    await deleteDashboard(id);
    setDashboards(prev => prev.filter(d => d.id !== id));
    setActiveDash(prev => prev?.id === id ? (dashboards.find(d => d.id !== id) ?? null) : prev);
  };

  return (
    <div className="flex h-full">
      {/* Left: dashboard list */}
      <div className="w-52 flex-shrink-0 border-r border-[#1e1e1e] flex flex-col bg-[#0a0a0a]">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1e1e1e]">
          <LayoutDashboard size={14} className="text-amber-400" />
          <span className="text-xs font-semibold text-[#f9f9f9] flex-1">Dashboards</span>
        </div>
        {/* Backend status badges */}
        {backendStatus && (
          <div className="flex gap-1.5 px-3 py-2 border-b border-[#111]">
            <span className={clsx("flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border",
              backendStatus.neo4j_active ? "bg-purple-500/10 text-purple-400 border-purple-500/20" : "bg-[#1a1a1a] text-[#4b5563] border-[#252525]"
            )}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", backendStatus.neo4j_active ? "bg-purple-400" : "bg-[#4b5563]")} />
              Neo4j
            </span>
            <span className={clsx("flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded-full border",
              backendStatus.qdrant_active ? "bg-sky-500/10 text-sky-400 border-sky-500/20" : "bg-[#1a1a1a] text-[#4b5563] border-[#252525]"
            )}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", backendStatus.qdrant_active ? "bg-sky-400" : "bg-[#4b5563]")} />
              Qdrant
            </span>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {loading ? (
            <div className="flex justify-center py-4"><Loader2 size={14} className="animate-spin text-amber-400" /></div>
          ) : (
            dashboards.map(d => (
              <div key={d.id} className="group relative">
                <button onClick={() => { setActiveDash(d); setEditing(false); }}
                  className={clsx("w-full text-left px-3 py-2 rounded-lg text-xs transition-colors",
                    activeDash?.id === d.id ? "bg-amber-500/10 border border-amber-500/20 text-amber-400" : "text-[#a0a0a0] hover:bg-[#141414]")}>
                  <p className="font-medium truncate">{d.name}</p>
                  <p className="text-[10px] text-[#4b5563]">{(d.widgets || []).length} widgets</p>
                </button>
                <button onClick={() => handleDelete(d.id)}
                  className="absolute right-1.5 top-1.5 opacity-0 group-hover:opacity-100 text-[#333] hover:text-red-400 transition-all">
                  <Trash2 size={10} />
                </button>
              </div>
            ))
          )}
        </div>
        <div className="border-t border-[#1e1e1e] p-2">
          <button onClick={() => { setActiveDash(null); setEditing(true); }}
            className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 transition-colors">
            <Plus size={12} /> New Dashboard
          </button>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 min-w-0 overflow-y-auto p-5">
        {saved && (
          <div className="flex items-center gap-2 mb-4 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-xs text-emerald-400">
            <CheckCircle2 size={13} /> Dashboard saved successfully.
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20 gap-2 text-[#4b5563]">
            <Loader2 size={16} className="animate-spin text-amber-400" /> Loading dashboards…
          </div>
        ) : editing ? (
          <DashboardBuilder
            dash={activeDash} catalogue={catalogue} equipmentList={equipmentList}
            onSave={handleSave} onCancel={() => setEditing(false)}
          />
        ) : activeDash ? (
          <DashboardViewer dash={activeDash} onEdit={() => setEditing(true)} />
        ) : (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <LayoutDashboard size={40} className="text-[#1e1e1e]" />
            <p className="text-sm text-[#4b5563]">Select a dashboard or create a new one.</p>
            {/* Demo scenario loader */}
            <div className="flex flex-col items-center gap-2">
              <button
                onClick={seedDemo}
                disabled={seeding}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 transition-colors disabled:opacity-50"
              >
                {seeding ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
                {seeding ? "Loading demo…" : "Load Demo Scenario"}
              </button>
              {seedMsg && <p className="text-xs text-emerald-400 text-center max-w-xs">{seedMsg}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
