/**
 * AI Operations Brain — Quality Inspections & Action Items Page
 * Two-tab interface: Inspections (scheduled/in-progress/closed) + Action Items (CAPA).
 * Shows full review workflow and allows inline result recording.
 */
"use client";

import { useEffect, useState } from "react";
import {
  ClipboardCheck, AlertTriangle, CheckCircle2, Clock, XCircle,
  ChevronRight, X, User, Calendar, AlertCircle, ListChecks, Plus, Loader2,
} from "lucide-react";
import clsx from "clsx";
import { useCurrentUser } from "@/lib/user-context";
import { usePageState } from "@/lib/page-state";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface Inspection {
  id: string;
  inspection_number: string;
  title: string;
  inspection_type: string;
  status: string;
  priority: string;
  scheduled_date?: string;
  actual_date?: string;
  inspector_name?: string;
  plant_id?: string;
  equipment_ids: string[];
  checklist_items: any[];
  non_conformances: any[];
  observations: string[];
  overall_score?: number;
  summary_notes?: string;
  reviewer_name?: string;
  reviewer_decision?: string;
  audit_trail: any[];
  created_at: string;
}

interface ActionItem {
  id: string;
  action_number: string;
  title: string;
  description: string;
  source_type?: string;
  source_ref?: string;
  action_type: string;
  priority: string;
  status: string;
  assigned_to_name?: string;
  due_date?: string;
  completed_by_name?: string;
  completed_at?: string;
  verifier_name?: string;
  verified_at?: string;
}

const INSP_STATUS_COLOR: Record<string, string> = {
  scheduled:             "text-blue-400 bg-blue-500/10 border-blue-500/30",
  in_progress:           "text-amber-400 bg-amber-500/10 border-amber-500/30",
  pending_review:        "text-purple-400 bg-purple-500/10 border-purple-500/30",
  closed_satisfactory:   "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  closed_with_findings:  "text-orange-400 bg-orange-500/10 border-orange-500/30",
  rejected:              "text-red-400 bg-red-500/10 border-red-500/30",
};

const ACTION_STATUS_COLOR: Record<string, string> = {
  open:                 "text-blue-400 bg-blue-500/10 border-blue-500/30",
  in_progress:          "text-amber-400 bg-amber-500/10 border-amber-500/30",
  pending_verification: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  verified:             "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  overdue:              "text-red-400 bg-red-500/10 border-red-500/30",
};

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-red-400 bg-red-500/10 border-red-500/30",
  high:     "text-orange-400 bg-orange-500/10 border-orange-500/30",
  medium:   "text-amber-400 bg-amber-500/10 border-amber-500/30",
  low:      "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

function Pill({ label, cls }: { label: string; cls: string }) {
  return <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium", cls)}>{label}</span>;
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 36 36" className="w-10 h-10 -rotate-90">
        <circle cx="18" cy="18" r="15" fill="none" stroke="#2a2a2a" strokeWidth="3" />
        <circle cx="18" cy="18" r="15" fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${(score / 100) * 94.25} 94.25`} strokeLinecap="round" />
      </svg>
      <span className="text-lg font-bold" style={{ color }}>{score}%</span>
    </div>
  );
}

function InspectionCard({ insp, onSelect }: { insp: Inspection; onSelect: () => void }) {
  const ncCount = insp.non_conformances?.length ?? 0;
  const itemCount = insp.checklist_items?.length ?? 0;
  const doneCount = insp.checklist_items?.filter(i => i.result).length ?? 0;
  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 cursor-pointer hover:border-amber-500/40 transition-colors"
      onClick={onSelect}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <ClipboardCheck size={16} className="text-amber-500 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[#f9f9f9] truncate">{insp.title}</p>
            <p className="text-xs text-[#6b7280]">{insp.inspection_number}</p>
          </div>
        </div>
        <Pill label={insp.status.replace(/_/g, " ")} cls={INSP_STATUS_COLOR[insp.status] ?? ""} />
      </div>

      <div className="flex items-center gap-2 mb-3">
        <Pill label={insp.inspection_type.replace(/_/g, " ")} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
        <Pill label={insp.priority} cls={PRIORITY_COLOR[insp.priority] ?? ""} />
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className="text-base font-bold text-[#f9f9f9]">{itemCount}</p>
          <p className="text-xs text-[#6b7280]">Checks</p>
        </div>
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className={clsx("text-base font-bold", ncCount > 0 ? "text-red-400" : "text-emerald-400")}>{ncCount}</p>
          <p className="text-xs text-[#6b7280]">NCs</p>
        </div>
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className="text-base font-bold text-amber-400">{insp.overall_score != null ? `${insp.overall_score}%` : "—"}</p>
          <p className="text-xs text-[#6b7280]">Score</p>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-[#6b7280]">
        {insp.inspector_name && <span className="flex items-center gap-1"><User size={11} />{insp.inspector_name}</span>}
        {insp.scheduled_date && <span className="flex items-center gap-1"><Calendar size={11} />{insp.scheduled_date}</span>}
      </div>
    </div>
  );
}

function InspectionDetail({ insp, onClose, onRefresh }: { insp: Inspection; onClose: () => void; onRefresh: () => void }) {
  const [tab, setTab] = useState<"checklist" | "ncs" | "audit">("checklist");
  const [loading, setLoading] = useState(false);
  const { currentUser } = useCurrentUser();

  const doAction = async (endpoint: string, payload: any, useBody = true) => {
    setLoading(true);
    try {
      let url = `${API}/api/v1/inspections/${insp.id}/${endpoint}`;
      const opts: RequestInit = useBody
        ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }
        : { method: "POST" };
      if (!useBody) url += "?" + new URLSearchParams(payload).toString();
      const res = await fetch(url, opts);
      if (!res.ok) { const e = await res.json(); alert(e.detail); }
      else { onRefresh(); onClose(); }
    } catch { alert("Network error"); }
    setLoading(false);
  };

  const resultColor = (r?: string) =>
    r === "pass" ? "text-emerald-400" : r === "fail" ? "text-red-400" : r === "obs" ? "text-amber-400" : "text-[#6b7280]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">{insp.title}</p>
            <p className="text-xs text-[#6b7280]">{insp.inspection_number}</p>
          </div>
          <div className="flex items-center gap-2">
            {insp.overall_score != null && <ScoreRing score={insp.overall_score} />}
            <Pill label={insp.status.replace(/_/g, " ")} cls={INSP_STATUS_COLOR[insp.status] ?? ""} />
            <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={20} /></button>
          </div>
        </div>

        <div className="flex gap-1 px-6 pt-3 border-b border-[#2a2a2a]">
          {(["checklist", "ncs", "audit"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx(
                "px-3 py-1.5 text-xs rounded-t font-medium capitalize",
                tab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]",
              )}>
              {t === "ncs" ? `Non-Conformances (${insp.non_conformances?.length ?? 0})` : t}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === "checklist" && (
            <div className="space-y-2">
              {insp.checklist_items?.map((item, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-[#f9f9f9]">{item.check_item}</p>
                      <p className="text-xs text-[#6b7280]">{item.criteria}</p>
                    </div>
                    <span className={clsx("text-xs font-bold", resultColor(item.result))}>
                      {item.result?.toUpperCase() || "PENDING"}
                    </span>
                  </div>
                  {item.findings && <p className="text-xs text-amber-400 mt-1">Finding: {item.findings}</p>}
                </div>
              ))}
              {insp.status === "scheduled" && (
                <button disabled={loading}
                  onClick={() => doAction("start", { inspector_id: currentUser?.id ?? (insp.inspector_name ? "USR-007" : "USR-003"), inspector_name: currentUser?.name ?? insp.inspector_name ?? "Inspector" })}
                  className="w-full mt-3 py-2 text-sm rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30">
                  Start Inspection
                </button>
              )}
              {insp.status === "in_progress" && (
                <button disabled={loading}
                  onClick={() => doAction("submit", false, false) || doAction("submit", {}, false)}
                  className="w-full mt-3 py-2 text-sm rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 hover:bg-purple-500/30">
                  Submit for Review
                </button>
              )}
              {insp.status === "pending_review" && (
                <div className="bg-[#242424] rounded-lg p-4 mt-3 space-y-3">
                  <p className="text-xs font-semibold text-purple-400">Reviewer Action</p>
                  <div className="flex gap-2">
                    <button disabled={loading}
                      onClick={() => doAction("review", { reviewer_id: currentUser?.id ?? "USR-005", reviewer_name: currentUser?.name ?? "Robert Halliday", decision: "closed_satisfactory", comments: "All checks passed" })}
                      className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Close — Satisfactory</button>
                    <button disabled={loading}
                      onClick={() => doAction("review", { reviewer_id: currentUser?.id ?? "USR-005", reviewer_name: currentUser?.name ?? "Robert Halliday", decision: "closed_with_findings", comments: "NCs to be actioned" })}
                      className="flex-1 py-1.5 text-xs rounded bg-orange-500/20 text-orange-400 border border-orange-500/30">Close — With Findings</button>
                    <button disabled={loading}
                      onClick={() => doAction("review", { reviewer_id: currentUser?.id ?? "USR-005", reviewer_name: currentUser?.name ?? "Robert Halliday", decision: "rejected", comments: "Incomplete" })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Reject</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === "ncs" && (
            <div className="space-y-3">
              {insp.non_conformances?.length === 0 && <p className="text-xs text-[#6b7280]">No non-conformances recorded.</p>}
              {insp.non_conformances?.map((nc, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{nc.id}</p>
                    <div className="flex gap-1">
                      <Pill label={nc.severity} cls={nc.severity === "critical" ? "text-red-400 bg-red-500/10 border-red-500/20" : nc.severity === "major" ? "text-orange-400 bg-orange-500/10 border-orange-500/20" : "text-amber-400 bg-amber-500/10 border-amber-500/20"} />
                      <Pill label={nc.status} cls={nc.status === "closed" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" : "text-blue-400 bg-blue-500/10 border-blue-500/20"} />
                    </div>
                  </div>
                  <p className="text-sm text-[#a0a0a0]">{nc.description}</p>
                  {nc.action_required && <p className="text-xs text-amber-400 mt-1">Action: {nc.action_required}</p>}
                  {nc.due_date && <p className="text-xs text-[#6b7280] mt-1">Due: {nc.due_date}</p>}
                </div>
              ))}
              {insp.summary_notes && (
                <div className="bg-[#242424] rounded-lg p-3">
                  <p className="text-xs font-semibold text-[#f9f9f9] mb-1">Summary</p>
                  <p className="text-xs text-[#a0a0a0]">{insp.summary_notes}</p>
                </div>
              )}
            </div>
          )}

          {tab === "audit" && (
            <div>
              {insp.audit_trail?.map((entry, i) => (
                <div key={i} className="flex gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[#f9f9f9]">{entry.action?.replace(/_/g, " ")}</span>
                      <span className="text-xs text-[#6b7280]">by {entry.user}</span>
                    </div>
                    <p className="text-xs text-[#6b7280]">{entry.timestamp}</p>
                    {entry.comments && <p className="text-xs text-[#a0a0a0] italic">{entry.comments}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ActionItemCard({ action, onComplete, onVerify }: { action: ActionItem; onComplete: () => void; onVerify: () => void }) {
  const isOverdue = action.due_date && new Date(action.due_date) < new Date() && !["verified"].includes(action.status);
  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] truncate">{action.title}</p>
          <p className="text-xs text-[#6b7280]">{action.action_number} · {action.source_ref || action.source_type || "—"}</p>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          <Pill label={action.status.replace(/_/g, " ")} cls={ACTION_STATUS_COLOR[action.status] ?? ""} />
        </div>
      </div>
      <div className="flex items-center gap-2 mb-2">
        <Pill label={action.action_type} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
        <Pill label={action.priority} cls={PRIORITY_COLOR[action.priority] ?? ""} />
        {isOverdue && <Pill label="OVERDUE" cls="text-red-400 bg-red-500/10 border-red-500/30" />}
      </div>
      <p className="text-xs text-[#a0a0a0] mb-3 line-clamp-2">{action.description}</p>
      <div className="flex items-center justify-between text-xs text-[#6b7280]">
        <span className="flex items-center gap-1"><User size={11} />{action.assigned_to_name || "Unassigned"}</span>
        {action.due_date && <span className="flex items-center gap-1"><Calendar size={11} />Due {action.due_date}</span>}
      </div>
      {action.status === "in_progress" && (
        <button onClick={onComplete}
          className="mt-3 w-full py-1.5 text-xs rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30">
          Mark Complete
        </button>
      )}
      {action.status === "pending_verification" && (
        <button onClick={onVerify}
          className="mt-3 w-full py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30">
          Verify Completion
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────────────────────────

function Toast({ msg, ok, onDone }: { msg: string; ok: boolean; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3200); return () => clearTimeout(t); }, [onDone]);
  return (
    <div className={clsx(
      "fixed bottom-6 right-6 z-[100] flex items-center gap-2 px-4 py-3 rounded-lg border shadow-xl text-sm font-medium",
      ok ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" : "bg-red-500/10 border-red-500/30 text-red-300",
    )}>
      {ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}{msg}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Inspection Create Modal
// ─────────────────────────────────────────────────────────────────────────────

const INSP_TYPES = ["equipment","process","safety_audit","environmental","contractor","pre_startup","housekeeping"];
const INSP_PRIORITIES = ["critical","high","medium","low"];
const INSP_TYPE_LABEL: Record<string, string> = {
  equipment: "Equipment Inspection", process: "Process Inspection",
  safety_audit: "Safety Audit", environmental: "Environmental",
  contractor: "Contractor Inspection", pre_startup: "Pre-Startup",
  housekeeping: "Housekeeping",
};

const iInp = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
const iSel = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";
function IFL({ label, req, children }: { label: string; req?: boolean; children: React.ReactNode }) {
  return <div><label className="block text-xs font-medium text-[#a0a0a0] mb-1">{label}{req && <span className="text-red-400 ml-0.5">*</span>}</label>{children}</div>;
}

function InspectionCreateModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    title: "", inspection_type: "equipment", priority: "medium",
    scheduled_date: "", inspector_name: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const s = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setErr("Title is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/inspections`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(), inspection_type: form.inspection_type,
          priority: form.priority,
          scheduled_date: form.scheduled_date || undefined,
          inspector_name: form.inspector_name || undefined,
        }),
      });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-lg max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">New Inspection</p>
            <p className="text-xs text-[#6b7280]">Creates in Scheduled status — start when inspector begins</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <IFL label="Title" req>
            <input className={iInp} value={form.title} onChange={e => s("title", e.target.value)} placeholder="Quarterly pump house safety audit" />
          </IFL>
          <div className="grid grid-cols-2 gap-4">
            <IFL label="Inspection Type">
              <select className={iSel} value={form.inspection_type} onChange={e => s("inspection_type", e.target.value)}>
                {INSP_TYPES.map(t => <option key={t} value={t}>{INSP_TYPE_LABEL[t]}</option>)}
              </select>
            </IFL>
            <IFL label="Priority">
              <select className={iSel} value={form.priority} onChange={e => s("priority", e.target.value)}>
                {INSP_PRIORITIES.map(p => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
              </select>
            </IFL>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <IFL label="Scheduled Date"><input type="date" className={iInp} value={form.scheduled_date} onChange={e => s("scheduled_date", e.target.value)} /></IFL>
            <IFL label="Inspector Name"><input className={iInp} value={form.inspector_name} onChange={e => s("inspector_name", e.target.value)} placeholder="Sarah Chen" /></IFL>
          </div>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}Schedule Inspection
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function InspectionsPage() {
  const { inspections: inspState, updateInspections } = usePageState();
  const [inspections, setInspections] = useState<Inspection[]>([]);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedInsp, setSelectedInsp] = useState<Inspection | null>(null);
  const [activeTab, _setActiveTab] = useState<"inspections" | "actions">(inspState.activeTab);
  const setActiveTab = (t: "inspections" | "actions") => { _setActiveTab(t); updateInspections({ activeTab: t }); };
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const { currentUser } = useCurrentUser();

  const load = async () => {
    setLoading(true);
    const [iData, aData] = await Promise.all([
      fetch(`${API}/api/v1/inspections`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/v1/inspections/actions/list`).then(r => r.ok ? r.json() : []),
    ]);
    setInspections(iData);
    setActions(aData);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const doActionUpdate = async (actionId: string, endpoint: string, payload: any) => {
    try {
      const res = await fetch(`${API}/api/v1/inspections/actions/${actionId}/${endpoint}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) load();
    } catch { /* */ }
  };

  const pendingCount = actions.filter(a => a.status !== "verified").length;

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0f0f0f] min-h-screen">
      {selectedInsp && (
        <InspectionDetail insp={selectedInsp} onClose={() => setSelectedInsp(null)} onRefresh={() => { load(); setSelectedInsp(null); }} />
      )}
      {createOpen && <InspectionCreateModal onClose={() => setCreateOpen(false)} onSave={() => { load(); setCreateOpen(false); setToast({ msg: "Inspection scheduled", ok: true }); }} />}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#f9f9f9] flex items-center gap-3">
            <ClipboardCheck size={26} className="text-amber-500" />
            Inspections &amp; Action Items
          </h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Quality / HSE inspections, non-conformances, and CAPA action tracking
          </p>
        </div>
        {activeTab === "inspections" && (
          <button onClick={() => setCreateOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors">
            <Plus size={16} />New Inspection
          </button>
        )}
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{inspections.length}</p>
          <p className="text-xs text-[#6b7280]">Inspections</p>
        </div>
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-blue-400">{inspections.filter(i => i.status === "in_progress").length}</p>
          <p className="text-xs text-[#6b7280]">In Progress</p>
        </div>
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-red-400">{inspections.reduce((s, i) => s + (i.non_conformances?.length ?? 0), 0)}</p>
          <p className="text-xs text-[#6b7280]">Open NCs</p>
        </div>
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{pendingCount}</p>
          <p className="text-xs text-[#6b7280]">Pending Actions</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-5 border-b border-[#2a2a2a] pb-2">
        {(["inspections", "actions"] as const).map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={clsx(
              "px-4 py-1.5 text-sm font-medium rounded-t capitalize transition-colors",
              activeTab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]",
            )}>
            {t === "inspections" ? `Inspections (${inspections.length})` : `Action Items (${actions.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-[#6b7280] py-20">Loading…</div>
      ) : activeTab === "inspections" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {inspections.map(insp => (
            <InspectionCard key={insp.id} insp={insp} onSelect={() => setSelectedInsp(insp)} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {actions.map(a => (
            <ActionItemCard key={a.id} action={a}
              onComplete={() => doActionUpdate(a.id, "complete", { completed_by_id: currentUser?.id ?? "USR-002", completed_by_name: currentUser?.name ?? "Sarah Chen", completion_evidence: "Work completed per WO" })}
              onVerify={() => doActionUpdate(a.id, "verify", { verifier_id: currentUser?.id ?? "USR-003", verifier_name: currentUser?.name ?? "David Okonkwo", decision: "verified", comments: "Evidence reviewed and accepted" })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
