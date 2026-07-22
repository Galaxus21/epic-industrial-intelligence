/**
 * AI Operations Brain — Permit to Work (PTW) Page
 * Lists all permits with full workflow status.
 * Supports approval actions inline: Area Authority, Safety Officer, AP issue/close.
 */
"use client";

import { useEffect, useState } from "react";
import {
  ShieldAlert, Plus, ChevronRight, Clock, CheckCircle2, XCircle,
  AlertTriangle, Flame, Zap, Wind, Eye, X, FileText, User,
  ChevronDown, ChevronUp, ClipboardCheck, Loader2, AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import { useCurrentUser } from "@/lib/user-context";
import { usePageState } from "@/lib/page-state";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

type PTWStatus =
  | "draft" | "submitted" | "area_authority_review" | "safety_review"
  | "ap_approval" | "issued" | "active" | "suspended"
  | "completion_requested" | "closed" | "cancelled";

interface PTW {
  id: string;
  permit_number: string;
  permit_type: string;
  title: string;
  scope_of_work: string;
  status: PTWStatus;
  plant_id?: string;
  equipment_ids: string[];
  location_description?: string;
  area_classification?: string;
  planned_start?: string;
  planned_end?: string;
  originator_name?: string;
  originator_date?: string;
  area_authority_name?: string;
  area_authority_decision?: string;
  safety_officer_name?: string;
  safety_officer_decision?: string;
  ap_name?: string;
  ap_decision?: string;
  hazards: any[];
  ppe_requirements: any[];
  isolation_points: any[];
  gas_tests: any[];
  audit_trail: any[];
  created_at: string;
}

const STATUS_STEPS: PTWStatus[] = [
  "draft", "submitted", "area_authority_review", "safety_review",
  "ap_approval", "issued", "active", "suspended",
  "completion_requested", "closed",
];

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  area_authority_review: "AA Review",
  safety_review: "Safety Review",
  ap_approval: "AP Approval",
  issued: "Issued",
  active: "Active",
  suspended: "Suspended",
  completion_requested: "Closure Req.",
  closed: "Closed",
  cancelled: "Cancelled",
};

const STATUS_COLOR: Record<string, string> = {
  draft:                   "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  submitted:               "text-blue-400 bg-blue-500/10 border-blue-500/30",
  area_authority_review:   "text-amber-400 bg-amber-500/10 border-amber-500/30",
  safety_review:           "text-orange-400 bg-orange-500/10 border-orange-500/30",
  ap_approval:             "text-purple-400 bg-purple-500/10 border-purple-500/30",
  issued:                  "text-teal-400 bg-teal-500/10 border-teal-500/30",
  active:                  "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  suspended:               "text-red-400 bg-red-500/10 border-red-500/30",
  completion_requested:    "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
  closed:                  "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  cancelled:               "text-red-500 bg-red-500/10 border-red-500/20",
};

const TYPE_ICON: Record<string, any> = {
  hot_work:             Flame,
  electrical_isolation: Zap,
  confined_space:       Wind,
  cold_work:            ClipboardCheck,
  height:               AlertTriangle,
  radiography:          Eye,
  excavation:           AlertTriangle,
  general:              FileText,
};

const TYPE_LABEL: Record<string, string> = {
  hot_work:             "Hot Work",
  electrical_isolation: "Electrical Isolation",
  confined_space:       "Confined Space",
  cold_work:            "Cold Work",
  height:               "Work at Height",
  radiography:          "Radiography",
  excavation:           "Excavation",
  general:              "General",
};

function Pill({ label, cls }: { label: string; cls: string }) {
  return <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium", cls)}>{label}</span>;
}

function WorkflowBar({ status }: { status: string }) {
  const activeSteps: PTWStatus[] = [
    "draft", "submitted", "area_authority_review", "safety_review",
    "ap_approval", "issued", "active", "closed",
  ];
  const idx = activeSteps.indexOf(status as PTWStatus);
  return (
    <div className="flex items-center gap-0 mt-3">
      {activeSteps.map((step, i) => {
        const done = i < idx;
        const current = i === idx;
        const cancelled = status === "cancelled" || status === "suspended";
        return (
          <div key={step} className="flex items-center flex-1 min-w-0">
            <div className={clsx(
              "h-1.5 flex-1 rounded-full",
              done ? "bg-emerald-500" : current && !cancelled ? "bg-amber-500" : "bg-[#2a2a2a]",
            )} />
            {i < activeSteps.length - 1 && (
              <div className={clsx(
                "w-2 h-2 rounded-full flex-shrink-0 mx-0.5",
                done ? "bg-emerald-500" : current ? "bg-amber-500" : "bg-[#333]",
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function PTWCard({ ptw, onSelect }: { ptw: PTW; onSelect: () => void }) {
  const TypeIcon = TYPE_ICON[ptw.permit_type] ?? FileText;
  const typeColor = ptw.permit_type === "hot_work" ? "text-red-400" :
    ptw.permit_type === "electrical_isolation" ? "text-yellow-400" :
    ptw.permit_type === "confined_space" ? "text-blue-400" : "text-amber-400";
  return (
    <div
      className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 cursor-pointer hover:border-amber-500/40 transition-colors"
      onClick={onSelect}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <TypeIcon size={16} className={clsx("flex-shrink-0", typeColor)} />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[#f9f9f9] truncate">{ptw.title}</p>
            <p className="text-xs text-[#6b7280]">{ptw.permit_number}</p>
          </div>
        </div>
        <Pill label={STATUS_LABEL[ptw.status] ?? ptw.status} cls={STATUS_COLOR[ptw.status] ?? ""} />
      </div>

      <div className="flex items-center gap-3 text-xs text-[#6b7280] mb-2">
        <Pill label={TYPE_LABEL[ptw.permit_type] ?? ptw.permit_type}
          cls={clsx("border", typeColor, "bg-transparent")} />
        {ptw.location_description && <span className="truncate">{ptw.location_description}</span>}
      </div>

      {ptw.equipment_ids?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {ptw.equipment_ids.slice(0, 3).map(e => (
            <span key={e} className="text-xs px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">{e}</span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 text-xs text-[#6b7280]">
        {ptw.originator_name && <span className="flex items-center gap-1"><User size={11} />{ptw.originator_name}</span>}
        {ptw.planned_start && <span className="flex items-center gap-1"><Clock size={11} />{ptw.planned_start.slice(0, 10)}</span>}
      </div>

      <WorkflowBar status={ptw.status} />
    </div>
  );
}

function AuditStep({ entry }: { entry: any }) {
  return (
    <div className="flex gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
      <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-[#f9f9f9]">{entry.action.replace(/_/g, " ")}</span>
          <span className="text-xs text-[#6b7280]">by {entry.user}</span>
        </div>
        <p className="text-xs text-[#6b7280]">{new Date(entry.timestamp).toLocaleString()}</p>
        {entry.comments && <p className="text-xs text-[#a0a0a0] mt-0.5 italic">{entry.comments}</p>}
      </div>
    </div>
  );
}

function PTWDetail({ ptw, onClose, onRefresh }: { ptw: PTW; onClose: () => void; onRefresh: () => void }) {
  const [tab, setTab] = useState<"overview" | "hazards" | "isolation" | "gas" | "audit">("overview");
  const [actionLoading, setActionLoading] = useState(false);
  const { currentUser } = useCurrentUser();
  const [form, setForm] = useState({ decision: "approved", comments: "" });

  const doAction = async (endpoint: string, payload: any) => {
    setActionLoading(true);
    const params = new URLSearchParams(payload).toString();
    const url = `${API}/api/v1/permits/${ptw.id}/${endpoint}`;
    try {
      const res = await fetch(`${url}?${params}`, { method: "POST" });
      if (!res.ok) { const e = await res.json(); alert(e.detail || "Action failed"); }
      else { onRefresh(); onClose(); }
    } catch (e) { alert("Network error"); }
    setActionLoading(false);
  };

  const doBodyAction = async (endpoint: string, payload: any) => {
    setActionLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/permits/${ptw.id}/${endpoint}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const e = await res.json(); alert(e.detail || "Action failed"); }
      else { onRefresh(); onClose(); }
    } catch (e) { alert("Network error"); }
    setActionLoading(false);
  };

  const TypeIcon = TYPE_ICON[ptw.permit_type] ?? FileText;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-3xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <TypeIcon size={20} className="text-amber-400" />
            <div>
              <p className="text-base font-bold text-[#f9f9f9]">{ptw.title}</p>
              <p className="text-xs text-[#6b7280]">{ptw.permit_number} · {TYPE_LABEL[ptw.permit_type]}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Pill label={STATUS_LABEL[ptw.status]} cls={STATUS_COLOR[ptw.status] ?? ""} />
            <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={20} /></button>
          </div>
        </div>

        <div className="px-6 pt-2">
          <WorkflowBar status={ptw.status} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 px-6 pt-3 border-b border-[#2a2a2a]">
          {(["overview", "hazards", "isolation", "gas", "audit"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={clsx(
                "px-3 py-1.5 text-xs rounded-t font-medium capitalize",
                tab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]",
              )}>
              {t}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === "overview" && (
            <div className="space-y-4">
              <div>
                <p className="text-xs text-[#6b7280] mb-1">Scope of Work</p>
                <p className="text-sm text-[#a0a0a0]">{ptw.scope_of_work || "—"}</p>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs text-[#6b7280]">Location</p><p className="text-[#f9f9f9]">{ptw.location_description || "—"}</p></div>
                <div><p className="text-xs text-[#6b7280]">Area Classification</p><p className="text-[#f9f9f9]">{ptw.area_classification || "—"}</p></div>
                <div><p className="text-xs text-[#6b7280]">Planned Start</p><p className="text-[#f9f9f9]">{ptw.planned_start?.slice(0, 16) || "—"}</p></div>
                <div><p className="text-xs text-[#6b7280]">Planned End</p><p className="text-[#f9f9f9]">{ptw.planned_end?.slice(0, 16) || "—"}</p></div>
              </div>

              {/* Approval chain */}
              <div>
                <p className="text-xs font-semibold text-[#f9f9f9] mb-2">Approval Chain</p>
                {[
                  { role: "Originator", name: ptw.originator_name, decision: "submitted", date: ptw.originator_date },
                  { role: "Area Authority", name: ptw.area_authority_name, decision: ptw.area_authority_decision, date: undefined },
                  { role: "Safety Officer", name: ptw.safety_officer_name, decision: ptw.safety_officer_decision, date: undefined },
                  { role: "Authorized Person", name: ptw.ap_name, decision: ptw.ap_decision, date: undefined },
                ].map((step, i) => (
                  <div key={i} className="flex items-center gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
                    <div className={clsx(
                      "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0",
                      step.decision === "approved" || step.decision === "issued" || step.decision === "submitted"
                        ? "bg-emerald-500/20 text-emerald-400"
                        : step.decision === "rejected"
                        ? "bg-red-500/20 text-red-400"
                        : "bg-[#2a2a2a] text-[#6b7280]",
                    )}>
                      {step.decision === "approved" || step.decision === "issued" || step.decision === "submitted"
                        ? <CheckCircle2 size={12} />
                        : step.decision === "rejected"
                        ? <XCircle size={12} />
                        : <Clock size={12} />}
                    </div>
                    <div className="flex-1">
                      <p className="text-xs font-medium text-[#f9f9f9]">{step.role}</p>
                      <p className="text-xs text-[#6b7280]">{step.name || "Awaiting assignment"}</p>
                    </div>
                    <span className={clsx(
                      "text-xs px-1.5 py-0.5 rounded",
                      step.decision === "approved" || step.decision === "issued" || step.decision === "submitted"
                        ? "text-emerald-400 bg-emerald-500/10"
                        : step.decision === "rejected" ? "text-red-400 bg-red-500/10" : "text-[#6b7280] bg-[#2a2a2a]",
                    )}>
                      {step.decision || "Pending"}
                    </span>
                  </div>
                ))}
              </div>

              {/* Available actions */}
              {ptw.status === "submitted" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-amber-400">Area Authority Action</p>
                  <textarea
                    placeholder="Comments…"
                    value={form.comments}
                    onChange={e => setForm(f => ({ ...f, comments: e.target.value }))}
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16"
                  />
                  <div className="flex gap-2">
                    <button disabled={actionLoading} onClick={() => doBodyAction("area-authority-review", { user_id: currentUser?.id ?? "USR-004", user_name: currentUser?.name ?? "Maria Santos", decision: "approved", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30">
                      Approve (Area Authority)
                    </button>
                    <button disabled={actionLoading} onClick={() => doBodyAction("area-authority-review", { user_id: currentUser?.id ?? "USR-004", user_name: currentUser?.name ?? "Maria Santos", decision: "rejected", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30">
                      Reject
                    </button>
                  </div>
                </div>
              )}
              {ptw.status === "area_authority_review" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-orange-400">Safety Officer Action</p>
                  <textarea placeholder="Comments…" value={form.comments} onChange={e => setForm(f => ({ ...f, comments: e.target.value }))}
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={actionLoading} onClick={() => doBodyAction("safety-review", { user_id: currentUser?.id ?? "USR-003", user_name: currentUser?.name ?? "David Okonkwo", decision: "approved", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30">
                      Approve (Safety)
                    </button>
                    <button disabled={actionLoading} onClick={() => doBodyAction("safety-review", { user_id: currentUser?.id ?? "USR-003", user_name: currentUser?.name ?? "David Okonkwo", decision: "rejected", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30">
                      Reject
                    </button>
                  </div>
                </div>
              )}
              {ptw.status === "safety_review" && (
                <div className="bg-[#242424] rounded-lg p-4 space-y-3">
                  <p className="text-xs font-semibold text-purple-400">Authorized Person Action</p>
                  <textarea placeholder="Comments…" value={form.comments} onChange={e => setForm(f => ({ ...f, comments: e.target.value }))}
                    className="w-full bg-[#1a1a1a] border border-[#333] rounded p-2 text-xs text-[#f9f9f9] resize-none h-16" />
                  <div className="flex gap-2">
                    <button disabled={actionLoading} onClick={() => doBodyAction("ap-approval", { user_id: currentUser?.id ?? "USR-005", user_name: currentUser?.name ?? "Robert Halliday", decision: "issued", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-teal-500/20 text-teal-400 border border-teal-500/30 hover:bg-teal-500/30">
                      Issue Permit (AP)
                    </button>
                    <button disabled={actionLoading} onClick={() => doBodyAction("ap-approval", { user_id: currentUser?.id ?? "USR-005", user_name: currentUser?.name ?? "Robert Halliday", decision: "rejected", comments: form.comments })}
                      className="flex-1 py-1.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30">
                      Reject
                    </button>
                  </div>
                </div>
              )}
              {ptw.status === "ap_approval" && (
                <button disabled={actionLoading} onClick={() => doAction("issue", { ap_id: currentUser?.id ?? "USR-005", ap_name: currentUser?.name ?? "Robert Halliday" })}
                  className="w-full py-2 text-sm rounded bg-teal-500/20 text-teal-400 border border-teal-500/30 hover:bg-teal-500/30">
                  Issue Permit
                </button>
              )}
              {ptw.status === "issued" && (
                <button disabled={actionLoading} onClick={() => doAction("activate", { user_id: currentUser?.id ?? "USR-001", user_name: currentUser?.name ?? "James Mitchell" })}
                  className="w-full py-2 text-sm rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30">
                  Activate — Work Commencing
                </button>
              )}
              {ptw.status === "active" && (
                <div className="flex gap-2">
                  <button disabled={actionLoading} onClick={() => doBodyAction("request-closure", { requested_by_id: currentUser?.id ?? "USR-001", requested_by_name: currentUser?.name ?? "James Mitchell", comments: "Work complete" })}
                    className="flex-1 py-2 text-sm rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:bg-amber-500/30">
                    Request Closure
                  </button>
                  <button disabled={actionLoading} onClick={() => doBodyAction("suspend", { user_id: currentUser?.id ?? "USR-001", user_name: currentUser?.name ?? "James Mitchell", reason: "Shift end" })}
                    className="flex-1 py-2 text-sm rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30">
                    Suspend
                  </button>
                </div>
              )}
              {ptw.status === "completion_requested" && (
                <button disabled={actionLoading} onClick={() => doBodyAction("close", { ap_id: currentUser?.id ?? "USR-005", ap_name: currentUser?.name ?? "Robert Halliday", comments: "Site returned to safe state" })}
                  className="w-full py-2 text-sm rounded bg-[#2a2a2a] text-[#a0a0a0] border border-[#333] hover:text-[#f9f9f9]">
                  Close Permit (AP)
                </button>
              )}
            </div>
          )}

          {tab === "hazards" && (
            <div className="space-y-3">
              {ptw.hazards?.map((h, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{h.hazard}</p>
                    <div className="flex gap-1">
                      <Pill label={h.likelihood} cls={h.likelihood === "High" ? "text-red-400 bg-red-500/10 border-red-500/20" : "text-amber-400 bg-amber-500/10 border-amber-500/20"} />
                      <Pill label={h.severity} cls={h.severity === "Critical" ? "text-red-400 bg-red-500/10 border-red-500/20" : "text-amber-400 bg-amber-500/10 border-amber-500/20"} />
                    </div>
                  </div>
                  <p className="text-xs text-[#a0a0a0]">{h.mitigation}</p>
                </div>
              )) ?? <p className="text-xs text-[#6b7280]">No hazards recorded.</p>}
              <div>
                <p className="text-xs font-semibold text-[#f9f9f9] mb-2">PPE Requirements</p>
                {ptw.ppe_requirements?.map((p, i) => (
                  <div key={i} className="flex justify-between py-1.5 border-b border-[#2a2a2a] last:border-0 text-sm">
                    <span className="text-[#a0a0a0]">{p.item}</span>
                    <span className="text-xs text-[#6b7280]">{p.specification}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {tab === "isolation" && (
            <div className="space-y-2">
              {ptw.isolation_points?.map((ip, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3 flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full bg-amber-500 mt-1.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{ip.tag_number}</p>
                    <p className="text-xs text-[#a0a0a0]">{ip.description}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Pill label={ip.isolation_type} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
                      {ip.verified_by && <span className="text-xs text-[#6b7280]">Verified: {ip.verified_by}</span>}
                    </div>
                  </div>
                  {ip.verified_at && <CheckCircle2 size={14} className="text-emerald-400 flex-shrink-0" />}
                </div>
              )) ?? <p className="text-xs text-[#6b7280]">No isolation points recorded.</p>}
            </div>
          )}

          {tab === "gas" && (
            <div className="space-y-2">
              {ptw.gas_tests?.length ? ptw.gas_tests.map((gt, i) => (
                <div key={i} className="bg-[#242424] rounded-lg p-3 flex items-center gap-3">
                  <div className={clsx("w-3 h-3 rounded-full flex-shrink-0", gt.result === "pass" ? "bg-emerald-500" : "bg-red-500")} />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-[#f9f9f9]">{gt.gas}</p>
                    <p className="text-xs text-[#6b7280]">{gt.tested_by} · {gt.test_time?.slice(0, 16)}</p>
                  </div>
                  <div className="text-right">
                    <p className={clsx("text-sm font-bold", gt.result === "pass" ? "text-emerald-400" : "text-red-400")}>{gt.result?.toUpperCase()}</p>
                    {gt.ppm != null && <p className="text-xs text-[#6b7280]">{gt.ppm} ppm</p>}
                    {gt.lel_percent != null && <p className="text-xs text-[#6b7280]">{gt.lel_percent}% LEL</p>}
                  </div>
                </div>
              )) : <p className="text-xs text-[#6b7280]">No gas tests recorded.</p>}
            </div>
          )}

          {tab === "audit" && (
            <div>
              {ptw.audit_trail?.map((entry, i) => <AuditStep key={i} entry={entry} />) ?? <p className="text-xs text-[#6b7280]">No audit trail.</p>}
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
// PTW Create Modal
// ─────────────────────────────────────────────────────────────────────────────

const PERMIT_TYPES = ["hot_work","cold_work","confined_space","electrical_isolation","height","radiography","excavation","general"];
const PERMIT_TYPE_LABEL: Record<string, string> = {
  hot_work: "Hot Work", cold_work: "Cold Work", confined_space: "Confined Space",
  electrical_isolation: "Electrical Isolation", height: "Work at Height",
  radiography: "Radiography", excavation: "Excavation", general: "General",
};

const inp = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
const sel = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";

function FL({ label, req, children }: { label: string; req?: boolean; children: React.ReactNode }) {
  return <div><label className="block text-xs font-medium text-[#a0a0a0] mb-1">{label}{req && <span className="text-red-400 ml-0.5">*</span>}</label>{children}</div>;
}

function PTWCreateModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    title: "", permit_type: "cold_work", scope_of_work: "",
    location_description: "", planned_start: "", planned_end: "",
    originator_name: "", originator_comments: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const s = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.title.trim()) { setErr("Title is required"); return; }
    setSaving(true); setErr("");
    try {
      const res = await fetch(`${API}/api/v1/permits`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim(), permit_type: form.permit_type,
          scope_of_work: form.scope_of_work || "",
          location_description: form.location_description || undefined,
          planned_start: form.planned_start || undefined,
          planned_end: form.planned_end || undefined,
          originator_name: form.originator_name || undefined,
          originator_comments: form.originator_comments || undefined,
        }),
      });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">New Permit to Work</p>
            <p className="text-xs text-[#6b7280]">Creates in Draft — submit to begin approval workflow</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <FL label="Title" req><input className={inp} value={form.title} onChange={e => s("title", e.target.value)} placeholder="Hot work on CDU furnace burner" /></FL>
          <FL label="Permit Type">
            <select className={sel} value={form.permit_type} onChange={e => s("permit_type", e.target.value)}>
              {PERMIT_TYPES.map(t => <option key={t} value={t}>{PERMIT_TYPE_LABEL[t]}</option>)}
            </select>
          </FL>
          <FL label="Scope of Work">
            <textarea className={inp + " resize-none h-20"} value={form.scope_of_work} onChange={e => s("scope_of_work", e.target.value)} placeholder="Describe the work to be performed…" />
          </FL>
          <FL label="Location / Area"><input className={inp} value={form.location_description} onChange={e => s("location_description", e.target.value)} placeholder="Unit 4 — CDU Furnace Bay" /></FL>
          <div className="grid grid-cols-2 gap-4">
            <FL label="Planned Start"><input type="date" className={inp} value={form.planned_start} onChange={e => s("planned_start", e.target.value)} /></FL>
            <FL label="Planned End"><input type="date" className={inp} value={form.planned_end} onChange={e => s("planned_end", e.target.value)} /></FL>
          </div>
          <FL label="Originator Name"><input className={inp} value={form.originator_name} onChange={e => s("originator_name", e.target.value)} placeholder="John Smith" /></FL>
          <FL label="Originator Comments">
            <textarea className={inp + " resize-none h-16"} value={form.originator_comments} onChange={e => s("originator_comments", e.target.value)} placeholder="Additional context or precautions…" />
          </FL>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}Create PTW
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PermitsPage() {
  const { permits: permitsState, updatePermits } = usePageState();
  const [permits, setPermits] = useState<PTW[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<PTW | null>(null);
  const [filterStatus, _setFilterStatus] = useState<string>(permitsState.filterStatus);
  const setFilterStatus = (s: string) => { _setFilterStatus(s); updatePermits({ filterStatus: s }); };
  const [filterType, _setFilterType] = useState<string>(permitsState.filterType);
  const setFilterType = (s: string) => { _setFilterType(s); updatePermits({ filterType: s }); };
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const load = async () => {
    setLoading(true);
    const data = await fetch(`${API}/api/v1/permits`).then(r => r.ok ? r.json() : []);
    setPermits(data);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const filtered = permits.filter(p => {
    if (filterStatus !== "all" && p.status !== filterStatus) return false;
    if (filterType !== "all" && p.permit_type !== filterType) return false;
    return true;
  });

  const countBy = (field: keyof PTW) => {
    const c: Record<string, number> = {};
    permits.forEach(p => { const v = String(p[field]); c[v] = (c[v] || 0) + 1; });
    return c;
  };

  const statusCounts = countBy("status");

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0f0f0f] min-h-screen">
      {selected && <PTWDetail ptw={selected} onClose={() => setSelected(null)} onRefresh={load} />}
      {createOpen && <PTWCreateModal onClose={() => setCreateOpen(false)} onSave={() => { load(); setCreateOpen(false); setToast({ msg: "PTW created", ok: true }); }} />}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#f9f9f9] flex items-center gap-3">
            <ShieldAlert size={26} className="text-amber-500" />
            Permit to Work (PTW)
          </h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Industry-standard PTW workflow: Originator → Area Authority → Safety Officer → AP → Active → Closure
          </p>
        </div>
        <button onClick={() => setCreateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors">
          <Plus size={16} />New PTW
        </button>
      </div>

      {/* Status summary */}
      <div className="flex flex-wrap gap-2 mb-5">
        {Object.entries(statusCounts).map(([st, cnt]) => (
          <button key={st}
            onClick={() => setFilterStatus(filterStatus === st ? "all" : st)}
            className={clsx(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors",
              filterStatus === st
                ? "border-amber-500 bg-amber-500/10 text-amber-400"
                : (STATUS_COLOR[st] ?? "text-[#6b7280] bg-[#1f1f1f] border-[#2a2a2a]"),
            )}>
            {STATUS_LABEL[st] ?? st} <span className="opacity-70">({cnt})</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center text-[#6b7280] py-20">Loading permits…</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <ShieldAlert size={40} className="text-[#333] mx-auto mb-3" />
          <p className="text-sm text-[#6b7280]">No permits found.</p>
          <button onClick={() => setCreateOpen(true)} className="mt-3 text-sm text-amber-400 hover:underline">Create your first PTW &rarr;</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map(p => <PTWCard key={p.id} ptw={p} onSelect={() => setSelected(p)} />)}
        </div>
      )}
    </div>
  );
}
