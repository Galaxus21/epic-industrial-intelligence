/**
 * AI Operations Brain — Maintenance Logs Page
 * Lists all maintenance records from every equipment with filter/search.
 * Shows a status pill per record.
 */
"use client";

import { useEffect, useState } from "react";
import {
  Wrench, RefreshCw, Filter, Search, CheckCircle2, Clock,
  AlertTriangle, XCircle, Cpu, ChevronRight, Zap,
} from "lucide-react";
import clsx from "clsx";
import { listMaintenanceRecords, type MaintenanceRecord } from "@/lib/api";
import { Pill } from "@/components/ui/Pill";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// ── Status styling ──────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, string> = {
  Completed:    "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  Pending:      "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Scheduled:    "text-amber-400 bg-amber-500/10 border-amber-500/30",
  "In Progress":"text-blue-400 bg-blue-500/10 border-blue-500/30",
  Overdue:      "text-red-400 bg-red-500/10 border-red-500/30",
  Cancelled:    "text-zinc-400 bg-zinc-500/10 border-zinc-500/30",
};

const STATUS_ICON: Record<string, React.ReactNode> = {
  Completed:    <CheckCircle2 className="w-3.5 h-3.5" />,
  Pending:      <Clock className="w-3.5 h-3.5" />,
  Scheduled:    <Clock className="w-3.5 h-3.5" />,
  "In Progress":<Zap className="w-3.5 h-3.5" />,
  Overdue:      <AlertTriangle className="w-3.5 h-3.5" />,
  Cancelled:    <XCircle className="w-3.5 h-3.5" />,
};

const TYPE_STYLE: Record<string, string> = {
  Preventive:  "text-sky-400 bg-sky-500/10 border-sky-500/30",
  Corrective:  "text-orange-400 bg-orange-500/10 border-orange-500/30",
  Predictive:  "text-purple-400 bg-purple-500/10 border-purple-500/30",
  Emergency:   "text-red-400 bg-red-500/10 border-red-500/30",
};

const ALL_STATUSES = ["Completed", "Pending", "Scheduled", "In Progress", "Overdue", "Cancelled"];
const ALL_TYPES    = ["Preventive", "Corrective", "Predictive", "Emergency"];


// ── Main page ───────────────────────────────────────────────────────────────

export default function MaintenancePage() {
  const [records, setRecords]       = useState<MaintenanceRecord[]>([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState("");
  const [filterStatus, setStatus]   = useState("all");
  const [filterType, setType]       = useState("all");
  const [filterEq, setFilterEq]     = useState("all");
  const [selected, setSelected]     = useState<MaintenanceRecord | null>(null);
  const [error, setError]           = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMaintenanceRecords(
        filterStatus !== "all" || filterType !== "all" || filterEq !== "all"
          ? {
              status: filterStatus !== "all" ? filterStatus : undefined,
              type: filterType !== "all" ? filterType : undefined,
              equipment_id: filterEq !== "all" ? filterEq : undefined,
            }
          : undefined,
      );
      setRecords(data);
    } catch (e) {
      setError("Failed to load maintenance records.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filterStatus, filterType, filterEq]);

  // Unique equipment IDs for the filter dropdown
  const equipmentOptions = Array.from(new Set(records.map((r) => r.equipment_id))).sort();

  const filtered = records.filter((r) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      r.equipment_id.toLowerCase().includes(s) ||
      r.description.toLowerCase().includes(s) ||
      (r.technician ?? "").toLowerCase().includes(s) ||
      (r.findings ?? "").toLowerCase().includes(s)
    );
  });

  // Stats
  const overdue    = records.filter((r) => r.status === "Overdue").length;
  const inProgress = records.filter((r) => r.status === "In Progress").length;
  const scheduled  = records.filter((r) => r.status === "Scheduled" || r.status === "Pending").length;
  const completed  = records.filter((r) => r.status === "Completed").length;

  return (
    <div className="flex h-full gap-4 p-4 overflow-hidden">
      {/* ── List panel ── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Wrench className="w-5 h-5 text-amber-400" />
            <h1 className="text-lg font-semibold text-white">Maintenance Logs</h1>
            <span className="text-xs text-zinc-400 ml-1">{filtered.length} records</span>
          </div>
          <button
            onClick={load}
            className="p-1.5 rounded hover:bg-white/5 text-zinc-400 hover:text-white transition-colors"
            title="Refresh"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
          {[
            { label: "Overdue",     value: overdue,    color: "text-red-400",     bg: "bg-red-500/10" },
            { label: "In Progress", value: inProgress, color: "text-blue-400",    bg: "bg-blue-500/10" },
            { label: "Scheduled",   value: scheduled,  color: "text-amber-400",   bg: "bg-amber-500/10" },
            { label: "Completed",   value: completed,  color: "text-emerald-400", bg: "bg-emerald-500/10" },
          ].map((s) => (
            <div key={s.label} className={clsx("rounded-lg p-3 border border-white/5", s.bg)}>
              <div className={clsx("text-2xl font-bold", s.color)}>{s.value}</div>
              <div className="text-xs text-zinc-400">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-3">
          <div className="relative flex-1 min-w-40">
            <Search className="absolute left-2.5 top-2 w-3.5 h-3.5 text-zinc-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search description, technician…"
              aria-label="Search maintenance records"
              className="w-full pl-8 pr-3 py-1.5 text-sm bg-zinc-800 border border-zinc-700 rounded text-white placeholder-zinc-500 focus:outline-none focus:border-amber-400/50"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
            className="text-sm bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-zinc-300 focus:outline-none"
          >
            <option value="all">All Status</option>
            {ALL_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>

          <select
            value={filterType}
            onChange={(e) => setType(e.target.value)}
            aria-label="Filter by type"
            className="text-sm bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-zinc-300 focus:outline-none"
          >
            <option value="all">All Types</option>
            {ALL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>

          <select
            value={filterEq}
            onChange={(e) => setFilterEq(e.target.value)}
            aria-label="Filter by equipment"
            className="text-sm bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-zinc-300 focus:outline-none"
          >
            <option value="all">All Equipment</option>
            {equipmentOptions.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-3 p-3 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Table */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-zinc-800">
          {loading ? (
            <div className="flex items-center justify-center h-40 text-zinc-500 text-sm">
              <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading…
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-zinc-500 text-sm gap-2">
              <Wrench className="w-8 h-8 opacity-30" />
              No maintenance records found
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-zinc-900 border-b border-zinc-800">
                <tr>
                  {["Equipment", "Type", "Description", "Date", "Technician", "Status", ""].map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-xs text-zinc-500 font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelected(r)}
                    className={clsx(
                      "border-b border-zinc-800 hover:bg-white/3 cursor-pointer transition-colors",
                      selected?.id === r.id && "bg-amber-500/5 border-l-2 border-l-amber-400",
                    )}
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <Cpu className="w-3.5 h-3.5 text-zinc-500" />
                        <span className="font-mono text-amber-400 text-xs font-medium">{r.equipment_id}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Pill label={r.type} cls={TYPE_STYLE[r.type] ?? "text-zinc-400 bg-zinc-700 border-zinc-600"} icon={STATUS_ICON[r.type] ?? null} />
                    </td>
                    <td className="px-3 py-2.5 max-w-xs">
                      <p className="text-zinc-300 truncate" title={r.description}>{r.description}</p>
                    </td>
                    <td className="px-3 py-2.5 text-zinc-400 whitespace-nowrap text-xs">
                      {r.date ?? r.scheduled_date ?? "—"}
                      {r.overdue_days != null && r.overdue_days > 0 && (
                        <span className="ml-1 text-red-400 text-[10px]">+{r.overdue_days}d overdue</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-zinc-400 text-xs">{r.technician ?? "—"}</td>
                    <td className="px-3 py-2.5">
                      <Pill label={r.status} cls={STATUS_STYLE[r.status] ?? "text-zinc-400 bg-zinc-700 border-zinc-600"} icon={STATUS_ICON[r.status] ?? null} />
                    </td>
                    <td className="px-3 py-2.5">
                      <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── Detail panel ── */}
      {selected && (
        <div className="w-80 flex-shrink-0 rounded-lg border border-zinc-800 bg-zinc-900 overflow-y-auto">
          <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Wrench className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-white">{selected.id}</span>
            </div>
            <button onClick={() => setSelected(null)} className="text-zinc-500 hover:text-white transition-colors">
              <XCircle className="w-4 h-4" />
            </button>
          </div>
          <div className="p-4 space-y-4 text-sm">

            <div className="flex flex-wrap gap-2">
              <Pill label={selected.status} cls={STATUS_STYLE[selected.status] ?? "text-zinc-400 bg-zinc-700 border-zinc-600"} icon={STATUS_ICON[selected.status] ?? null} />
              <Pill label={selected.type} cls={TYPE_STYLE[selected.type] ?? "text-zinc-400 bg-zinc-700 border-zinc-600"} icon={STATUS_ICON[selected.type] ?? null} />
            </div>

            <Section label="Equipment">
              <span className="font-mono text-amber-400">{selected.equipment_id}</span>
            </Section>

            <Section label="Description">
              <p className="text-zinc-300 leading-relaxed">{selected.description}</p>
            </Section>

            {selected.findings && (
              <Section label="Findings / Action Taken">
                <p className="text-zinc-300 leading-relaxed">{selected.findings}</p>
              </Section>
            )}

            <div className="grid grid-cols-2 gap-3">
              <Section label="Date">
                <span className="text-zinc-300">{selected.date ?? "—"}</span>
              </Section>
              <Section label="Scheduled">
                <span className="text-zinc-300">{selected.scheduled_date ?? "—"}</span>
              </Section>
              <Section label="Technician">
                <span className="text-zinc-300">{selected.technician ?? "—"}</span>
              </Section>
              {selected.overdue_days != null && selected.overdue_days > 0 && (
                <Section label="Overdue By">
                  <span className="text-red-400 font-medium">{selected.overdue_days} days</span>
                </Section>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-zinc-500 mb-0.5">{label}</p>
      <div>{children}</div>
    </div>
  );
}
