/**
 * AI Operations Brain — Safety Procedures Page
 * Full CRUD: create / edit (draft only) / delete procedures.
 * UX: search, status & type filters, modal forms, toast notifications.
 * Workflow: draft → peer_review → technical_review → final_approval → active → obsolete
 */
"use client";

import { useEffect, useState } from "react";
import {
  BookOpen, FileText, CheckCircle2, Clock, XCircle,
  AlertTriangle, Shield, X, User, Calendar,
  Plus, Search, Pencil, Trash2, Loader2, AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import { useCurrentUser } from "@/lib/user-context";
import { usePageState } from "@/lib/page-state";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Procedure {
  id: string; code: string; title: string; version: string;
  doc_type: string; category?: string; status: string; risk_level?: string;
  author_name?: string; authored_date?: string;
  peer_reviewer_name?: string; peer_review_decision?: string;
  tech_reviewer_name?: string; tech_review_decision?: string;
  approver_name?: string; approver_decision?: string;
  effective_date?: string; review_due_date?: string;
  steps: Record<string, unknown>[]; hazard_register: Record<string, unknown>[];
  ppe_requirements: string[]; references: string[]; tags: string[];
  audit_trail: Record<string, unknown>[]; created_at: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  draft:            "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  peer_review:      "text-blue-400 bg-blue-500/10 border-blue-500/30",
  technical_review: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  final_approval:   "text-purple-400 bg-purple-500/10 border-purple-500/30",
  active:           "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  obsolete:         "text-[#6b7280] bg-[#1a1a1a] border-[#2a2a2a]",
};

const STATUS_LABEL: Record<string, string> = {
  draft:            "Draft",
  peer_review:      "Peer Review",
  technical_review: "Tech Review",
  final_approval:   "Awaiting Approval",
  active:           "Active",
  obsolete:         "Obsolete",
};

const RISK_COLOR: Record<string, string> = {
  Critical: "text-red-400 bg-red-500/10 border-red-500/30",
  High:     "text-orange-400 bg-orange-500/10 border-orange-500/30",
  Medium:   "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Low:      "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

const DOC_TYPE_LABEL: Record<string, string> = {
  SOP: "Standard Operating Procedure", JSA: "Job Safety Analysis",
  SWMS: "Safe Work Method Statement",  MSDS: "Material Safety Data Sheet",
  ERP: "Emergency Response Plan",      Checklist: "Checklist",
  Work_Instruction: "Work Instruction",
};

const DOC_TYPES   = ["SOP", "JSA", "SWMS", "MSDS", "ERP", "Checklist", "Work_Instruction"];
const RISK_LEVELS = ["Critical", "High", "Medium", "Low"];

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
// Confirm Delete
// ─────────────────────────────────────────────────────────────────────────────

function ConfirmDialog({ label, onConfirm, onCancel, loading }: {
  label: string; onConfirm: () => void; onCancel: () => void; loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-6 w-full max-w-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <Trash2 size={18} className="text-red-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[#f9f9f9]">Confirm Delete</p>
            <p className="text-xs text-[#6b7280]">This action cannot be undone</p>
          </div>
        </div>
        <p className="text-sm text-[#a0a0a0] mb-5">Delete <span className="text-[#f9f9f9] font-medium">&ldquo;{label}&rdquo;</span>?</p>
        <div className="flex gap-2">
          <button onClick={onCancel} disabled={loading} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
          <button onClick={onConfirm} disabled={loading} className="flex-1 py-2 text-sm rounded-lg bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30 flex items-center justify-center gap-2">
            {loading && <Loader2 size={13} className="animate-spin" />}Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Form helpers
// ─────────────────────────────────────────────────────────────────────────────

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#a0a0a0] mb-1">{label}{required && <span className="text-red-400 ml-0.5">*</span>}</label>
      {children}
    </div>
  );
}

const inputCls  = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
const selectCls = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";

// ─────────────────────────────────────────────────────────────────────────────
// Procedure Create Modal
// ─────────────────────────────────────────────────────────────────────────────

function ProcedureCreateModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    code: "", title: "", version: "1.0", doc_type: "SOP", category: "",
    risk_level: "", author_name: "", ppe_requirements: "", tags: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.code.trim()) { setErr("Code is required"); return; }
    if (!form.title.trim()) { setErr("Title is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/procedures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: form.code.trim(), title: form.title.trim(),
          version: form.version || "1.0", doc_type: form.doc_type,
          category: form.category || undefined,
          risk_level: form.risk_level || undefined,
          author_name: form.author_name || undefined,
          ppe_requirements: form.ppe_requirements ? form.ppe_requirements.split(",").map(s => s.trim()).filter(Boolean) : [],
          tags: form.tags ? form.tags.split(",").map(s => s.trim()).filter(Boolean) : [],
        }),
      });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed to save"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">New Safety Procedure</p>
            <p className="text-xs text-[#6b7280]">Will be created in Draft status</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Code" required><input className={inputCls} value={form.code} onChange={e => set("code", e.target.value)} placeholder="SOP-CDU-001" /></Field>
            <Field label="Version"><input className={inputCls} value={form.version} onChange={e => set("version", e.target.value)} placeholder="1.0" /></Field>
          </div>
          <Field label="Title" required><input className={inputCls} value={form.title} onChange={e => set("title", e.target.value)} placeholder="Crude Distillation Unit Startup Procedure" /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Document Type">
              <select className={selectCls} value={form.doc_type} onChange={e => set("doc_type", e.target.value)}>
                {DOC_TYPES.map(t => <option key={t} value={t}>{t} — {DOC_TYPE_LABEL[t]}</option>)}
              </select>
            </Field>
            <Field label="Risk Level">
              <select className={selectCls} value={form.risk_level} onChange={e => set("risk_level", e.target.value)}>
                <option value="">— Select —</option>
                {RISK_LEVELS.map(r => <option key={r}>{r}</option>)}
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Category"><input className={inputCls} value={form.category} onChange={e => set("category", e.target.value)} placeholder="e.g. Startup / Shutdown" /></Field>
            <Field label="Author Name"><input className={inputCls} value={form.author_name} onChange={e => set("author_name", e.target.value)} placeholder="John Smith" /></Field>
          </div>
          <Field label="PPE Requirements (comma-separated)"><input className={inputCls} value={form.ppe_requirements} onChange={e => set("ppe_requirements", e.target.value)} placeholder="Hard Hat, Safety Glasses, Gloves" /></Field>
          <Field label="Tags (comma-separated)"><input className={inputCls} value={form.tags} onChange={e => set("tags", e.target.value)} placeholder="cdu, startup, rotating-equipment" /></Field>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}Create Procedure
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Procedure Edit Modal (draft only)
// ─────────────────────────────────────────────────────────────────────────────

function ProcedureEditModal({ proc, onClose, onSave }: { proc: Procedure; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    title: proc.title, category: proc.category ?? "",
    risk_level: proc.risk_level ?? "",
    ppe_requirements: (proc.ppe_requirements ?? []).join(", "),
    tags: (proc.tags ?? []).join(", "),
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setErr("Title is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/procedures/${proc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(),
          category: form.category || undefined,
          risk_level: form.risk_level || undefined,
          ppe_requirements: form.ppe_requirements ? form.ppe_requirements.split(",").map(s => s.trim()).filter(Boolean) : [],
          tags: form.tags ? form.tags.split(",").map(s => s.trim()).filter(Boolean) : [],
        }),
      });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed to save"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">Edit Procedure</p>
            <p className="text-xs text-[#6b7280]">{proc.code} v{proc.version} &mdash; Draft only</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <Field label="Title" required><input className={inputCls} value={form.title} onChange={e => set("title", e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Category"><input className={inputCls} value={form.category} onChange={e => set("category", e.target.value)} placeholder="e.g. Startup / Shutdown" /></Field>
            <Field label="Risk Level">
              <select className={selectCls} value={form.risk_level} onChange={e => set("risk_level", e.target.value)}>
                <option value="">— Select —</option>
                {RISK_LEVELS.map(r => <option key={r}>{r}</option>)}
              </select>
            </Field>
          </div>
          <Field label="PPE Requirements (comma-separated)"><input className={inputCls} value={form.ppe_requirements} onChange={e => set("ppe_requirements", e.target.value)} /></Field>
          <Field label="Tags (comma-separated)"><input className={inputCls} value={form.tags} onChange={e => set("tags", e.target.value)} /></Field>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared Pill
// ─────────────────────────────────────────────────────────────────────────────

function Pill({ label, cls }: { label: string; cls: string }) {
  return <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium", cls)}>{label}</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Approval Chain (inside detail drawer)
// ─────────────────────────────────────────────────────────────────────────────

function ApprovalChain({ proc }: { proc: Procedure }) {
  const steps = [
    { role: "Author",             name: proc.author_name,        decision: "submitted",              date: proc.authored_date },
    { role: "Peer Reviewer",      name: proc.peer_reviewer_name, decision: proc.peer_review_decision },
    { role: "Technical Reviewer", name: proc.tech_reviewer_name, decision: proc.tech_review_decision },
    { role: "Approver",           name: proc.approver_name,      decision: proc.approver_decision },
  ];
  return (
    <div className="space-y-1">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-3 py-1.5 border-b border-[#2a2a2a] last:border-0">
          <div className={clsx(
            "w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0",
            step.decision === "approved" || step.decision === "submitted" ? "bg-emerald-500/20 text-emerald-400" : step.decision === "rejected" ? "bg-red-500/20 text-red-400" : "bg-[#2a2a2a] text-[#6b7280]",
          )}>
            {step.decision === "approved" || step.decision === "submitted" ? <CheckCircle2 size={11} /> : step.decision === "rejected" ? <XCircle size={11} /> : <Clock size={11} />}
          </div>
          <div className="flex-1">
            <p className="text-xs font-medium text-[#a0a0a0]">{step.role}</p>
            <p className="text-xs text-[#6b7280]">{step.name || "—"}</p>
          </div>
          <span className={clsx("text-xs px-1.5 py-0.5 rounded",
            step.decision === "approved" || step.decision === "submitted" ? "text-emerald-400 bg-emerald-500/10" : step.decision === "rejected" ? "text-red-400 bg-red-500/10" : "text-[#6b7280] bg-[#2a2a2a]",
          )}>{step.decision || "Pending"}</span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Procedure Detail Drawer
// ─────────────────────────────────────────────────────────────────────────────

function ProcedureDetail({ proc, onClose, onRefresh }: { proc: Procedure; onClose: () => void; onRefresh: () => void }) {
  const [tab, setTab]         = useState<"overview" | "steps" | "hazards" | "audit">("overview");
  const [loading, setLoading] = useState(false);
  const [comments, setComments] = useState("");
  const { currentUser } = useCurrentUser();

  const doReview = async (endpoint: string, payload: Record<string, unknown>) => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/procedures/${proc.id}/${endpoint}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      if (!res.ok) { const e = await res.json(); alert(e.detail || "Action failed"); }
      else { onRefresh(); onClose(); }
    } catch { alert("Network error"); }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">{proc.title}</p>
            <p className="text-xs text-[#6b7280]">{proc.code} v{proc.version} &middot; {proc.doc_type}</p>
          </div>
          <div className="flex items-center gap-2">
            <Pill label={STATUS_LABEL[proc.status] ?? proc.status} cls={STATUS_COLOR[proc.status] ?? ""} />
            {proc.risk_level && <Pill label={proc.risk_level} cls={RISK_COLOR[proc.risk_level] ?? ""} />}
            <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={20} /></button>
          </div>
        </div>

        <div className="flex gap-1 px-6 pt-3 border-b border-[#2a2a2a]">
          {(["overview", "steps", "hazards", "audit"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx("px-3 py-1.5 text-xs rounded-t font-medium capitalize",
                tab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]")}>{t}</button>
          ))}
        </div>

        <div className="p-6 space-y-5">
          {tab === "overview" && (
            <>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><p className="text-xs text-[#6b7280]">Document Type</p><p className="text-[#a0a0a0]">{DOC_TYPE_LABEL[proc.doc_type] ?? proc.doc_type}</p></div>
                <div><p className="text-xs text-[#6b7280]">Category</p><p className="text-[#a0a0a0]">{proc.category || "—"}</p></div>
                {proc.effective_date && <div><p className="text-xs text-[#6b7280]">Effective</p><p className="text-[#a0a0a0]">{proc.effective_date}</p></div>}
                {proc.review_due_date && <div><p className="text-xs text-[#6b7280]">Review Due</p><p className="text-[#a0a0a0]">{proc.review_due_date}</p></div>}
              </div>
              {proc.ppe_requirements?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-[#f9f9f9] mb-2">PPE Requirements</p>
                  <div className="flex flex-wrap gap-1">
                    {proc.ppe_requirements.map((p, i) => <span key={i} className="text-xs px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20">{p}</span>)}
                  </div>
                </div>
              )}
              {proc.references?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-[#f9f9f9] mb-2">References</p>
                  <ul className="space-y-1">{proc.references.map((r, i) => <li key={i} className="text-xs text-[#a0a0a0]">&bull; {r}</li>)}</ul>
                </div>
              )}
              <div>
                <p className="text-xs font-semibold text-[#f9f9f9] mb-2">Approval Chain</p>
                <ApprovalChain proc={proc} />
              </div>
              {/* Workflow Actions */}
              {/* Acting-as user banner */}
              {currentUser && (
                <div className="flex items-center gap-2 bg-amber-500/5 border border-amber-500/20 rounded p-2">
                  <User size={12} className="text-amber-400 flex-shrink-0" />
                  <p className="text-xs text-amber-300">Acting as <span className="font-semibold">{currentUser.name}</span> ({currentUser.role.replace(/_/g,' ')})</p>
                </div>
              )}
              {proc.status === "draft" && (
                <button disabled={loading} onClick={() => {
                  const uid = currentUser?.id ?? "USR-001";
                  const uname = currentUser?.name ?? proc.author_name ?? "Author";
                  const params = new URLSearchParams({ user_id: uid, user_name: uname });
                  fetch(`${API}/api/v1/procedures/${proc.id}/submit?${params}`, { method: "POST" })
                    .then(() => { onRefresh(); onClose(); });
                }} className="w-full py-2 text-sm rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 hover:bg-blue-500/30">
                  Submit for Peer Review
                </button>
              )}
              {proc.status === "peer_review" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-blue-400">Peer Reviewer Action</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Comments…" className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={loading} onClick={() => doReview("peer-review", { reviewer_id: currentUser?.id ?? "USR-002", reviewer_name: currentUser?.name ?? "Sarah Chen", decision: "approved", comments })} className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approve</button>
                    <button disabled={loading} onClick={() => doReview("peer-review", { reviewer_id: currentUser?.id ?? "USR-002", reviewer_name: currentUser?.name ?? "Sarah Chen", decision: "rejected", comments })} className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Reject</button>
                  </div>
                </div>
              )}
              {proc.status === "technical_review" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-amber-400">Technical Reviewer Action</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Comments…" className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={loading} onClick={() => doReview("technical-review", { reviewer_id: currentUser?.id ?? "USR-005", reviewer_name: currentUser?.name ?? "Robert Halliday", decision: "approved", comments })} className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approve</button>
                    <button disabled={loading} onClick={() => doReview("technical-review", { reviewer_id: currentUser?.id ?? "USR-005", reviewer_name: currentUser?.name ?? "Robert Halliday", decision: "rejected", comments })} className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Reject</button>
                  </div>
                </div>
              )}
              {proc.status === "final_approval" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-purple-400">Final Approver Action</p>
                  <textarea value={comments} onChange={e => setComments(e.target.value)} placeholder="Comments…" className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={loading} onClick={() => doReview("approve", { approver_id: currentUser?.id ?? "USR-006", approver_name: currentUser?.name ?? "Linda Park", decision: "approved", comments, effective_date: new Date().toISOString().slice(0, 10) })} className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approve &amp; Activate</button>
                    <button disabled={loading} onClick={() => doReview("approve", { approver_id: currentUser?.id ?? "USR-006", approver_name: currentUser?.name ?? "Linda Park", decision: "rejected", comments })} className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">Reject</button>
                  </div>
                </div>
              )}
            </>
          )}
          {tab === "steps" && (
            <div className="space-y-3">
              {proc.steps?.length === 0 && <p className="text-xs text-[#6b7280]">No steps defined.</p>}
              {proc.steps?.map((step: Record<string, unknown>, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3">
                  <div className="flex items-start gap-3 mb-2">
                    <span className="text-sm font-bold text-amber-400 flex-shrink-0 w-6">{step.step_number as number}</span>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-[#f9f9f9]">{step.title as string}</p>
                      <p className="text-xs text-[#a0a0a0] mt-1">{step.description as string}</p>
                    </div>
                    <span className="text-xs text-[#6b7280] flex-shrink-0">{step.responsible_role as string}</span>
                  </div>
                  {(step.hazards as string[])?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {(step.hazards as string[]).map((h, j) => <span key={j} className="text-xs px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">{h}</span>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {tab === "hazards" && (
            <div className="space-y-3">
              {proc.hazard_register?.map((h: Record<string, unknown>, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{h.hazard as string}</p>
                    <div className="flex gap-1">
                      <Pill label={`Before: ${h.risk_before}`} cls={RISK_COLOR[h.risk_before as string] ?? ""} />
                      <Pill label={`After: ${h.risk_after}`}   cls={RISK_COLOR[h.risk_after as string] ?? ""} />
                    </div>
                  </div>
                  <p className="text-xs text-[#a0a0a0]">{h.control_measure as string}</p>
                </div>
              )) ?? <p className="text-xs text-[#6b7280]">No hazards registered.</p>}
            </div>
          )}
          {tab === "audit" && (
            <div>
              {proc.audit_trail?.map((entry: Record<string, unknown>, i) => (
                <div key={i} className="flex gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[#f9f9f9]">{(entry.action as string)?.replace(/_/g, " ")}</span>
                      <span className="text-xs text-[#6b7280]">by {entry.user as string}</span>
                    </div>
                    <p className="text-xs text-[#6b7280]">{entry.timestamp as string}</p>
                    {!!entry.comments && <p className="text-xs text-[#a0a0a0] italic">{entry.comments as string}</p>}
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
// Workflow Progress Bar
// ─────────────────────────────────────────────────────────────────────────────

const WORKFLOW_STEPS = ["draft", "peer_review", "technical_review", "final_approval", "active"];

function WorkflowBar({ status }: { status: string }) {
  const idx = WORKFLOW_STEPS.indexOf(status);
  return (
    <div className="flex items-center gap-0.5 mt-2">
      {WORKFLOW_STEPS.map((s, i) => (
        <div key={s} className={clsx(
          "h-1 flex-1 rounded-full transition-colors",
          i < idx ? "bg-emerald-500" : i === idx ? "bg-amber-500" : "bg-[#2a2a2a]",
        )} title={STATUS_LABEL[s]} />
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProceduresPage() {
  const { procedures: procState, updateProcedures } = usePageState();
  const [procs,   setProcs]   = useState<Procedure[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Procedure | null>(null);

  const [search, _setSearch] = useState(procState.search);
  const setSearch = (s: string) => { _setSearch(s); updateProcedures({ search: s }); };
  const [filterStatus, _setFilterStatus] = useState(procState.filterStatus);
  const setFilterStatus = (s: string) => { _setFilterStatus(s); updateProcedures({ filterStatus: s }); };
  const [filterType, _setFilterType] = useState(procState.filterType);
  const setFilterType = (s: string) => { _setFilterType(s); updateProcedures({ filterType: s }); };

  const [createOpen,   setCreateOpen]   = useState(false);
  const [editProc,     setEditProc]     = useState<Procedure | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Procedure | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const notify = (msg: string, ok = true) => setToast({ msg, ok });

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/api/v1/procedures`).then(r => r.ok ? r.json() : []);
    setProcs(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/procedures/${deleteTarget.id}`, { method: "DELETE" });
      if (res.ok || res.status === 204) { notify("Procedure deleted"); await load(); }
      else { notify("Delete failed", false); }
    } catch { notify("Network error", false); }
    setDeleteLoading(false);
    setDeleteTarget(null);
  };

  const filtered = procs.filter(p => {
    const q = search.toLowerCase();
    return (!q || p.title.toLowerCase().includes(q) || p.code.toLowerCase().includes(q) || (p.author_name ?? "").toLowerCase().includes(q))
      && (filterStatus === "all" || p.status === filterStatus)
      && (filterType   === "all" || p.doc_type === filterType);
  });

  const statusCounts: Record<string, number> = {};
  procs.forEach(p => { statusCounts[p.status] = (statusCounts[p.status] || 0) + 1; });

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0f0f0f] min-h-screen">
      {/* Overlays */}
      {selected && <ProcedureDetail proc={selected} onClose={() => setSelected(null)} onRefresh={() => { load(); setSelected(null); }} />}
      {createOpen && <ProcedureCreateModal onClose={() => setCreateOpen(false)} onSave={() => { load(); setCreateOpen(false); notify("Procedure created"); }} />}
      {editProc && <ProcedureEditModal proc={editProc} onClose={() => setEditProc(null)} onSave={() => { load(); setEditProc(null); notify("Procedure updated"); }} />}
      {deleteTarget && <ConfirmDialog label={deleteTarget.title} loading={deleteLoading} onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#f9f9f9] flex items-center gap-3">
            <BookOpen size={26} className="text-amber-500" />Safety Procedures
          </h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Controlled documents: SOPs, JSAs, SWMS, MSDs &mdash; Draft &rarr; Peer Review &rarr; Tech Review &rarr; Approval &rarr; Active
          </p>
        </div>
        <button onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors">
          <Plus size={16} />New Procedure
        </button>
      </div>

      {/* Status stat cards (clickable filter) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
        {Object.entries(STATUS_LABEL).map(([st, label]) => (
          <button key={st} onClick={() => setFilterStatus(filterStatus === st ? "all" : st)}
            className={clsx("p-3 rounded-lg border text-center transition-colors",
              filterStatus === st ? "border-amber-500 bg-amber-500/10" : "bg-[#1f1f1f] border-[#2a2a2a] hover:border-[#333]")}>
            <p className={clsx("text-xl font-bold", filterStatus === st ? "text-amber-400" : "text-[#f9f9f9]")}>{statusCounts[st] ?? 0}</p>
            <p className="text-xs text-[#6b7280] leading-tight">{label}</p>
          </button>
        ))}
      </div>

      {/* Toolbar: search + type filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7280]" />
          <input
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-9 pr-3 py-1.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50"
            placeholder="Search by title, code, author…"
            value={search} onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {["all", ...DOC_TYPES].map(t => (
            <button key={t} onClick={() => setFilterType(t)}
              className={clsx("px-3 py-1 text-xs rounded border font-medium transition-colors",
                filterType === t ? "border-amber-500/50 bg-amber-500/10 text-amber-400" : "border-[#2a2a2a] text-[#6b7280] hover:text-[#f9f9f9]")}>
              {t === "all" ? "All Types" : t}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-[#6b7280]">
          <Loader2 size={20} className="animate-spin mr-2" />Loading&hellip;
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <BookOpen size={40} className="text-[#333] mx-auto mb-3" />
          <p className="text-sm text-[#6b7280]">{search ? "No procedures match your search" : "No procedures yet"}</p>
          {!search && filterStatus === "all" && filterType === "all" && (
            <button onClick={() => setCreateOpen(true)} className="mt-3 text-sm text-amber-400 hover:underline">Create your first procedure &rarr;</button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(p => (
            <div key={p.id} className="group bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 hover:border-amber-500/40 transition-colors relative">
              {/* hover actions */}
              <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {p.status === "draft" && (
                  <button onClick={e => { e.stopPropagation(); setEditProc(p); }}
                    className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit (draft only)">
                    <Pencil size={13} />
                  </button>
                )}
                <button onClick={e => { e.stopPropagation(); setDeleteTarget(p); }}
                  className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
                  <Trash2 size={13} />
                </button>
              </div>

              {/* card body — click opens detail */}
              <div className="cursor-pointer pr-16" onClick={() => setSelected(p)}>
                <div className="flex items-start gap-2 mb-2">
                  <BookOpen size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[#f9f9f9] truncate">{p.title}</p>
                    <p className="text-xs text-[#6b7280]">{p.code} v{p.version}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <Pill label={STATUS_LABEL[p.status] ?? p.status} cls={STATUS_COLOR[p.status] ?? ""} />
                  <Pill label={p.doc_type} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
                  {p.risk_level && <Pill label={p.risk_level} cls={RISK_COLOR[p.risk_level] ?? ""} />}
                </div>
                {p.category && <p className="text-xs text-[#6b7280] mb-1">{p.category}</p>}
                <div className="flex items-center justify-between text-xs text-[#6b7280]">
                  <span className="flex items-center gap-1"><User size={11} />{p.author_name || "—"}</span>
                  <span>{p.steps?.length ?? 0} steps</span>
                </div>
                <WorkflowBar status={p.status} />
                {p.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {p.tags.slice(0, 3).map(t => <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-[#2a2a2a] text-[#6b7280]">{t}</span>)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
