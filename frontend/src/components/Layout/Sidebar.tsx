/**
 * AI Operations Brain — Sidebar Navigation
 * • Theme toggle (sun / moon), stored in localStorage
 * • "Acting as" user picker — replaces all hardcoded reviewer names
 * • Delete All modal — purge any entity type (projects, plants, equipment, sensors, …)
 *   with a "Delete Everything" shortcut
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, BrainCircuit, Network, FileText, ShieldCheck,
  Zap, Plug, Layers, ClipboardCheck, Workflow,
  GitBranch, Factory, ShieldAlert, FormInput, Activity,
  FolderKanban, BookOpen, Wrench, AlertTriangle, Users,
  BarChart3, History, LayoutGrid, Sun, Moon, Trash2, X,
  ChevronDown, ChevronRight, Loader2, AlertCircle, CheckCircle2,
  Building2, HardDrive, Settings, Database, Menu, Sparkles,
} from "lucide-react";
import clsx from "clsx";
import { useTheme } from "@/lib/theme-context";
import { useCurrentUser, ROLE_LABEL } from "@/lib/user-context";

// ─── Nav items ────────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: "/",              icon: LayoutDashboard, label: "Dashboard" },
  { href: "/query",         icon: BrainCircuit,    label: "AI Query" },
  { href: "/equipment",     icon: HardDrive,       label: "Equipment" },
  { href: "/sensors",       icon: Activity,         label: "Sensors" },
  { href: "/rca",           icon: GitBranch,       label: "Root Cause" },
  { href: "/plant",         icon: Factory,         label: "Plant Twin" },
  { href: "/forms",         icon: FormInput,        label: "Forms" },
  { href: "/reports",       icon: BarChart3,        label: "Reports" },
  { href: "/dashboards",    icon: LayoutGrid,       label: "Dashboards" },
  { href: "/audit",         icon: History,          label: "Audit Log" },
  { href: "/graph",         icon: Network,          label: "Knowledge Graph" },
  { href: "/documents",     icon: FileText,         label: "Documents" },
  { href: "/drawings",      icon: Workflow,         label: "Drawings" },
  { href: "/work-orders",   icon: ClipboardCheck,   label: "Work Orders" },
  { href: "/maintenance",   icon: Wrench,            label: "Maintenance Logs" },
  { href: "/compliance",    icon: ShieldCheck,      label: "Compliance" },
  { href: "/integrations",  icon: Plug,             label: "Integrations" },
] as const;

const PM_NAV_ITEMS = [
  { href: "/projects",              icon: FolderKanban,  label: "Projects & Plants" },
  { href: "/permits",               icon: ShieldAlert,    label: "Permits (PTW)" },
  { href: "/procedures",            icon: BookOpen,       label: "Safety Procedures" },
  { href: "/managed-work-orders",   icon: Wrench,         label: "Managed Work Orders" },
  { href: "/inspections",           icon: AlertTriangle,  label: "Inspections & CAPA" },
] as const;

// ─── Delete-All entity catalogue ─────────────────────────────────────────────

const ENTITY_GROUPS = [
  {
    group: "Project Hierarchy",
    icon: FolderKanban,
    color: "text-amber-400",
    entities: [
      { key: "projects",   label: "Projects",      icon: FolderKanban },
      { key: "plants",     label: "Plants / Sites", icon: Building2 },
    ],
  },
  {
    group: "Assets & Equipment",
    icon: HardDrive,
    color: "text-blue-400",
    entities: [
      { key: "equipment",    label: "Equipment",          icon: HardDrive },
      { key: "maintenance",  label: "Maintenance Records", icon: Wrench },
      { key: "sensors",      label: "Sensor History",      icon: Activity },
      { key: "spare_parts",  label: "Spare Parts",         icon: Settings },
      { key: "technicians",  label: "Technicians",         icon: Users },
    ],
  },
  {
    group: "Operations",
    icon: ClipboardCheck,
    color: "text-emerald-400",
    entities: [
      { key: "drawings",          label: "Engineering Drawings",  icon: Workflow },
      { key: "procedures",        label: "Safety Procedures",     icon: BookOpen },
      { key: "permits",           label: "Permits (PTW)",         icon: ShieldAlert },
      { key: "work_orders",       label: "Managed Work Orders",   icon: Wrench },
      { key: "incidents",         label: "Incident Reports",      icon: AlertTriangle },
      { key: "inspections",       label: "Quality Inspections",   icon: ClipboardCheck },
      { key: "action_items",      label: "Action Items / CAPA",   icon: CheckCircle2 },
      { key: "saved_checklists",  label: "Saved Checklists",      icon: ClipboardCheck },
      { key: "saved_work_orders", label: "Saved Work Orders",     icon: ClipboardCheck },
    ],
  },
  {
    group: "System",
    icon: Database,
    color: "text-purple-400",
    entities: [
      { key: "documents",   label: "Documents",        icon: FileText },
      { key: "dashboards",  label: "Dashboards",       icon: LayoutGrid },
      { key: "audit_logs",  label: "Audit Logs",       icon: History },
      { key: "graph",       label: "Knowledge Graph",  icon: Network },
      { key: "compliance",  label: "Compliance",       icon: ShieldCheck },
    ],
  },
] as const;

type EntityKey = string;

// ─── Delete-All modal ─────────────────────────────────────────────────────────

function DeleteAllModal({ onClose }: { onClose: () => void }) {
  const [selected, setSelected] = useState<Set<EntityKey>>(new Set());
  const [stats, setStats]       = useState<Record<string, number>>({});
  const [loadingStats, setLoadingStats] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [result, setResult]     = useState<{ success: string[]; errors: string[] } | null>(null);

  // Fetch live record counts
  useEffect(() => {
    fetch("/api/v1/admin/stats")
      .then(r => r.ok ? r.json() : {})
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoadingStats(false));
  }, []);

  const allKeys = ENTITY_GROUPS.flatMap(g => g.entities.map(e => e.key));

  const toggle = (k: EntityKey) =>
    setSelected(s => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });

  const toggleGroup = (keys: readonly string[]) => {
    const allIn = keys.every(k => selected.has(k));
    setSelected(s => {
      const n = new Set(s);
      if (allIn) keys.forEach(k => n.delete(k));
      else        keys.forEach(k => n.add(k));
      return n;
    });
  };

  const selectAll  = () => setSelected(new Set(allKeys));
  const clearAll   = () => setSelected(new Set());
  const allSelected = allKeys.every(k => selected.has(k));

  const purge = async () => {
    if (selected.size === 0) return;
    setDeleting(true); setResult(null);
    const success: string[] = [];
    const errors:  string[] = [];

    // If all selected use the single "all" endpoint
    if (allSelected) {
      try {
        const res = await fetch("/api/v1/admin/purge?entity=all", { method: "DELETE" });
        if (res.ok) success.push(...allKeys);
        else        errors.push("all");
      } catch { errors.push("all"); }
    } else {
      for (const key of Array.from(selected)) {
        try {
          const res = await fetch(`/api/v1/admin/purge?entity=${key}`, { method: "DELETE" });
          if (res.ok) success.push(key);
          else        errors.push(key);
        } catch { errors.push(key); }
      }
    }
    setResult({ success, errors });
    setDeleting(false);
    setSelected(new Set());
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-md shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Trash2 size={16} className="text-red-400" />
            <p className="text-sm font-bold text-[#f9f9f9]">Delete Data</p>
          </div>
          <button onClick={onClose} className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><X size={16} /></button>
        </div>

        {result ? (
          // Result state
          <div className="p-5 space-y-3">
            {result.success.length > 0 && (
              <div className="flex items-start gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-semibold text-emerald-300 mb-0.5">Deleted successfully</p>
                  <p className="text-xs text-emerald-400/70">{result.success.length} entity type{result.success.length > 1 ? "s" : ""} purged</p>
                </div>
              </div>
            )}
            {result.errors.length > 0 && (
              <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <AlertCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-red-300">Failed: {result.errors.join(", ")}</p>
              </div>
            )}
            <button onClick={onClose}
              className="w-full py-2.5 text-sm rounded-lg border border-[#2a2a2a] text-[#a0a0a0] hover:text-[#f9f9f9] hover:border-[#333] transition-colors">
              Close
            </button>
          </div>
        ) : (
          <>
            {/* Select-all bar */}
            <div className="flex items-center justify-between px-5 py-2.5 border-b border-[#1a1a1a] flex-shrink-0 bg-[#111]">
              <p className="text-xs text-[#6b7280]">
                {loadingStats ? "Loading…" : `${selected.size} of ${allKeys.length} selected`}
              </p>
              <div className="flex gap-3">
                <button onClick={selectAll}
                  className="text-xs text-amber-400 hover:text-amber-300 font-medium">
                  Select All
                </button>
                <button onClick={clearAll}
                  className="text-xs text-[#6b7280] hover:text-[#f9f9f9]">
                  Clear
                </button>
              </div>
            </div>

            {/* Entity groups — scrollable */}
            <div className="overflow-y-auto flex-1 p-3 space-y-2">
              {ENTITY_GROUPS.map(({ group, icon: GIcon, color, entities }) => {
                const keys = entities.map(e => e.key);
                const allIn = keys.every(k => selected.has(k));
                const someIn = keys.some(k => selected.has(k));
                return (
                  <div key={group} className="bg-[#111] border border-[#2a2a2a] rounded-lg overflow-hidden">
                    {/* Group header */}
                    <button
                      onClick={() => toggleGroup(keys)}
                      className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-[#1a1a1a] transition-colors text-left"
                    >
                      <div className={clsx(
                        "w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0",
                        allIn ? "bg-red-500 border-red-500" : someIn ? "bg-red-500/40 border-red-500/60" : "border-[#4b5563]",
                      )}>
                        {allIn && <span className="text-white text-xs font-bold leading-none">✓</span>}
                        {!allIn && someIn && <span className="text-white text-xs font-bold leading-none">–</span>}
                      </div>
                      <GIcon size={13} className={color} />
                      <span className="text-xs font-semibold text-[#f9f9f9] flex-1">{group}</span>
                      <span className="text-xs text-[#4b5563]">
                        {keys.reduce((s, k) => s + (stats[k] || 0), 0)} records
                      </span>
                    </button>
                    {/* Entity rows */}
                    <div className="border-t border-[#1a1a1a]">
                      {entities.map(({ key, label, icon: EIcon }) => (
                        <button
                          key={key}
                          onClick={() => toggle(key)}
                          className={clsx(
                            "w-full flex items-center gap-2.5 px-3 py-1.5 text-xs hover:bg-[#1a1a1a] transition-colors text-left",
                            selected.has(key) ? "text-[#f9f9f9]" : "text-[#6b7280]",
                          )}
                        >
                          <div className={clsx(
                            "w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0",
                            selected.has(key) ? "bg-red-500 border-red-500" : "border-[#4b5563]",
                          )}>
                            {selected.has(key) && <span className="text-white text-xs leading-none" style={{ fontSize: "9px" }}>✓</span>}
                          </div>
                          <EIcon size={11} className="flex-shrink-0 text-[#4b5563]" />
                          <span className="flex-1">{label}</span>
                          <span className={clsx(
                            "font-mono text-xs px-1.5 py-0.5 rounded",
                            (stats[key] || 0) > 0 ? "bg-[#2a2a2a] text-[#a0a0a0]" : "text-[#374151]",
                          )}>
                            {stats[key] ?? "—"}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Warning + actions */}
            <div className="px-4 pb-4 pt-2 flex-shrink-0 border-t border-[#1a1a1a] space-y-2">
              {selected.size > 0 && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5">
                  <AlertCircle size={13} className="text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">
                    Permanently deletes{" "}
                    <span className="font-bold">
                      {Array.from(selected).reduce((s, k) => s + (stats[k] || 0), 0)} records
                    </span>{" "}
                    across {selected.size} entity type{selected.size > 1 ? "s" : ""}. Cannot be undone.
                  </p>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={onClose} disabled={deleting}
                  className="flex-1 py-2 text-sm rounded-lg border border-[#2a2a2a] text-[#a0a0a0] hover:text-[#f9f9f9] hover:border-[#333] transition-colors">
                  Cancel
                </button>
                <button
                  onClick={purge}
                  disabled={deleting || selected.size === 0}
                  className={clsx(
                    "flex-1 py-2 text-sm rounded-lg flex items-center justify-center gap-2 font-medium transition-colors",
                    selected.size > 0
                      ? "bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30"
                      : "border border-[#2a2a2a] text-[#374151] cursor-not-allowed",
                  )}
                >
                  {deleting
                    ? <><Loader2 size={13} className="animate-spin" />Deleting…</>
                    : allSelected
                    ? <><Trash2 size={13} />Delete Everything</>
                    : selected.size > 0
                    ? <><Trash2 size={13} />Delete ({selected.size})</>
                    : "Select items"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Demo data modal ──────────────────────────────────────────────────────────

function DemoDataModal({ onClose }: { onClose: () => void }) {
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<{
    status: string; total_entities: number; highlights: string[];
    demo_query: string; created: Record<string, unknown>;
    demo_doc_files?: { doc_id: string; filename: string }[];
  } | null>(null);
  const [error, setError] = useState("");

  const generate = async () => {
    setGenerating(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/v1/admin/generate-demo", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setGenerating(false);
    }
  };

  const WHAT_GETS_CREATED = [
    { icon: "🏭", label: "1 Project + 2 Plants (CDU Unit 4 + VDU Unit 5)" },
    { icon: "⚙️",  label: "6 Equipment — P-101 pump (vibration alarm), K-401 compressor (pressure drop), HX-201, V-301, P-202, G-101" },
    { icon: "👤", label: "6 Users covering all 7 roles (technician → manager)" },
    { icon: "🔩", label: "4 Spare parts with stock levels" },
    { icon: "🚨", label: "4 Legacy incidents (AI knowledge base + Qdrant indexed)" },
    { icon: "📋", label: "3 Formal incident reports at reported/investigation/capa stages" },
    { icon: "🔧", label: "5 Maintenance records (completed + overdue)" },
    { icon: "📦", label: "4 Managed work orders (draft → approved → in_progress → closed)" },
    { icon: "🪪", label: "3 Permits to Work (issued, under review, closed)" },
    { icon: "📖", label: "3 Safety procedures (active SOP, peer-review JSA, draft)" },
    { icon: "🔍", label: "3 Quality inspections (scheduled, in_progress, closed with findings)" },
    { icon: "✅", label: "3 Action items / CAPA across open + in_progress statuses" },
    { icon: "📈", label: "30-day sensor history — P-101 vibration trending up, K-401 pressure declining" },
    { icon: "🕸️",  label: "Knowledge graph nodes + links for all entities" },
    { icon: "⚖️",  label: "Compliance records with open issues per equipment" },
  ];

  const DOC_ICON: Record<string, string> = {
    pdf: "📕", docx: "📘", xlsx: "📗", pptx: "📙", txt: "📄", csv: "📊",
  };

  const getDocIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase() ?? "";
    return DOC_ICON[ext] ?? "📄";
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-amber-400" />
            <div>
              <p className="text-sm font-bold text-[#f9f9f9]">Generate Demo Data</p>
              <p className="text-[10px] text-[#4b5563]">Creates 60+ realistic entities across all entity types</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><X size={16} /></button>
        </div>

        {result ? (
          /* ── Success state ── */
          <div className="overflow-y-auto flex-1 p-5 space-y-4">

            {/* Step 1 done */}
            <div className="flex items-start gap-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4">
              <CheckCircle2 size={18} className="text-emerald-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-emerald-300">
                  Step 1 done — {result.total_entities} entities in database
                </p>
                <p className="text-xs text-emerald-400/70 mt-0.5">Equipment, sensors, incidents, WOs, PTWs, procedures all loaded.</p>
              </div>
            </div>

            {/* Step 2 — upload docs */}
            {result.demo_doc_files && result.demo_doc_files.length > 0 && (
              <div className="bg-amber-500/5 border border-amber-500/30 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm">📂</span>
                  <div>
                    <p className="text-xs font-semibold text-amber-300">Step 2 — Upload sample documents</p>
                    <p className="text-[10px] text-amber-400/60 mt-0.5">
                      Download each file below, then drag them into the <strong className="text-amber-400">Documents</strong> page to run the AI extraction pipeline.
                    </p>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {result.demo_doc_files.map(({ filename }) => (
                    <a
                      key={filename}
                      href={`/api/v1/admin/demo-docs/${filename}`}
                      download={filename}
                      className="flex items-center gap-2.5 bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] hover:border-amber-500/30 rounded-lg px-3 py-2 transition-colors group"
                    >
                      <span className="text-sm flex-shrink-0">{getDocIcon(filename)}</span>
                      <span className="flex-1 text-[11px] text-[#c0c0c0] truncate group-hover:text-[#f9f9f9]">{filename}</span>
                      <span className="text-[10px] text-amber-400 opacity-0 group-hover:opacity-100 flex-shrink-0 transition-opacity">↓ download</span>
                    </a>
                  ))}
                </div>
                <a
                  href="/documents"
                  onClick={onClose}
                  className="flex items-center justify-center gap-2 w-full py-2 text-xs rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/30 text-amber-300 font-semibold transition-colors"
                >
                  <span>Go to Documents →</span>
                </a>
              </div>
            )}

            {/* Demo query */}
            <div className="bg-[#141414] border border-[#252525] rounded-xl p-4">
              <p className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
                <Zap size={12} /> Try this query first
              </p>
              <p className="text-xs text-[#e0e0e0] font-mono leading-relaxed">{result.demo_query}</p>
            </div>

            {/* Highlights */}
            <div>
              <p className="text-xs font-semibold text-[#6b7280] mb-2">What&apos;s in the data</p>
              <div className="space-y-1.5">
                {result.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-[#a0a0a0]">
                    <span className="text-amber-400 flex-shrink-0 mt-0.5">›</span>
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Entity counts */}
            <div className="bg-[#141414] border border-[#252525] rounded-xl p-3">
              <p className="text-[10px] font-semibold text-[#4b5563] mb-2 uppercase tracking-wider">Entity counts</p>
              <div className="grid grid-cols-2 gap-1">
                {Object.entries(result.created).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between">
                    <span className="text-[10px] text-[#6b7280]">{k}</span>
                    <span className="text-[10px] font-mono text-amber-400">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            <button onClick={onClose}
              className="w-full py-2.5 text-sm rounded-xl bg-amber-500 text-black font-semibold hover:bg-amber-400 transition-colors">
              Done — Start the Demo
            </button>
          </div>
        ) : (
          /* ── Pre-generate state ── */
          <>
            <div className="overflow-y-auto flex-1 p-4 space-y-3">
              <div>
                <p className="text-xs font-semibold text-[#6b7280] mb-2 uppercase tracking-wider">Step 1 — what gets created in DB</p>
                <div className="space-y-1.5">
                  {WHAT_GETS_CREATED.map(({ icon, label }, i) => (
                    <div key={i} className="flex items-start gap-2.5 bg-[#141414] rounded-lg px-3 py-2">
                      <span className="text-sm flex-shrink-0">{icon}</span>
                      <span className="text-xs text-[#a0a0a0] leading-relaxed">{label}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-3">
                <p className="text-xs font-semibold text-amber-400 mb-1.5">Step 2 — upload documents yourself</p>
                <p className="text-[11px] text-[#a0a0a0] leading-relaxed">
                  9 sample documents (PDF, DOCX, XLSX, PPTX, TXT, CSV) will be generated on disk.
                  After generation, download them from the success screen and upload via the{" "}
                  <strong className="text-amber-300">Documents</strong> page to see the full AI extraction pipeline live.
                </p>
              </div>

              {error && (
                <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                  <AlertCircle size={13} className="text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-300">{error}</p>
                </div>
              )}
            </div>

            <div className="px-4 pb-4 pt-2 flex-shrink-0 border-t border-[#1a1a1a] space-y-2">
              <p className="text-[10px] text-[#4b5563]">
                ✓ Safe to run on an empty DB or alongside existing data — uses fixed IDs (idempotent).
              </p>
              <div className="flex gap-2">
                <button onClick={onClose} disabled={generating}
                  className="flex-1 py-2.5 text-sm rounded-xl border border-[#252525] text-[#6b7280] hover:text-[#f9f9f9] transition-colors">
                  Cancel
                </button>
                <button
                  onClick={generate}
                  disabled={generating}
                  className="flex-1 py-2.5 text-sm rounded-xl bg-amber-500 text-black font-semibold hover:bg-amber-400 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                >
                  {generating
                    ? <><Loader2 size={14} className="animate-spin" />Generating…</>
                    : <><Sparkles size={14} />Generate Demo Data</>
                  }
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── User picker ──────────────────────────────────────────────────────────────

function UserPicker() {
  const { users, currentUser, setCurrentUser } = useCurrentUser();
  const [open, setOpen] = useState(false);

  if (!currentUser) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-[#242424] transition-colors text-left"
      >
        <div className="w-7 h-7 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center flex-shrink-0">
          <span className="text-amber-400 text-xs font-bold">{currentUser.name.charAt(0)}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-[#f9f9f9] truncate">{currentUser.name}</p>
          <p className="text-xs text-[#6b7280] truncate">{ROLE_LABEL[currentUser.role] ?? currentUser.role}</p>
        </div>
        <ChevronDown size={12} className="text-[#4b5563] flex-shrink-0" />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 right-0 mb-1 bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl shadow-2xl z-50 max-h-52 overflow-y-auto">
            <p className="px-3 py-2 text-xs font-semibold text-[#4b5563] uppercase tracking-wider border-b border-[#2a2a2a]">
              Acting As
            </p>
            {users.map(u => (
              <button
                key={u.id}
                onClick={() => { setCurrentUser(u); setOpen(false); }}
                className={clsx(
                  "w-full flex items-center gap-2 px-3 py-2 text-xs hover:bg-[#2a2a2a] transition-colors text-left",
                  currentUser?.id === u.id ? "text-amber-400 bg-amber-500/5" : "text-[#a0a0a0]",
                )}
              >
                <div className="w-6 h-6 rounded-full bg-[#2a2a2a] border border-[#333] flex items-center justify-center flex-shrink-0">
                  <span className="text-[#6b7280] text-xs">{u.name.charAt(0)}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{u.name}</p>
                  <p className="text-[#4b5563]">{ROLE_LABEL[u.role] ?? u.role}</p>
                </div>
                {currentUser?.id === u.id && <span className="text-amber-400 flex-shrink-0">●</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [demoOpen,   setDemoOpen]   = useState(false);
  const [apiStatus, setApiStatus]   = useState<"online" | "offline" | "checking">("checking");
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  useEffect(() => {
    fetch("/api/v1/equipment")
      .then(r => setApiStatus(r.ok ? "online" : "offline"))
      .catch(() => setApiStatus("offline"));
  }, []);

  const sidebarContent = (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-[#1a1a1a] border-r border-[#2a2a2a] h-full">

      {/* Logo + theme toggle */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-[#2a2a2a]">
        <Zap size={20} className="text-amber-500 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] leading-tight">EPIC - Enterprise Platform for Industial cognition </p>
          <p className="text-xs text-[#6b7280] leading-tight">Brain v1.0</p>
        </div>
        <button
          onClick={toggleTheme}
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          className="p-1.5 rounded-md border border-[#2a2a2a] text-[#6b7280] hover:text-amber-400 hover:border-amber-500/40 transition-colors flex-shrink-0"
        >
          {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
        </button>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileOpen(false)}
          className="lg:hidden p-1.5 rounded-md border border-[#2a2a2a] text-[#6b7280] hover:text-[#f9f9f9] transition-colors flex-shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link key={href} href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                active
                  ? "bg-amber-500/10 text-amber-400 font-medium"
                  : "text-[#a0a0a0] hover:bg-[#242424] hover:text-[#f9f9f9]",
              )}
            >
              <Icon size={15} />{label}
            </Link>
          );
        })}

        <div className="pt-2 mt-1 border-t border-[#2a2a2a]">
          <p className="px-3 pb-1 text-xs font-semibold text-[#4b5563] uppercase tracking-wider">
            Project Mgmt
          </p>
          {PM_NAV_ITEMS.map(({ href, icon: Icon, label }) => {
            const active = pathname === href || pathname.startsWith(href);
            return (
              <Link key={href} href={href}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  active
                    ? "bg-amber-500/10 text-amber-400 font-medium"
                    : "text-[#a0a0a0] hover:bg-[#242424] hover:text-[#f9f9f9]",
                )}
              >
                <Icon size={15} />{label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-[#2a2a2a] flex-shrink-0 p-3 space-y-2">
        <UserPicker />

        {/* Generate Demo Data button */}
        <button
          onClick={() => setDemoOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 hover:border-amber-500/40 transition-colors"
        >
          <Sparkles size={13} />
          Generate Demo Data
        </button>

        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-1.5">
            <span className={clsx("h-1.5 w-1.5 rounded-full", {
              "bg-emerald-500 animate-pulse": apiStatus === "online",
              "bg-red-500":                   apiStatus === "offline",
              "bg-amber-500 animate-pulse":   apiStatus === "checking",
            })} />
            <p className={clsx("text-xs", {
              "text-emerald-500": apiStatus === "online",
              "text-red-400":     apiStatus === "offline",
              "text-amber-400":   apiStatus === "checking",
            })}>
              {apiStatus === "online"   ? "All systems online"
               : apiStatus === "offline" ? "API offline"
               : "Checking…"}
            </p>
          </div>
          <button
            onClick={() => setDeleteOpen(true)}
            title="Delete all data"
            className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-[#2a2a2a] text-[#4b5563] hover:text-red-400 hover:border-red-500/40 hover:bg-red-500/5 transition-colors text-xs font-medium"
          >
            <Trash2 size={13} />
            <span>Delete</span>
          </button>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      {/* ── Desktop sidebar (always visible ≥ lg) ─────────────────────── */}
      <div className="hidden lg:flex h-screen">
        {sidebarContent}
      </div>

      {/* ── Mobile hamburger button ────────────────────────────────────── */}
      <button
        onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-3 left-3 z-50 p-2 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-[#a0a0a0] hover:text-amber-400 shadow-lg"
        aria-label="Open navigation"
      >
        <Menu size={18} />
      </button>

      {/* ── Mobile overlay sidebar ─────────────────────────────────────── */}
      {mobileOpen && (
        <>
          {/* Backdrop */}
          <div
            className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          {/* Slide-in panel */}
          <div className="lg:hidden fixed inset-y-0 left-0 z-50 h-full">
            {sidebarContent}
          </div>
        </>
      )}

      {deleteOpen && <DeleteAllModal onClose={() => setDeleteOpen(false)} />}
      {demoOpen   && <DemoDataModal  onClose={() => setDemoOpen(false)}   />}
    </>
  );
}
