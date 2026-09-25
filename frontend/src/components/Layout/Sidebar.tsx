/**
 * EPIC — Sidebar Navigation
 * • Theme toggle (sun / moon), stored in localStorage
 * • The signed-in user (from the session cookie) and Sign out
 * • Delete All modal — purge any entity type the backend allows (equipment, sensors, documents, …)
 *   with a "Delete Everything" shortcut
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, BrainCircuit, Network, FileText,
  Zap, ClipboardCheck, Activity,
  Wrench,
  Sun, Moon, Trash2, X,
  Loader2, AlertCircle, CheckCircle2,
  HardDrive, Menu, Sparkles, LogOut,
} from "lucide-react";
import clsx from "clsx";
import { useTheme } from "@/lib/theme-context";
import { useCurrentUser } from "@/lib/user-context";
import { forbiddenMessage } from "@/lib/api";
import { adminRoles, hasRole, roleLabel } from "@/lib/roles";
import { useDialogFocus } from "@/lib/useDialogFocus";

// ─── Nav items ────────────────────────────────────────────────────────────────

const NAV_ITEMS = [
  { href: "/",              icon: LayoutDashboard, label: "Dashboard" },
  { href: "/query",         icon: BrainCircuit,    label: "AI Query" },
  { href: "/equipment",     icon: HardDrive,       label: "Equipment" },
  { href: "/sensors",       icon: Activity,         label: "Sensors" },
  { href: "/graph",         icon: Network,          label: "Knowledge Graph" },
  { href: "/documents",     icon: FileText,         label: "Documents" },
  { href: "/work-orders",   icon: ClipboardCheck,   label: "Work Orders" },
  { href: "/maintenance",   icon: Wrench,            label: "Maintenance Logs" },
] as const;

// ─── Delete-All modal ─────────────────────────────────────────────────────────

function DeleteAllModal({ onClose }: { onClose: () => void }) {
  const [deleting, setDeleting] = useState(false);
  const [result, setResult]     = useState<{ success: boolean; error?: string } | null>(null);

  const dialogRef = useDialogFocus<HTMLDivElement>(onClose);

  const purgeAll = async () => {
    setDeleting(true);
    setResult(null);
    try {
      const res = await fetch("/api/v1/admin/purge?entity=all", { method: "DELETE" });
      if (res.status === 403) {
        setResult({ success: false, error: forbiddenMessage });
      } else if (res.ok) {
        setResult({ success: true });
      } else {
        setResult({ success: false, error: "Failed to purge database" });
      }
    } catch {
      setResult({ success: false, error: "Network error while purging database" });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-data-dialog-title"
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3"
    >
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-md shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Trash2 size={16} className="text-red-400" />
            <p id="delete-data-dialog-title" className="text-sm font-bold text-[#f9f9f9]">Delete All Data</p>
          </div>
          <button onClick={onClose} aria-label="Close dialog" className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><X size={16} /></button>
        </div>

        {result ? (
          // Result state
          <div className="p-5 space-y-3">
            {result.success ? (
              <div className="flex items-start gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                <CheckCircle2 size={14} className="text-emerald-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-xs font-semibold text-emerald-300 mb-0.5">Database purged successfully</p>
                  <p className="text-xs text-emerald-400/70">All entity records have been reset. Audit logs were preserved.</p>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <AlertCircle size={14} className="text-red-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-red-300">Failed: {result.error}</p>
              </div>
            )}
            <button
              onClick={onClose}
              className="w-full py-2.5 text-sm rounded-lg border border-[#2a2a2a] text-[#a0a0a0] hover:text-[#f9f9f9] hover:border-[#333] transition-colors"
            >
              Close
            </button>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            <div className="flex items-start gap-2.5 bg-red-500/10 border border-red-500/20 rounded-lg p-3">
              <AlertCircle size={15} className="text-red-400 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs font-semibold text-red-300">Permanent Database Reset</p>
                <p className="text-xs text-red-400/80 leading-relaxed">
                  This will permanently delete all records across all entity types (equipment, sensors, incidents, work orders, documents, graph, compliance). Audit logs are append-only evidence and cannot be purged. This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                onClick={onClose}
                disabled={deleting}
                className="flex-1 py-2 text-sm rounded-lg border border-[#2a2a2a] text-[#a0a0a0] hover:text-[#f9f9f9] hover:border-[#333] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={purgeAll}
                disabled={deleting}
                className="flex-1 py-2 text-sm rounded-lg flex items-center justify-center gap-2 font-medium bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30 transition-colors"
              >
                {deleting ? (
                  <>
                    <Loader2 size={13} className="animate-spin" />
                    Deleting…
                  </>
                ) : (
                  <>
                    <Trash2 size={13} />
                    Delete Everything
                  </>
                )}
              </button>
            </div>
          </div>
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
  const dialogRef = useDialogFocus<HTMLDivElement>(onClose);

  const generate = async () => {
    setGenerating(true); setError(""); setResult(null);
    try {
      const res = await fetch("/api/v1/admin/generate-demo", { method: "POST" });
      if (res.status === 403) throw new Error(forbiddenMessage);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setGenerating(false);
    }
  };

  const WHAT_GETS_CREATED = [
    { icon: "⚙️",  label: "Equipment — P-101 pump (vibration alarm), K-401 compressor (pressure drop), HX-201, V-301, P-202, G-101" },
    { icon: "👤", label: "Demo users across the technician → manager roles, and who looks after each asset" },
    { icon: "🔩", label: "Spare parts with stock levels" },
    { icon: "🚨", label: "Past incidents for retrieval and lessons learned" },
    { icon: "🔧", label: "Maintenance records (one overdue) and work orders, one completed with outcome feedback" },
    { icon: "📈", label: "30-day history for every sensor — P-101 vibration and bearing temperature rising, K-401 pressure falling" },
    { icon: "🕸️",  label: "Knowledge graph linking equipment, incidents, work orders, technicians and spare parts" },
    { icon: "⚖️",  label: "Compliance records, with open issues on most equipment" },
  ];

  const DOC_ICON: Record<string, string> = {
    pdf: "📕", docx: "📘", xlsx: "📗", pptx: "📙", txt: "📄", csv: "📊",
  };

  const getDocIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase() ?? "";
    return DOC_ICON[ext] ?? "📄";
  };

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="generate-demo-dialog-title"
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/75 p-3"
    >
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-amber-400" />
            <div>
              <p id="generate-demo-dialog-title" className="text-sm font-bold text-[#f9f9f9]">Generate Demo Data</p>
              <p className="text-[10px] text-[#4b5563]">Loads a realistic demo dataset for the AI query pipeline</p>
            </div>
          </div>
          <button onClick={onClose} aria-label="Close dialog" className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><X size={16} /></button>
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
                <p className="text-xs text-emerald-400/70 mt-0.5">Equipment, sensors, incidents, maintenance records, compliance and the knowledge graph are loaded.</p>
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

            <button onClick={() => { onClose(); window.location.href = "/"; }}
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
                  3 sample documents (two PDF reports and a TXT shift handover) will be generated on disk.
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

// ─── Signed-in user ───────────────────────────────────────────────────────────

function SignedInUser() {
  const { currentUser, logoutUser } = useCurrentUser();
  if (!currentUser) return null;

  return (
    <div className="flex items-center gap-1 w-full">
      <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg text-left min-w-0">
        <div className="w-7 h-7 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center flex-shrink-0">
          <span className="text-amber-400 text-xs font-bold">{currentUser.name.charAt(0)}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-[#f9f9f9] truncate">{currentUser.name}</p>
          <p className="text-xs text-[#6b7280] truncate">{roleLabel[currentUser.role] ?? currentUser.role}</p>
        </div>
      </div>
      <button
        onClick={() => logoutUser()}
        title="Sign out"
        aria-label="Sign out"
        className="p-2 rounded-lg text-[#6b7280] hover:text-red-400 hover:bg-red-500/10 transition-colors flex-shrink-0"
      >
        <LogOut size={14} />
      </button>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar() {
  // The login check lives here because hooks must not run after an early return.
  return usePathname() === "/login" ? null : <SidebarContent />;
}

function SidebarContent() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { currentUser } = useCurrentUser();
  const isAdmin = hasRole(currentUser?.role, adminRoles);
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
          <p className="text-sm font-semibold text-[#f9f9f9] leading-tight">EPIC — Enterprise Platform for Industrial Cognition</p>
          <p className="text-xs text-[#6b7280] leading-tight">EPIC v1.0</p>
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
          aria-label="Close navigation"
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
      </nav>

      {/* Footer */}
      <div className="border-t border-[#2a2a2a] flex-shrink-0 p-3 space-y-2">
        <SignedInUser />

        {/* Generate Demo Data button (manager only) */}
        {isAdmin && (
          <button
            onClick={() => setDemoOpen(true)}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-amber-500/10 border border-amber-500/25 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 hover:border-amber-500/40 transition-colors"
          >
            <Sparkles size={13} />
            Generate Demo Data
          </button>
        )}

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
          {isAdmin && (
            <button
              onClick={() => setDeleteOpen(true)}
              title="Delete all data"
              aria-label="Delete all data"
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg border border-[#2a2a2a] text-[#4b5563] hover:text-red-400 hover:border-red-500/40 hover:bg-red-500/5 transition-colors text-xs font-medium"
            >
              <Trash2 size={13} />
              <span>Delete</span>
            </button>
          )}
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
