/**
 * AI Operations Brain — Audit Log & Relation Map
 * Append-only audit trail.
 *
 * Left panel  : filter controls + stats
 * Right panel : time-sorted audit entries OR relation map for one equipment
 *
 * Tabs: Activity Log | Relation Map | Export
 */
"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  getAuditLog, getRelationMap, listEquipment,
} from "@/lib/api";
import { format, parseISO } from "date-fns";
import {
  History, Filter, Download, Loader2, AlertTriangle,
  ChevronDown, ChevronRight, GitBranch, ClipboardList,
  Wrench, FileText, Activity, Cog, RefreshCw, type LucideIcon,
} from "lucide-react";
import clsx from "clsx";
import type { Equipment } from "@/lib/types";
import { usePageState } from "@/lib/page-state";

// ── Types ─────────────────────────────────────────────────────────────────────

type AuditEntry = {
  id: number; timestamp: string;
  object_type: string; object_id: string; equipment_id: string | null;
  action: string; actor: string; actor_type: string;
  changes: Record<string, unknown> | null; risk_level: string | null;
  notes: string | null; icon: string;
};

type RelationMap = {
  equipment_id: string; equipment_name: string; equipment_type: string;
  location: string; health_score: number | null; status: string;
  relations: {
    incidents: unknown[]; maintenance: unknown[]; work_orders: unknown[];
    checklists: unknown[]; documents: unknown[];
    lessons_learned: unknown[];
  };
  timeline: { date: string | null; type: string; id: string; title: string; severity: string | null; description: string | null }[];
  audit_trail: AuditEntry[];
  summary: Record<string, number>;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const OBJ_COLOR: Record<string, string> = {
  work_order: "text-purple-400", checklist: "text-blue-400",
  incident: "text-red-400", defect: "text-orange-400",
  equipment: "text-amber-400", sensor: "text-sky-400",
  document: "text-slate-400",
  feedback: "text-yellow-400", lesson: "text-teal-400",
};

const ACTION_BADGE: Record<string, string> = {
  create:   "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  complete: "bg-sky-500/10 text-sky-400 border-sky-500/20",
  update:   "bg-amber-500/10 text-amber-400 border-amber-500/20",
  purge:    "bg-red-500/10 text-red-400 border-red-500/20",
};

const RELATION_ICON: Record<string, LucideIcon> = {
  incidents: AlertTriangle, maintenance: Wrench, work_orders: ClipboardList,
  checklists: ClipboardList, documents: FileText,
  lessons_learned: GitBranch,
};

const TIMELINE_COLOR: Record<string, string> = {
  incident: "border-red-500 bg-red-500/10",
  maintenance: "border-emerald-500 bg-emerald-500/10",
  work_order: "border-purple-500 bg-purple-500/10",
  checklist: "border-sky-500 bg-sky-500/10",
};

const SEV_COLOR: Record<string, string> = {
  Critical: "text-red-400", High: "text-orange-400",
  Medium: "text-amber-400", Low: "text-emerald-400",
  Overdue: "text-red-400", Completed: "text-emerald-400", Scheduled: "text-sky-400",
};

// ── Audit entry row ───────────────────────────────────────────────────────────

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const hasDetails = !!entry.changes || !!entry.notes;
  return (
    <div className="border-b border-[#1a1a1a] last:border-0">
      <button
        onClick={() => hasDetails && setOpen(o => !o)}
        className={clsx(
          "w-full flex items-start gap-3 px-4 py-2.5 hover:bg-[#141414] transition-colors text-left",
          !hasDetails && "cursor-default"
        )}
      >
        <span className="text-base flex-shrink-0 mt-0.5">{entry.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={clsx("text-xs font-semibold", OBJ_COLOR[entry.object_type] ?? "text-[#a0a0a0]")}>
              {entry.object_type.replace("_", " ")}
            </span>
            <span className="text-[10px] font-mono text-[#6b7280] truncate max-w-[120px]">{entry.object_id}</span>
            <span className={clsx("text-[9px] px-1.5 py-0.5 rounded border font-semibold", ACTION_BADGE[entry.action] ?? "bg-[#1e1e1e] text-[#6b7280] border-[#252525]")}>
              {entry.action}
            </span>
            {entry.risk_level && (
              <span className={clsx("text-[10px] font-semibold", SEV_COLOR[entry.risk_level] ?? "text-[#6b7280]")}>
                {entry.risk_level}
              </span>
            )}
            {entry.equipment_id && (
              <span className="text-[10px] text-amber-400/70 font-mono">{entry.equipment_id}</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[10px] text-[#4b5563]">
              {format(parseISO(entry.timestamp), "MMM d, yyyy HH:mm:ss")} UTC
            </span>
            <span className="text-[10px] text-[#333]">·</span>
            <span className="text-[10px] text-[#4b5563]">{entry.actor} ({entry.actor_type})</span>
            {entry.notes && <p className="text-[10px] text-[#6b7280] truncate">{entry.notes}</p>}
          </div>
        </div>
        {hasDetails && (open ? <ChevronDown size={12} className="text-[#4b5563] mt-1 flex-shrink-0" /> : <ChevronRight size={12} className="text-[#4b5563] mt-1 flex-shrink-0" />)}
      </button>
      {open && (entry.changes || entry.notes) && (
        <div className="px-12 pb-3">
          {entry.notes && <p className="text-xs text-[#a0a0a0] mb-1">{entry.notes}</p>}
          {entry.changes && (
            <pre className="text-[10px] text-[#6b7280] bg-[#0f0f0f] rounded-lg px-3 py-2 overflow-x-auto">
              {JSON.stringify(entry.changes, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Relation map view ─────────────────────────────────────────────────────────

function RelationMapView({ equipmentId }: { equipmentId: string }) {
  const [data, setData] = useState<RelationMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getRelationMap(equipmentId)
      .then(d => setData(d as RelationMap))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [equipmentId]);

  if (loading) return <div className="flex items-center gap-2 py-10 justify-center text-[#4b5563]"><Loader2 size={16} className="animate-spin text-amber-400" /> Loading relation map…</div>;
  if (!data) return <p className="text-xs text-red-400 py-4">Failed to load relation map.</p>;

  const rel = data.relations ?? {};
  const sections = [
    { key: "incidents",       label: "Incidents",       count: (rel.incidents       ?? []).length },
    { key: "maintenance",     label: "Maintenance",     count: (rel.maintenance     ?? []).length },
    { key: "work_orders",     label: "Work Orders",     count: (rel.work_orders     ?? []).length },
    { key: "checklists",      label: "Checklists",      count: (rel.checklists      ?? []).length },
    { key: "documents",       label: "Documents",       count: (rel.documents       ?? []).length },
    { key: "lessons_learned", label: "Lessons Learned", count: (rel.lessons_learned ?? []).length },
  ];

  return (
    <div className="space-y-5">
      {/* Equipment header */}
      <div className="bg-[#141414] border border-[#252525] rounded-xl p-4 flex items-start gap-4">
        <Cog size={28} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-bold text-[#f9f9f9]">{data.equipment_id} — {data.equipment_name}</p>
          <p className="text-xs text-[#6b7280]">{data.equipment_type} · {data.location}</p>
          <p className="text-xs text-[#4b5563] mt-0.5">Status: {data.status} · Health: {data.health_score ?? "—"}%</p>
        </div>
        <div className="grid grid-cols-4 gap-3 text-center">
          {Object.entries(data.summary).map(([k, v]) => (
            <div key={k} className="bg-[#0f0f0f] rounded-lg px-3 py-1.5">
              <p className="text-base font-bold text-amber-400">{v}</p>
              <p className="text-[9px] text-[#4b5563] capitalize">{k.replace(/_/g, " ")}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Relation summary boxes */}
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Object Relations</p>
          <div className="space-y-1">
            {sections.map(sec => {
              const Icon = RELATION_ICON[sec.key] ?? Activity;
              return (
                <button
                  key={sec.key}
                  onClick={() => setActiveSection(activeSection === sec.key ? null : sec.key)}
                  className={clsx(
                    "w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-left",
                    activeSection === sec.key ? "bg-amber-500/10 border border-amber-500/20" : "hover:bg-[#1a1a1a]"
                  )}
                >
                  <Icon size={13} className={activeSection === sec.key ? "text-amber-400" : "text-[#4b5563]"} />
                  <span className="flex-1 text-xs text-[#a0a0a0]">{sec.label}</span>
                  <span className={clsx("text-xs font-mono font-bold", sec.count > 0 ? "text-amber-400" : "text-[#333]")}>{sec.count}</span>
                  <ChevronRight size={10} className={clsx("text-[#333]", activeSection === sec.key && "rotate-90")} />
                </button>
              );
            })}
          </div>
          {activeSection && (
            <div className="mt-3 max-h-40 overflow-y-auto space-y-1">
              {((data.relations as Record<string, unknown[]>)[activeSection] || []).map((item: unknown, i: number) => {
                const obj = item as Record<string, unknown>;
                return (
                  <div key={i} className="text-[10px] text-[#6b7280] bg-[#0f0f0f] rounded px-2 py-1.5">
                    <span className="font-mono text-amber-400/70">{String(obj["id"] ?? "")}</span>
                    {!!obj["title"] && <span className="ml-1">{String(obj["title"]).slice(0, 60)}</span>}
                    {!!obj["date"] && <span className="ml-1 text-[#333]">· {String(obj["date"])}</span>}
                    {!!obj["severity"] && <span className={clsx("ml-1 font-semibold", SEV_COLOR[String(obj["severity"])] ?? "text-[#6b7280]")}>{String(obj["severity"])}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Timeline */}
        <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Full History Timeline ({data.timeline.length} events)</p>
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {data.timeline.length === 0 && <p className="text-xs text-[#333] italic">No timeline events.</p>}
            {data.timeline.map((ev, i) => (
              <div key={i} className={clsx("flex gap-2 pl-2 border-l-2", TIMELINE_COLOR[ev.type] ?? "border-[#252525]")}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[9px] text-[#4b5563]">{ev.date?.slice(0, 10) ?? "—"}</span>
                    <span className={clsx("text-[9px] font-semibold px-1 rounded capitalize", TIMELINE_COLOR[ev.type] ?? "")}>{ev.type.replace("_", " ")}</span>
                    <span className="text-[10px] font-mono text-[#4b5563]">{ev.id?.slice(0, 12)}</span>
                  </div>
                  <p className="text-xs text-[#a0a0a0] truncate">{ev.title}</p>
                  {ev.description && <p className="text-[10px] text-[#4b5563] truncate">{ev.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Audit trail for this equipment */}
      {data.audit_trail.length > 0 && (
        <div className="bg-[#141414] border border-[#252525] rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-[#1e1e1e]">
            <p className="text-xs font-semibold text-[#6b7280]">Audit Trail ({data.audit_trail.length} events)</p>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {data.audit_trail.map(e => <AuditRow key={e.id} entry={e} />)}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function AuditPageInner() {
  const searchParams = useSearchParams();
  const { audit: auditState, updateAudit } = usePageState();

  // URL params seed on first visit; subsequent visits restore from store
  const [tab, _setTab] = useState<"log" | "relations">(
    searchParams.get("tab") === "relations" ? "relations" : auditState.tab
  );
  const setTab = (t: "log" | "relations") => { _setTab(t); updateAudit({ tab: t }); };
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);

  // Filters
  const [objType, _setObjType] = useState(auditState.objType);
  const setObjType = (s: string) => { _setObjType(s); updateAudit({ objType: s }); };
  const [eqFilter, _setEqFilter] = useState(searchParams.get("equipment") || auditState.eqFilter);
  const setEqFilter = (s: string) => { _setEqFilter(s); updateAudit({ eqFilter: s }); };
  const [actionFilter, _setActionFilter] = useState(auditState.actionFilter);
  const setActionFilter = (s: string) => { _setActionFilter(s); updateAudit({ actionFilter: s }); };
  const [days, _setDays] = useState(auditState.days);
  const setDays = (n: number) => { _setDays(n); updateAudit({ days: n }); };
  const [relEq, _setRelEq] = useState(searchParams.get("equipment") || auditState.relEq);
  const setRelEq = (s: string) => { _setRelEq(s); updateAudit({ relEq: s }); };

  useEffect(() => {
    listEquipment().then(list => setEquipmentList(list.filter(e => !e._discovered))).catch(() => {});
  }, []);

  const loadLog = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getAuditLog({
        object_type: objType || undefined,
        equipment_id: eqFilter || undefined,
        action: actionFilter || undefined,
        days, limit: 100,
      }) as { total: number; entries: AuditEntry[] };
      setEntries(res.entries);
      setTotal(res.total);
    } catch { setEntries([]); } finally { setLoading(false); }
  }, [objType, eqFilter, actionFilter, days]);

  useEffect(() => { if (tab === "log") loadLog(); }, [tab, loadLog]);

  const handleExport = () => {
    const params: Record<string, string> = { days: String(days) };
    if (objType) params.object_type = objType;
    if (eqFilter) params.equipment_id = eqFilter;
    if (actionFilter) params.action = actionFilter;
    const qs = new URLSearchParams(params);
    window.open(`/api/v1/audit/export/csv?${qs}`, "_blank");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center gap-3 px-5 py-3 border-b border-[#1e1e1e] bg-[#0a0a0a]">
        <History size={18} className="text-amber-400" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-[#f9f9f9]">Audit Log & Relation Map</p>
          <p className="text-[10px] text-[#4b5563] mt-0.5">
            Append-only trail · {entries.length !== total ? `showing ${entries.length} of ${total} entries` : `${total} entries`}
          </p>
        </div>
        <div className="flex gap-1.5">
          {(["log", "relations"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx("text-xs px-3 py-1.5 rounded-lg transition-colors capitalize",
                tab === t ? "bg-amber-500/15 text-amber-400 border border-amber-500/25"
                           : "text-[#4b5563] hover:text-[#a0a0a0]")}>
              {t === "log" ? "Activity Log" : "Relation Map"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        {/* Left: filters */}
        <div className="w-52 flex-shrink-0 border-r border-[#1e1e1e] p-3 space-y-3 overflow-y-auto">
          {tab === "log" ? (
            <>
              <div>
                <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Object Type</label>
                <select value={objType} onChange={e => setObjType(e.target.value)} aria-label="Object Type"
                  className="w-full bg-[#141414] border border-[#252525] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] appearance-none focus:outline-none">
                  <option value="">All types</option>
                  {["work_order","checklist","sensor","system"].map(t => (
                    <option key={t} value={t}>{t.replace("_"," ")}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Equipment</label>
                <select value={eqFilter} onChange={e => setEqFilter(e.target.value)} aria-label="Equipment"
                  className="w-full bg-[#141414] border border-[#252525] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] appearance-none focus:outline-none">
                  <option value="">All equipment</option>
                  {equipmentList.map(eq => <option key={eq.id} value={eq.id}>{eq.id}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Action</label>
                <select value={actionFilter} onChange={e => setActionFilter(e.target.value)} aria-label="Action"
                  className="w-full bg-[#141414] border border-[#252525] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] appearance-none focus:outline-none">
                  <option value="">All actions</option>
                  {["create","update","complete","purge"].map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block mb-1">Last {days} days</label>
                <input type="range" min={1} max={90} value={days} onChange={e => setDays(+e.target.value)}
                  aria-label="Time range in days"
                  className="w-full accent-amber-500" />
                <p className="text-[10px] text-[#4b5563] text-center">{days}d</p>
              </div>
              <button onClick={loadLog} className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 transition-colors">
                <RefreshCw size={11} /> Apply Filters
              </button>
              <button onClick={handleExport} className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#141414] border border-[#252525] text-[#6b7280] text-xs hover:text-[#a0a0a0] transition-colors">
                <Download size={11} /> Export CSV
              </button>
            </>
          ) : (
            <>
              <label className="text-[10px] text-[#4b5563] uppercase tracking-wider block">Select Equipment</label>
              <div className="space-y-1">
                {equipmentList.map(eq => (
                  <button key={eq.id} onClick={() => setRelEq(eq.id)}
                    className={clsx("w-full text-left px-2.5 py-2 rounded-lg text-xs transition-colors",
                      relEq === eq.id ? "bg-amber-500/10 border border-amber-500/20 text-amber-400" : "text-[#a0a0a0] hover:bg-[#141414]")}>
                    <p className="font-mono">{eq.id}</p>
                    <p className="text-[10px] text-[#4b5563] truncate">{eq.name}</p>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right: content */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          {tab === "log" ? (
            loading ? (
              <div className="flex items-center gap-2 justify-center py-16 text-[#4b5563]">
                <Loader2 size={16} className="animate-spin text-amber-400" /> Loading…
              </div>
            ) : entries.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-3">
                <History size={36} className="text-[#1e1e1e]" />
                <p className="text-sm text-[#4b5563]">No audit entries match the current filters.</p>
                <p className="text-xs text-[#2e2e2e]">Create a work order or checklist to generate entries.</p>
              </div>
            ) : (
              <div>
                <div className="px-4 py-2 border-b border-[#1a1a1a] flex items-center gap-2">
                  <Filter size={11} className="text-[#4b5563]" />
                  <p className="text-[10px] text-[#4b5563]">{entries.length} of {total} entries · newest first</p>
                </div>
                {entries.map(e => <AuditRow key={e.id} entry={e} />)}
              </div>
            )
          ) : (
            <div className="p-5">
              {relEq ? (
                <RelationMapView equipmentId={relEq} />
              ) : (
                <div className="flex flex-col items-center justify-center py-20 gap-3">
                  <GitBranch size={36} className="text-[#1e1e1e]" />
                  <p className="text-sm text-[#4b5563]">Select an equipment to view its full relation map.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AuditPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-full gap-2 text-[#4b5563]"><Loader2 size={16} className="animate-spin text-amber-400" /> Loading…</div>}>
      <AuditPageInner />
    </Suspense>
  );
}
