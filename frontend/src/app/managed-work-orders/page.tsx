/**
 * AI Operations Brain — Managed Work Orders Page
 * Full approval workflow: Create → Submit → Approve → Schedule → Execute → Verify → Close
 * One person creates, a different person approves; a different person from completer verifies.
 */
"use client";

import { useEffect, useState } from "react";
import {
  Wrench, Plus, Clock, CheckCircle2, XCircle, User, Calendar,
  ChevronRight, AlertTriangle, X, Shield, Loader2, AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import { useCurrentUser } from "@/lib/user-context";
import { usePageState } from "@/lib/page-state";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

interface ManagedWO {
  id: string;
  wo_number: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  status: string;
  project_id?: string;
  plant_id?: string;
  equipment_ids: string[];
  permit_id?: string;
  scheduled_start?: string;
  scheduled_end?: string;
  actual_start?: string;
  estimated_hours?: number;
  actual_hours?: number;
  tasks: any[];
  materials: any[];
  safety_requirements: string[];
  created_by_name?: string;
  created_at: string;
  approver_name?: string;
  approval_decision?: string;
  approval_comments?: string;
  approval_date?: string;
  assigned_to: any[];
  started_by_name?: string;
  started_at?: string;
  completed_by_name?: string;
  completed_at?: string;
  completion_notes?: string;
  verified_by_name?: string;
  verification_decision?: string;
  verified_at?: string;
  audit_trail: any[];
}

const STATUS_COLOR: Record<string, string> = {
  draft:                 "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  submitted:             "text-blue-400 bg-blue-500/10 border-blue-500/30",
  pending_approval:      "text-amber-400 bg-amber-500/10 border-amber-500/30",
  approved:              "text-teal-400 bg-teal-500/10 border-teal-500/30",
  scheduled:             "text-purple-400 bg-purple-500/10 border-purple-500/30",
  in_progress:           "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  pending_verification:  "text-orange-400 bg-orange-500/10 border-orange-500/30",
  verified:              "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  closed:                "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  rejected:              "text-red-400 bg-red-500/10 border-red-500/30",
  cancelled:             "text-red-500/70 bg-[#2a2a2a] border-[#333]",
};

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-red-400 bg-red-500/10 border-red-500/30",
  high:     "text-orange-400 bg-orange-500/10 border-orange-500/30",
  medium:   "text-amber-400 bg-amber-500/10 border-amber-500/30",
  low:      "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

const WORKFLOW_STEPS = [
  "draft", "submitted", "approved", "scheduled", "in_progress", "pending_verification", "verified", "closed"
];

function Pill({ label, cls }: { label: string; cls: string }) {
  return <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium capitalize", cls)}>{label.replace(/_/g, " ")}</span>;
}

function WorkflowBar({ status }: { status: string }) {
  const idx = WORKFLOW_STEPS.indexOf(status);
  return (
    <div className="flex items-center mt-2">
      {WORKFLOW_STEPS.map((step, i) => {
        const done = i < idx;
        const current = i === idx;
        return (
          <div key={step} className="flex items-center flex-1 min-w-0">
            <div className={clsx("h-1 flex-1", done ? "bg-emerald-500" : current ? "bg-amber-500" : "bg-[#2a2a2a]")} />
            {i < WORKFLOW_STEPS.length - 1 && (
              <div className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0", done ? "bg-emerald-500" : current ? "bg-amber-500" : "bg-[#333]")} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function WOCard({ wo, onSelect }: { wo: ManagedWO; onSelect: () => void }) {
  const doneCount = wo.tasks?.filter(t => t.status === "completed").length ?? 0;
  const totalCount = wo.tasks?.length ?? 0;
  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 cursor-pointer hover:border-amber-500/40 transition-colors"
      onClick={onSelect}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] truncate">{wo.title}</p>
          <p className="text-xs text-[#6b7280]">{wo.wo_number}</p>
        </div>
        <Pill label={wo.status} cls={STATUS_COLOR[wo.status] ?? ""} />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <Pill label={wo.category} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
        <Pill label={wo.priority} cls={PRIORITY_COLOR[wo.priority] ?? ""} />
      </div>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className="text-sm font-bold text-[#f9f9f9]">{totalCount}</p>
          <p className="text-xs text-[#6b7280]">Tasks</p>
        </div>
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className="text-sm font-bold text-emerald-400">{doneCount}</p>
          <p className="text-xs text-[#6b7280]">Done</p>
        </div>
        <div className="bg-[#242424] rounded p-2 text-center">
          <p className="text-sm font-bold text-amber-400">{wo.estimated_hours ?? "—"}h</p>
          <p className="text-xs text-[#6b7280]">Est.</p>
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-[#6b7280]">
        {wo.created_by_name && <span className="flex items-center gap-1"><User size={11} />{wo.created_by_name}</span>}
        {wo.scheduled_start && <span className="flex items-center gap-1"><Calendar size={11} />{wo.scheduled_start.slice(0, 10)}</span>}
      </div>
      <WorkflowBar status={wo.status} />
    </div>
  );
}

function WODetail({ wo, onClose, onRefresh }: { wo: ManagedWO; onClose: () => void; onRefresh: () => void }) {
  const [tab, setTab] = useState<"tasks" | "approval" | "audit">("approval");
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState("");
  const { currentUser } = useCurrentUser();

  const doAction = async (endpoint: string, payload: any, asParams = false) => {
    setLoading(true);
    try {
      let url = `${API}/api/v1/work-orders/${wo.id}/${endpoint}`;
      const opts: RequestInit = asParams
        ? { method: "POST" }
        : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
      if (asParams) url += "?" + new URLSearchParams(payload).toString();
      const res = await fetch(url, opts);
      if (!res.ok) { const e = await res.json(); alert(e.detail); }
      else { onRefresh(); onClose(); }
    } catch { alert("Network error"); }
    setLoading(false);
  };

  const taskStatusColor = (s: string) =>
    s === "completed" ? "text-emerald-400" : s === "in_progress" ? "text-amber-400" : "text-[#6b7280]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">{wo.title}</p>
            <p className="text-xs text-[#6b7280]">{wo.wo_number} · {wo.category}</p>
          </div>
          <div className="flex items-center gap-2">
            <Pill label={wo.status} cls={STATUS_COLOR[wo.status] ?? ""} />
            <Pill label={wo.priority} cls={PRIORITY_COLOR[wo.priority] ?? ""} />
            <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={20} /></button>
          </div>
        </div>

        <div className="px-6 pt-2"><WorkflowBar status={wo.status} /></div>

        <div className="flex gap-1 px-6 pt-3 border-b border-[#2a2a2a]">
          {(["approval", "tasks", "audit"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx("px-3 py-1.5 text-xs rounded-t font-medium capitalize",
                tab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]"
              )}>
              {t}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === "approval" && (
            <div className="space-y-4">
              <p className="text-xs text-[#a0a0a0]">{wo.description}</p>

              {wo.equipment_ids?.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {wo.equipment_ids.map(e => (
                    <span key={e} className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">{e}</span>
                  ))}
                </div>
              )}

              {wo.safety_requirements?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-[#f9f9f9] mb-1 flex items-center gap-1"><Shield size={12} className="text-orange-400" />Safety Requirements</p>
                  <ul className="space-y-1">{wo.safety_requirements.map((r, i) => <li key={i} className="text-xs text-[#a0a0a0]">• {r}</li>)}</ul>
                </div>
              )}

              {/* Two-person approval summary */}
              <div>
                <p className="text-xs font-semibold text-[#f9f9f9] mb-2">Approval Chain (two-person rule enforced)</p>
                {[
                  { role: "Creator", name: wo.created_by_name, status: "created", date: wo.created_at },
                  { role: "Approver (≠ Creator)", name: wo.approver_name, status: wo.approval_decision, date: wo.approval_date },
                  { role: "Assignee (technician)", name: wo.assigned_to?.map(a => a.name).join(", "), status: wo.started_at ? "started" : "pending" },
                  { role: "Completer", name: wo.completed_by_name, status: wo.completed_at ? "completed" : "pending", date: wo.completed_at },
                  { role: "Verifier (≠ Completer)", name: wo.verified_by_name, status: wo.verification_decision, date: wo.verified_at },
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-3 py-1.5 border-b border-[#2a2a2a] last:border-0">
                    <div className={clsx("w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0",
                      step.status === "approved" || step.status === "created" || step.status === "passed" || step.status === "completed" || step.status === "started" ? "bg-emerald-500/20 text-emerald-400"
                        : step.status === "rejected" || step.status === "failed" ? "bg-red-500/20 text-red-400"
                        : "bg-[#2a2a2a] text-[#6b7280]"
                    )}>
                      {step.status === "approved" || step.status === "created" || step.status === "passed" || step.status === "completed" || step.status === "started" ? <CheckCircle2 size={11} />
                        : step.status === "rejected" ? <XCircle size={11} /> : <Clock size={11} />}
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-[#a0a0a0]">{step.role}</p>
                      <p className="text-xs text-[#6b7280]">{step.name || "—"}</p>
                    </div>
                    <span className={clsx("text-xs px-1.5 py-0.5 rounded",
                      step.status === "approved" || step.status === "created" || step.status === "passed" || step.status === "completed" || step.status === "started" ? "text-emerald-400 bg-emerald-500/10"
                        : step.status === "rejected" ? "text-red-400 bg-red-500/10" : "text-[#6b7280] bg-[#2a2a2a]"
                    )}>
                      {step.status || "Pending"}
                    </span>
                  </div>
                ))}
              </div>

              {wo.approval_comments && (
                <div className="bg-[#242424] rounded p-3">
                  <p className="text-xs text-[#6b7280]">Approval comments</p>
                  <p className="text-xs text-[#a0a0a0]">{wo.approval_comments}</p>
                </div>
              )}

              {/* Action buttons */}
              {wo.status === "draft" && (
                <button disabled={loading} onClick={() => doAction("submit", { user_id: currentUser?.id ?? wo.created_by_name ?? "USR-001", user_name: currentUser?.name ?? wo.created_by_name ?? "Creator" }, true)}
                  className="w-full py-2 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30">
                  Submit for Approval
                </button>
              )}
              {(wo.status === "submitted" || wo.status === "pending_approval") && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-amber-400">Supervisor Approval (must differ from creator)</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Approval comments…"
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={loading} onClick={() => doAction("approve", { approver_id: currentUser?.id ?? "USR-002", approver_name: currentUser?.name ?? "Sarah Chen", decision: "approved", comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approve</button>
                    <button disabled={loading} onClick={() => doAction("approve", { approver_id: currentUser?.id ?? "USR-002", approver_name: currentUser?.name ?? "Sarah Chen", decision: "rejected", comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Reject</button>
                  </div>
                </div>
              )}
              {wo.status === "approved" && (
                <button disabled={loading} onClick={() => doAction("assign", { assigned_to: [{ id: currentUser?.id ?? "USR-001", name: currentUser?.name ?? "James Mitchell", role: currentUser?.role ?? "Technician" }], scheduled_start: wo.scheduled_start })}
                  className="w-full py-2 text-sm rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 hover:bg-purple-500/30">
                  Assign & Schedule
                </button>
              )}
              {wo.status === "scheduled" && (
                <button disabled={loading} onClick={() => doAction("start", { started_by_id: currentUser?.id ?? "USR-001", started_by_name: currentUser?.name ?? "James Mitchell" })}
                  className="w-full py-2 text-sm rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30">
                  Start Work
                </button>
              )}
              {wo.status === "in_progress" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-emerald-400">Complete Work</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Completion notes…"
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <button disabled={loading} onClick={() => doAction("complete", { completed_by_id: currentUser?.id ?? "USR-001", completed_by_name: currentUser?.name ?? "James Mitchell", completion_notes: comments })}
                    className="w-full py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Mark Complete</button>
                </div>
              )}
              {wo.status === "pending_verification" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-orange-400">Supervisor Verification (must differ from completer)</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Verification comments…"
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={loading} onClick={() => doAction("verify", { verified_by_id: currentUser?.id ?? "USR-002", verified_by_name: currentUser?.name ?? "Sarah Chen", decision: "passed", comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Verify — Passed</button>
                    <button disabled={loading} onClick={() => doAction("verify", { verified_by_id: currentUser?.id ?? "USR-002", verified_by_name: currentUser?.name ?? "Sarah Chen", decision: "failed", comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Fail — Return to Work</button>
                  </div>
                </div>
              )}
              {wo.status === "verified" && (
                <button disabled={loading} onClick={() => doAction("close", { user_id: currentUser?.id ?? "USR-002", user_name: currentUser?.name ?? "Sarah Chen" }, true)}
                  className="w-full py-2 text-sm rounded bg-[#2a2a2a] text-[#a0a0a0] border border-[#333] hover:text-[#f9f9f9]">
                  Close Work Order
                </button>
              )}
            </div>
          )}

          {tab === "tasks" && (
            <div className="space-y-2">
              {wo.tasks?.map((task, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3 flex items-start gap-3">
                  <span className="text-xs font-bold text-amber-400 flex-shrink-0 w-6">{task.seq}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{task.title}</p>
                    {task.description && <p className="text-xs text-[#a0a0a0] mt-0.5">{task.description}</p>}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-[#6b7280]">{task.trade}</span>
                      <span className="text-xs text-[#6b7280]">{task.estimated_hours}h</span>
                    </div>
                    {task.notes && <p className="text-xs text-emerald-400 mt-1">{task.notes}</p>}
                  </div>
                  <span className={clsx("text-xs font-medium flex-shrink-0 capitalize", taskStatusColor(task.status))}>
                    {task.status}
                  </span>
                </div>
              ))}
              {wo.materials?.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs font-semibold text-[#f9f9f9] mb-2">Materials</p>
                  {wo.materials.map((m, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 border-b border-[#2a2a2a] last:border-0 text-sm">
                      <span className="text-[#a0a0a0] text-xs">{m.description}</span>
                      <span className="text-xs text-[#6b7280]">{m.qty_issued}/{m.qty_required} {m.unit}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "audit" && (
            <div>
              {wo.audit_trail?.map((entry, i) => (
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
// MWO Create Modal
// ─────────────────────────────────────────────────────────────────────────────

const WO_CATEGORIES = ["corrective","preventive","predictive","emergency","project","inspection"];
const WO_PRIORITIES  = ["critical","high","medium","low"];

const mInp = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
const mSel = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";
function MFL({ label, req, children }: { label: string; req?: boolean; children: React.ReactNode }) {
  return <div><label className="block text-xs font-medium text-[#a0a0a0] mb-1">{label}{req && <span className="text-red-400 ml-0.5">*</span>}</label>{children}</div>;
}

function MWOCreateModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    title: "", description: "", category: "corrective", priority: "medium",
    scheduled_start: "", scheduled_end: "", estimated_hours: "",
    created_by_name: "", safety_requirements: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const s = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setErr("Title is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/work-orders`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(), description: form.description || "",
          category: form.category, priority: form.priority,
          scheduled_start: form.scheduled_start || undefined,
          scheduled_end: form.scheduled_end || undefined,
          estimated_hours: form.estimated_hours ? parseFloat(form.estimated_hours) : undefined,
          created_by_name: form.created_by_name || undefined,
          safety_requirements: form.safety_requirements
            ? form.safety_requirements.split(",").map(s => s.trim()).filter(Boolean)
            : [],
        }),
      });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  const priorityColor: Record<string, string> = {
    critical: "text-red-400", high: "text-orange-400", medium: "text-amber-400", low: "text-emerald-400",
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">New Work Order</p>
            <p className="text-xs text-[#6b7280]">Creates in Draft — submit for supervisor approval</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <MFL label="Title" req><input className={mInp} value={form.title} onChange={e => s("title", e.target.value)} placeholder="Replace pump mechanical seal on P-101" /></MFL>
          <MFL label="Description">
            <textarea className={mInp + " resize-none h-20"} value={form.description} onChange={e => s("description", e.target.value)} placeholder="Detailed work description…" />
          </MFL>
          <div className="grid grid-cols-2 gap-4">
            <MFL label="Category">
              <select className={mSel} value={form.category} onChange={e => s("category", e.target.value)}>
                {WO_CATEGORIES.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
            </MFL>
            <MFL label="Priority">
              <select className={mSel} value={form.priority} onChange={e => s("priority", e.target.value)}>
                {WO_PRIORITIES.map(p => <option key={p} value={p} className={priorityColor[p]}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}
              </select>
            </MFL>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <MFL label="Scheduled Start"><input type="date" className={mInp} value={form.scheduled_start} onChange={e => s("scheduled_start", e.target.value)} /></MFL>
            <MFL label="Scheduled End"><input type="date" className={mInp} value={form.scheduled_end} onChange={e => s("scheduled_end", e.target.value)} /></MFL>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <MFL label="Estimated Hours"><input type="number" min="0" step="0.5" className={mInp} value={form.estimated_hours} onChange={e => s("estimated_hours", e.target.value)} placeholder="8" /></MFL>
            <MFL label="Created By"><input className={mInp} value={form.created_by_name} onChange={e => s("created_by_name", e.target.value)} placeholder="John Smith" /></MFL>
          </div>
          <MFL label="Safety Requirements (comma-separated)">
            <input className={mInp} value={form.safety_requirements} onChange={e => s("safety_requirements", e.target.value)} placeholder="Lockout/Tagout, PPE, Hot Work Permit" />
          </MFL>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}Create Work Order
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ManagedWorkOrdersPage() {
  const { managedWorkOrders: mwoState, updateManagedWorkOrders } = usePageState();
  const [wos, setWos] = useState<ManagedWO[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ManagedWO | null>(null);
  const [filterStatus, _setFilterStatus] = useState(mwoState.filterStatus);
  const setFilterStatus = (s: string) => { _setFilterStatus(s); updateManagedWorkOrders({ filterStatus: s }); };
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/api/v1/work-orders`).then(r => r.ok ? r.json() : []);
    setWos(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = filterStatus === "all" ? wos : wos.filter(w => w.status === filterStatus);
  const statusCounts: Record<string, number> = {};
  wos.forEach(w => { statusCounts[w.status] = (statusCounts[w.status] || 0) + 1; });

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0f0f0f] min-h-screen">
      {selected && <WODetail wo={selected} onClose={() => setSelected(null)} onRefresh={() => { load(); setSelected(null); }} />}
      {createOpen && <MWOCreateModal onClose={() => setCreateOpen(false)} onSave={() => { load(); setCreateOpen(false); setToast({ msg: "Work order created", ok: true }); }} />}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#f9f9f9] flex items-center gap-3">
            <Wrench size={26} className="text-amber-500" />
            Managed Work Orders
          </h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Full approval workflow with two-person rule: Creator → Approver → Execute → Verify → Close
          </p>
        </div>
        <button onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors">
          <Plus size={16} />New Work Order
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        {[
          { label: "Total", value: wos.length, color: "text-[#f9f9f9]" },
          { label: "In Progress", value: statusCounts.in_progress ?? 0, color: "text-emerald-400" },
          { label: "Pending Approval", value: (statusCounts.submitted ?? 0) + (statusCounts.pending_approval ?? 0), color: "text-amber-400" },
          { label: "Pending Verification", value: statusCounts.pending_verification ?? 0, color: "text-orange-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
            <p className={clsx("text-2xl font-bold", color)}>{value}</p>
            <p className="text-xs text-[#6b7280]">{label}</p>
          </div>
        ))}
      </div>

      {/* Status filter */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button onClick={() => setFilterStatus("all")}
          className={clsx("px-3 py-1 text-xs rounded border font-medium",
            filterStatus === "all" ? "border-amber-500 bg-amber-500/10 text-amber-400" : "border-[#2a2a2a] text-[#6b7280]")}>
          All ({wos.length})
        </button>
        {Object.entries(statusCounts).map(([st, cnt]) => (
          <button key={st} onClick={() => setFilterStatus(filterStatus === st ? "all" : st)}
            className={clsx("px-3 py-1 text-xs rounded border font-medium",
              filterStatus === st ? "border-amber-500 bg-amber-500/10 text-amber-400" : (STATUS_COLOR[st] ?? "border-[#2a2a2a] text-[#6b7280]"))}>
            {st.replace(/_/g, " ")} ({cnt})
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-[#6b7280] py-20">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(w => <WOCard key={w.id} wo={w} onSelect={() => setSelected(w)} />)}
        </div>
      )}
    </div>
  );
}
