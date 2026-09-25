/**
 * AI Operations Brain — Sensors & Telemetry Dashboard
 *
 * Left panel  : equipment selector + sensor card grid
 *               (current value · status colour · trend arrow)
 * Right panel : selected sensor detail
 *               ├─ history chart (area + alarm/trip reference lines + anomaly shading)
 *               ├─ Stats row     (current · average of the last readings · max and min of stored history)
 *               └─ Tabbed panel (Maintenance · Incidents)
 */
"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getEquipmentSensorDashboard, listEquipment } from "@/lib/api";
import { usePageState } from "@/lib/page-state";
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceArea, ResponsiveContainer, Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import {
  Activity, TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2,
  Loader2, ChevronDown, Wrench, Zap, BarChart3,
} from "lucide-react";
import clsx from "clsx";
import type { Equipment } from "@/lib/types";
import { isAlarmStatus, statusColor } from "@/lib/sensorDisplay";
import { accentClass, accentStyle } from "@/lib/accentStyle";

// ── Types ─────────────────────────────────────────────────────────────────────

type HistoryPt = { ts: string; value: number };
type AnomalyPeriod = { start: string; end: string; level: "alarm" | "trip" };

type SensorDetail = {
  key: string; label: string;
  current: number; unit: string;
  normal: number | null; alarm: number | null; trip: number | null;
  status: string;
  trend: string; trend_pct: number;
  history: HistoryPt[];
  anomaly_periods: AnomalyPeriod[];
  stats: { current?: number; max?: number; min?: number; avg_recent?: number; recent_count?: number; data_points?: number };
};

type MaintenanceRecord = {
  id: string; date: string | null; type: string; status: string;
  description: string; technician: string | null; findings: string | null;
};

type Incident = {
  id: string; date: string | null; title: string; severity: string;
  symptom: string | null; root_cause: string | null;
};

type SensorDashboard = {
  equipment_id: string; equipment_name: string; equipment_type: string;
  location: string; health_score: number | null;
  sensors: Record<string, SensorDetail>;
  maintenance_records: MaintenanceRecord[];
  incidents: Incident[];
};

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  normal: "Normal", high: "High", low: "Low", alarm: "Alarm", trip: "TRIP", no_reading: "No reading",
};
const STATUS_BG: Record<string, string> = {
  normal: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  high:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
  low:    "bg-sky-500/10 text-sky-400 border-sky-500/20",
  alarm:  "bg-orange-500/10 text-orange-400 border-orange-500/20",
  trip:   "bg-red-500/10 text-red-400 border-red-500/20",
  no_reading: "bg-[#6b7280]/10 text-[#9ca3af] border-[#6b7280]/20",
};

const SEV_COLOR: Record<string, string> = {
  Critical: "text-red-400", High: "text-orange-400",
  Medium: "text-amber-400", Low: "text-emerald-400",
};

// ── Trend icon ────────────────────────────────────────────────────────────────

function TrendIcon({ trend, pct }: { trend: string; pct: number }) {
  if (trend === "rising")  return <TrendingUp  size={12} className="text-orange-400" />;
  if (trend === "falling") return <TrendingDown size={12} className="text-emerald-400" />;
  return <Minus size={12} className="text-[#4b5563]" />;
}

// ── Sensor card (left panel) ──────────────────────────────────────────────────

function SensorCard({ s, active, onClick }: { s: SensorDetail; active: boolean; onClick: () => void }) {
  const dot_color = statusColor(s.status);
  return (
    <button
      onClick={onClick}
      className={clsx(
        "w-full text-left px-3 py-2.5 rounded-xl border transition-all",
        active
          ? "bg-amber-500/10 border-amber-500/30"
          : "bg-[#0f0f0f] border-[#1e1e1e] hover:border-[#2a2a2a]"
      )}
    >
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: dot_color }} />
        <p className="text-xs font-medium text-[#e0e0e0] flex-1 truncate">{s.label}</p>
        <TrendIcon trend={s.trend} pct={s.trend_pct} />
      </div>
      <div className="flex items-baseline gap-1 mt-0.5 pl-4">
        <span className={`text-base font-bold font-mono ${accentClass}`} style={accentStyle(dot_color)}>
          {s.current}
        </span>
        <span className="text-[10px] text-[#4b5563]">{s.unit}</span>
        <span className={clsx("ml-auto text-[9px] px-1.5 py-0.5 rounded border font-semibold", STATUS_BG[s.status] ?? STATUS_BG.normal)}>
          {STATUS_LABEL[s.status] ?? s.status}
        </span>
      </div>
      {/* Mini progress bar */}
      {s.alarm && (
        <div className="pl-4 mt-1.5">
          <div className="relative h-0.5 bg-[#252525] rounded-full overflow-visible">
            {(() => {
              const max = s.trip ?? s.alarm * 1.4;
              const pct = Math.min(100, (s.current / max) * 100);
              const apct = (s.alarm / max) * 100;
              return (
                <>
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: dot_color }} />
                  <div className="absolute top-0 h-2 w-px bg-orange-500/50 -translate-y-1/2" style={{ left: `${apct}%` }} />
                </>
              );
            })()}
          </div>
        </div>
      )}
    </button>
  );
}

// ── History chart ─────────────────────────────────────────────────────────────

function SensorHistoryChart({ sensor }: { sensor: SensorDetail }) {
  if (sensor.history.length === 0) {
    return (
      <p className="h-[220px] flex items-center justify-center text-xs text-[#6b7280]">
        No stored history for this sensor. Only the current reading is known.
      </p>
    );
  }
  // Downsample for performance: show every 3rd point for dense datasets
  const raw = sensor.history;
  const data = raw.length > 120
    ? raw.filter((_, i) => i % 2 === 0 || i === raw.length - 1)
    : raw;

  const formatted = data.map(p => ({
    ts: p.ts,
    label: format(parseISO(p.ts), "MMM d"),
    value: p.value,
  }));

  const yMin = Math.floor(Math.min(...data.map(p => p.value)) * 0.9);
  const yMax = Math.ceil((sensor.trip ?? (sensor.alarm ? sensor.alarm * 1.3 : sensor.current * 1.3)) * 1.05);

  const lineColor = statusColor(sensor.status);

  return (
    <div className="w-full h-[220px]">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={formatted} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${sensor.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={lineColor} stopOpacity={0.25} />
              <stop offset="95%" stopColor={lineColor} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e1e" />
          <XAxis
            dataKey="label" tick={{ fill: "#4b5563", fontSize: 9 }}
            interval={Math.floor(formatted.length / 6)}
            tickLine={false} axisLine={false}
          />
          <YAxis
            domain={[yMin, yMax]}
            tick={{ fill: "#4b5563", fontSize: 9 }}
            tickLine={false} axisLine={false}
            unit={` ${sensor.unit}`}
            width={52}
          />
          <Tooltip
            contentStyle={{ background: "#141414", border: "1px solid #252525", borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: "#a0a0a0" }}
            itemStyle={{ color: lineColor }}
            formatter={(v: number) => [`${v} ${sensor.unit}`, sensor.label]}
          />

          {/* Anomaly shading — alarm band */}
          {sensor.anomaly_periods.map((ap, i) => (
            <ReferenceArea
              key={i}
              x1={format(parseISO(ap.start), "MMM d")}
              x2={format(parseISO(ap.end), "MMM d")}
              fill={ap.level === "trip" ? "#ef444418" : "#f9731618"}
              stroke="none"
            />
          ))}

          {/* Normal band fill */}
          {sensor.normal && sensor.alarm && (
            <ReferenceArea y1={yMin} y2={sensor.normal} fill="#10b98108" stroke="none" />
          )}

          {/* Reference lines */}
          {sensor.normal && (
            <ReferenceLine y={sensor.normal} stroke="#10b981" strokeDasharray="4 3" strokeWidth={1}
              label={{ value: `Normal ${sensor.normal}`, fill: "#10b981", fontSize: 9, position: "insideTopRight" }} />
          )}
          {sensor.alarm && (
            <ReferenceLine y={sensor.alarm} stroke="#f97316" strokeDasharray="4 3" strokeWidth={1}
              label={{ value: `Alarm ${sensor.alarm}`, fill: "#f97316", fontSize: 9, position: "insideTopRight" }} />
          )}
          {sensor.trip && (
            <ReferenceLine y={sensor.trip} stroke="#ef4444" strokeDasharray="2 2" strokeWidth={1}
              label={{ value: `Trip ${sensor.trip}`, fill: "#ef4444", fontSize: 9, position: "insideTopRight" }} />
          )}

          <Area
            type="monotone" dataKey="value"
            stroke={lineColor} strokeWidth={1.5}
            fill={`url(#grad-${sensor.key})`}
            dot={false}
            activeDot={{ r: 4, fill: lineColor, stroke: "#141414", strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Stat card ─────────────────────────────────────────────────────────────────

function StatCard({ label, value, unit, highlight }: { label: string; value: number | string; unit?: string; highlight?: string }) {
  return (
    <div className="bg-[#0f0f0f] border border-[#1e1e1e] rounded-xl px-4 py-3">
      <p className="text-[10px] text-[#4b5563] mb-0.5">{label}</p>
      <p className={clsx("text-lg font-bold font-mono", highlight ?? "text-[#f9f9f9]")}>
        {value}<span className="text-[10px] text-[#4b5563] ml-0.5">{unit}</span>
      </p>
    </div>
  );
}

// ── Tab: Maintenance ──────────────────────────────────────────────────────────

function MaintenanceTab({ records }: { records: MaintenanceRecord[] }) {
  if (!records.length) return <p className="text-xs text-[#4b5563] italic py-4">No maintenance records.</p>;
  return (
    <div className="space-y-2">
      {records.map(r => (
        <div key={r.id} className="flex items-start gap-3 p-3 bg-[#0f0f0f] border border-[#1e1e1e] rounded-xl">
          <div className={clsx(
            "mt-0.5 w-2 h-2 rounded-full flex-shrink-0",
            r.status === "Overdue" ? "bg-red-400" : r.status === "Completed" ? "bg-emerald-400" : "bg-amber-400"
          )} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-[10px] font-mono text-amber-400/80">{r.id}</span>
              <span className="text-[10px] text-[#4b5563]">{r.date || "—"}</span>
              <span className={clsx(
                "text-[9px] px-1.5 py-0.5 rounded border",
                r.status === "Overdue" ? "bg-red-500/10 text-red-400 border-red-500/20"
                  : r.status === "Completed" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-400 border-amber-500/20"
              )}>{r.status}</span>
            </div>
            <p className="text-xs text-[#e0e0e0] truncate">{r.description}</p>
            {r.findings && r.findings !== "Not performed" && (
              <p className="text-[10px] text-[#6b7280] mt-0.5 truncate">{r.findings}</p>
            )}
            {r.technician && (
              <p className="text-[10px] text-[#4b5563] mt-0.5">By: {r.technician}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Tab: Incidents ────────────────────────────────────────────────────────────

function IncidentsTab({ incidents }: { incidents: Incident[] }) {
  if (!incidents.length) return <p className="text-xs text-[#4b5563] italic py-4">No incidents recorded.</p>;
  return (
    <div className="space-y-2">
      {incidents.map(inc => (
        <div key={inc.id} className="p-3 bg-[#0f0f0f] border border-[#1e1e1e] rounded-xl">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono text-amber-400/80">{inc.id}</span>
            <span className="text-[10px] text-[#4b5563]">{inc.date || "—"}</span>
            <span className={clsx("text-[10px] font-semibold", SEV_COLOR[inc.severity] ?? "text-[#6b7280]")}>
              {inc.severity}
            </span>
          </div>
          <p className="text-xs font-medium text-[#e0e0e0]">{inc.title}</p>
          {inc.symptom && <p className="text-[10px] text-[#6b7280] mt-0.5 line-clamp-2">{inc.symptom}</p>}
          {inc.root_cause && (
            <p className="text-[10px] text-sky-400/80 mt-1 flex items-start gap-1">
              <span className="flex-shrink-0 mt-0.5">→</span> {inc.root_cause}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Sensor detail panel (right) ───────────────────────────────────────────────

function SensorDetailPanel({ dashboard, sensorKey }: { dashboard: SensorDashboard; sensorKey: string }) {
  const [tab, setTab] = useState<"maintenance" | "incidents">("maintenance");
  const sensor = dashboard.sensors[sensorKey];
  if (!sensor) return null;

  const alarmCount = sensor.anomaly_periods.length;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-bold text-[#f9f9f9]">{sensor.label}</h2>
          <p className="text-xs text-[#4b5563] mt-0.5">
            {dashboard.equipment_id} · {dashboard.equipment_name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {alarmCount > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400">
              {alarmCount} alarm period{alarmCount !== 1 ? "s" : ""} in stored history
            </span>
          )}
          <span className={clsx("text-xs px-2.5 py-1 rounded-full border font-semibold", STATUS_BG[sensor.status] ?? STATUS_BG.normal)}>
            {STATUS_LABEL[sensor.status] ?? sensor.status}
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-[#0a0a0a] border border-[#1e1e1e] rounded-2xl p-4">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 size={13} className="text-amber-400" />
          <span className="text-xs font-semibold text-[#a0a0a0]">Stored History</span>
          <span className="text-[10px] text-[#333] ml-auto">{sensor.stats?.data_points ?? "—"} data points</span>
        </div>
        <SensorHistoryChart sensor={sensor} />
        {/* Trend annotation */}
        {sensor.trend !== "stable" && (
          <p className={`text-[10px] mt-2 flex items-center gap-1 ${accentClass}`} style={accentStyle(sensor.trend === "rising" ? "#f97316" : "#10b981")}>
            {sensor.trend === "rising" ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
            {Math.abs(sensor.trend_pct)}% {sensor.trend}: the last {sensor.stats?.recent_count} readings against the ones before
          </p>
        )}
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Current" value={sensor.current} unit={sensor.unit}
          highlight={isAlarmStatus(sensor.status) ? statusColor(sensor.status) : undefined} />
        <StatCard label={sensor.stats?.recent_count ? `Avg of Last ${sensor.stats.recent_count}` : "Recent Avg"}
          value={sensor.stats?.avg_recent ?? "—"} unit={sensor.unit} />
        <StatCard label="History Max" value={sensor.stats?.max ?? "—"} unit={sensor.unit} />
        <StatCard label="History Min" value={sensor.stats?.min ?? "—"} unit={sensor.unit} />
      </div>

      {/* Tabs */}
      <div className="bg-[#0a0a0a] border border-[#1e1e1e] rounded-2xl overflow-hidden">
        <div className="flex border-b border-[#1e1e1e]">
          {([
            { key: "maintenance", label: "Maintenance", icon: Wrench, count: dashboard.maintenance_records.length },
            { key: "incidents",   label: "Incidents",   icon: AlertTriangle, count: dashboard.incidents.length },
          ] as const).map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                "flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors border-b-2",
                tab === t.key
                  ? "border-amber-500 text-amber-400 bg-amber-500/5"
                  : "border-transparent text-[#4b5563] hover:text-[#a0a0a0]"
              )}
            >
              <t.icon size={11} />
              {t.label}
              {t.count > 0 && (
                <span className={clsx(
                  "text-[9px] px-1 rounded-full",
                  tab === t.key ? "bg-amber-500/20 text-amber-400" : "bg-[#1e1e1e] text-[#4b5563]"
                )}>{t.count}</span>
              )}
            </button>
          ))}
        </div>
        <div className="p-4 max-h-72 overflow-y-auto">
          {tab === "maintenance" && <MaintenanceTab records={dashboard.maintenance_records} />}
          {tab === "incidents"   && <IncidentsTab   incidents={dashboard.incidents} />}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function SensorsPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const presetEq = searchParams.get("equipment") ?? "";
  const presetKey = searchParams.get("sensor") ?? "";

  const { sensors: sensorsState, updateSensors } = usePageState();

  // Persist equipment selection; URL preset takes priority on initial mount
  const [equipmentId, _setEquipmentId] = useState(presetEq || sensorsState.equipmentId);
  const setEquipmentId = (id: string) => { _setEquipmentId(id); updateSensors({ equipmentId: id }); };

  // selectedKey stays transient — auto-selects based on alarm state after dashboard loads
  const [selectedKey, setSelectedKey] = useState(presetKey);

  // Transient state (always reset on mount — not persisted)
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [dashboard, setDashboard] = useState<SensorDashboard | null>(null);
  const [loading, setLoading] = useState(false);

  // Load equipment list
  useEffect(() => {
    listEquipment()
      .then(list => {
        const active = list.filter(e => !e.discovered && (e.current_readings && Object.keys(e.current_readings).length > 0));
        setEquipmentList(active);
        if (!equipmentId && active.length > 0) setEquipmentId(active[0].id);
      })
      .catch(() => {});
  }, []);

  // Load sensor dashboard whenever equipment changes
  useEffect(() => {
    if (!equipmentId) return;
    setLoading(true);
    setDashboard(null);
    setSelectedKey("");
    getEquipmentSensorDashboard(equipmentId)
      .then(d => {
        const dash = d as SensorDashboard;
        setDashboard(dash);
        // Auto-select first sensor in alarm, or just first
        const keys = Object.keys(dash.sensors);
        const alarmKey = keys.find(k => dash.sensors[k].status === "alarm" || dash.sensors[k].status === "trip");
        setSelectedKey(presetKey && dash.sensors[presetKey] ? presetKey : (alarmKey ?? keys[0] ?? ""));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [equipmentId]);

  const sensorEntries = dashboard ? Object.values(dashboard.sensors) : [];
  const alarmCount = sensorEntries.filter(s => s.status === "alarm" || s.status === "trip").length;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 flex items-center gap-3 px-5 py-3 border-b border-[#1e1e1e] bg-[#0a0a0a]">
        <Activity size={18} className="text-amber-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] leading-none">Sensors & Telemetry</p>
          <p className="text-[10px] text-[#4b5563] mt-0.5">
            {dashboard
              ? `${sensorEntries.length} sensors · ${alarmCount} in alarm`
              : "stored history · anomaly detection · maintenance correlation"}
          </p>
        </div>
        {/* Equipment selector */}
        <div className="relative flex-shrink-0">
          <select
            value={equipmentId}
            onChange={e => setEquipmentId(e.target.value)}
            aria-label="Equipment"
            className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-3 pr-8 py-1.5 text-xs text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50"
          >
            {equipmentList.length === 0
              ? <option value="">{equipmentId || "Loading…"}</option>
              : equipmentList.map(eq => (
                  <option key={eq.id} value={eq.id}>{eq.id} — {eq.name}</option>
                ))
            }
          </select>
          <ChevronDown size={11} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
        </div>
      </div>

      {/* ── Body ───────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center flex-1 gap-2 text-[#4b5563]">
          <Loader2 size={16} className="animate-spin text-amber-400" />
          <span className="text-sm">Loading sensor data…</span>
        </div>
      ) : !dashboard ? (
        <div className="flex items-center justify-center flex-1 gap-2 text-[#4b5563]">
          <Activity size={36} className="text-[#1e1e1e]" />
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex gap-0">
          {/* Left: sensor list */}
          <div className="w-56 flex-shrink-0 border-r border-[#1e1e1e] overflow-y-auto p-3 space-y-1.5">
            {sensorEntries
              .sort((a, b) => {
                const rank: Record<string, number> = { trip: 0, alarm: 1, high: 2, low: 3, normal: 4 };
                return (rank[a.status] ?? 5) - (rank[b.status] ?? 5);
              })
              .map(s => (
                <SensorCard key={s.key} s={s} active={s.key === selectedKey} onClick={() => setSelectedKey(s.key)} />
              ))}
          </div>

          {/* Right: detail */}
          <div className="flex-1 min-w-0 overflow-y-auto p-5">
            {selectedKey && dashboard.sensors[selectedKey] ? (
              <SensorDetailPanel dashboard={dashboard} sensorKey={selectedKey} />
            ) : (
              <div className="flex items-center justify-center h-full text-[#333] text-sm">
                Select a sensor to view its history.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function SensorsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full gap-2 text-[#4b5563]">
        <Loader2 size={16} className="animate-spin text-amber-400" /> Loading…
      </div>
    }>
      <SensorsPageInner />
    </Suspense>
  );
}
