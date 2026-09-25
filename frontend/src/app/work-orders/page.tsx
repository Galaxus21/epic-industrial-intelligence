/**
 * AI Operations Brain — Work Orders Page
 * Interface for managing saved work orders.
 * Technicians can check off steps, add notes, and submit completion feedback
 * which is stored in the knowledge base to improve future AI responses.
 */
"use client";

import { useEffect, useRef, useState, useCallback, Suspense } from "react";

export const dynamic = "force-dynamic";
import {
  listWorkOrders,
  updateWorkOrderStep, completeWorkOrder,
  deleteWorkOrder, updateWorkOrder,
  errorText,
} from "@/lib/api";
import type { SavedWorkOrder, OpsStatus, SavedWorkOrderStep } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { AIOpsChat } from "@/components/WorkOrders/AIOpsChat";
import {
  Wrench, CheckCircle2, Circle, AlertTriangle,
  Clock, Users, Package, ChevronDown, ChevronUp, ShieldAlert,
  ThumbsUp, ThumbsDown, Minus, Send, Loader2, Brain, Trash2, Pencil, MessageSquare,
} from "lucide-react";
import clsx from "clsx";
import { useCurrentUser } from "@/lib/user-context";
import { approverRoles, fieldRoles, hasRole } from "@/lib/roles";
import { toast } from "sonner";

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_BADGE: Record<OpsStatus, "low" | "medium" | "high"> = {
  open: "muted" as any,
  in_progress: "medium",
  completed: "low",
};

const PHASE_COLOR: Record<string, string> = {
  Preparation: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  Isolation: "text-orange-400 bg-orange-500/10 border-orange-500/30",
  Execution: "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Verification: "text-teal-400 bg-teal-500/10 border-teal-500/30",
  Restart: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
};

// ── Work order card ────────────────────────────────────────────────────────────

function WorkOrderDetailCard({ wo, onUpdate, onDelete }: { wo: SavedWorkOrder; onUpdate: () => void; onDelete: () => void }) {
  const { currentUser } = useCurrentUser();
  const canEditOrDelete = hasRole(currentUser?.role, approverRoles);
  const canWork = hasRole(currentUser?.role, fieldRoles);
  const [open, setOpen] = useState(wo.status !== "completed");
  const [showFeedback, setShowFeedback] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState({
    solution_worked: null as boolean | null,
    is_partial: false,
    extra_steps_taken: "",
    outcome_notes: "",
    completed_by: currentUser?.name || "",
    actual_duration_hours: "",
  });
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); }, []);
  const [editValues, setEditValues] = useState({
    description: wo.description,
    wo_type: wo.wo_type,
    risk_level: wo.risk_level ?? "",
    estimated_duration_hours: String(wo.estimated_duration_hours),
  });
  const [showChat, setShowChat] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteWorkOrder(wo.id);
      toast.success("Work order deleted");
      onDelete();
    } catch (err) {
      toast.error(errorText(err, "Failed to delete work order"));
    } finally {
      setDeleting(false);
    }
  };

  const handleEdit = async () => {
    setSaving(true);
    try {
      await updateWorkOrder(wo.id, {
        description: editValues.description,
        wo_type: editValues.wo_type,
        risk_level: editValues.risk_level || null,
        estimated_duration_hours: parseFloat(editValues.estimated_duration_hours) || 0,
      });
      toast.success("Work order updated");
      setEditMode(false);
      onUpdate();
    } catch (err) {
      toast.error(errorText(err, "Failed to update work order"));
    } finally {
      setSaving(false);
    }
  };

  const doneCount = wo.steps.filter(s => s.checked).length;
  const pct = wo.steps.length > 0 ? Math.round((doneCount / wo.steps.length) * 100) : 0;

  const toggleStep = async (idx: number, checked: boolean) => {
    setSaving(true);
    try {
      await updateWorkOrderStep(wo.id, { step_index: idx, checked, actual_notes: wo.steps[idx].actual_notes });
      onUpdate();
    } catch (err) {
      toast.error(errorText(err, "Failed to update step"));
    } finally {
      setSaving(false);
    }
  };

  const updateStepNote = async (idx: number, notes: string) => {
    try {
      await updateWorkOrderStep(wo.id, { step_index: idx, checked: wo.steps[idx].checked, actual_notes: notes });
      onUpdate();
    } catch (err) {
      toast.error(errorText(err, "Failed to update step note"));
    }
  };

  const submitFeedback = async () => {
    setSubmitting(true);
    try {
      await completeWorkOrder(wo.id, {
        solution_worked: feedback.solution_worked,
        is_partial: feedback.is_partial,
        extra_steps_taken: feedback.extra_steps_taken,
        outcome_notes: feedback.outcome_notes,
        completed_by: feedback.completed_by,
        actual_duration_hours: feedback.actual_duration_hours ? parseFloat(feedback.actual_duration_hours) : null,
      });
      toast.success("Work order completed and feedback saved");
      onUpdate();
      setShowFeedback(false);
    } catch (err) {
      toast.error(errorText(err, "Failed to submit feedback"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={clsx(
      "border rounded-xl overflow-hidden transition-all",
      wo.status === "completed" ? "bg-[#141414] border-[#1e1e1e] opacity-85" : "bg-[#1f1f1f] border-[#2a2a2a]",
    )}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#242424] transition-colors select-none"
      >
        <Wrench size={16} className="text-purple-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#f9f9f9]">{wo.id}</span>
            <span className="text-xs font-mono text-amber-400">{wo.equipment_id}</span>
            <span className="text-xs px-1.5 py-0.5 rounded border text-purple-400 bg-purple-500/10 border-purple-500/25">{wo.wo_type}</span>
            {wo.risk_level && <Badge variant={wo.risk_level === "High" || wo.risk_level === "Critical" ? "high" : "medium"}>{wo.risk_level}</Badge>}
            <span className={clsx("text-xs px-2 py-0.5 rounded-full border capitalize",
              wo.status === "completed" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" :
              wo.status === "in_progress" ? "bg-amber-500/15 text-amber-400 border-amber-500/30" :
              "bg-[#2a2a2a] text-[#9ca3af] border-[#333]"
            )}>{wo.status.replace("_", " ")}</span>
            {wo.is_partial && <span title="Partially worked"><Minus size={13} className="text-amber-400" /></span>}
            {!wo.is_partial && wo.solution_worked === true && <span title="Solution worked"><ThumbsUp size={13} className="text-emerald-400" /></span>}
            {!wo.is_partial && wo.solution_worked === false && <span title="Solution did not work"><ThumbsDown size={13} className="text-red-400" /></span>}
          </div>
          <p className="text-xs text-[#6b7280] truncate mt-0.5">{wo.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="flex items-center gap-1 text-xs text-[#6b7280]">
            <Clock size={11} />{wo.estimated_duration_hours}h
          </div>
          <span className="text-xs text-[#6b7280]">{doneCount}/{wo.steps.length} steps</span>
          {canEditOrDelete && (
            <button onClick={e => { e.stopPropagation(); setEditMode(m => !m); setOpen(true); }}
              className="p-1 rounded text-[#4b5563] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit" aria-label="Edit work order">
              <Pencil size={12} />
            </button>
          )}
          <button onClick={e => { e.stopPropagation(); setShowChat(c => !c); }}
            className={clsx("p-1 rounded transition-colors", showChat ? "text-purple-400 bg-purple-500/10" : "text-[#4b5563] hover:text-purple-400 hover:bg-purple-500/10")} title="AI Assistant" aria-label="AI Assistant">
            <MessageSquare size={12} />
          </button>
          {canEditOrDelete && (confirmDelete ? (
            <button onClick={e => { e.stopPropagation(); handleDelete(); }}
              className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors flex items-center gap-1">
              {deleting ? <Loader2 size={10} className="animate-spin" /> : "Confirm?"}
            </button>
          ) : (
            <button onClick={e => { e.stopPropagation(); setConfirmDelete(true); if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); confirmTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000); }}
              className="p-1 rounded text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete" aria-label="Delete work order">
              <Trash2 size={12} />
            </button>
          ))}
          {open ? <ChevronUp size={14} className="text-[#4b5563]" /> : <ChevronDown size={14} className="text-[#4b5563]" />}
        </div>
      </div>

      {open && (
        <div className="border-t border-[#222] px-4 pb-4">
          {/* Inline edit panel */}
          {editMode && (
            <div className="mt-3 mb-3 p-3 bg-[#181818] border border-[#2a2a2a] rounded-lg space-y-2">
              <p className="text-xs font-semibold text-[#a0a0a0]">Edit Work Order</p>
              <div className="flex gap-2 flex-wrap">
                <div>
                  <p className="text-xs text-[#6b7280] mb-1">Type</p>
                  <input value={editValues.wo_type} onChange={e => setEditValues(v => ({ ...v, wo_type: e.target.value }))}
                    aria-label="Work order type"
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] w-36 focus:outline-none focus:border-amber-500/50" />
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] mb-1">Risk Level</p>
                  <select value={editValues.risk_level} onChange={e => setEditValues(v => ({ ...v, risk_level: e.target.value }))}
                    aria-label="Risk level"
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] focus:outline-none focus:border-amber-500/50">
                    <option value="">None</option>
                    {["Low","Medium","High","Critical"].map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] mb-1">Est. Duration (h)</p>
                  <input type="number" value={editValues.estimated_duration_hours}
                    onChange={e => setEditValues(v => ({ ...v, estimated_duration_hours: e.target.value }))}
                    aria-label="Estimated duration in hours"
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] w-24 focus:outline-none focus:border-amber-500/50" />
                </div>
              </div>
              <div>
                <p className="text-xs text-[#6b7280] mb-1">Description</p>
                <textarea value={editValues.description} onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))}
                  aria-label="Work order description"
                  rows={2} className="w-full bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] resize-none focus:outline-none focus:border-amber-500/50" />
              </div>
              <div className="flex gap-2">
                <button onClick={handleEdit} disabled={saving}
                  className="flex items-center gap-1 text-xs px-3 py-1 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded hover:bg-amber-500/30 transition-colors disabled:opacity-50">
                  {saving && <Loader2 size={10} className="animate-spin" />} Save
                </button>
                <button onClick={() => setEditMode(false)}
                  className="text-xs px-3 py-1 border border-[#333] text-[#6b7280] rounded hover:border-[#444] transition-colors">Cancel</button>
              </div>
            </div>
          )}
          {/* Meta row */}
          <div className="flex gap-4 py-2 border-b border-[#222] mb-3 text-xs text-[#6b7280]">
            <span className="flex items-center gap-1"><Users size={11} />{wo.required_technicians} required</span>
            <span className="flex items-center gap-1"><Package size={11} />{wo.spare_parts.length} parts</span>
            {wo.completed_by && <span>Completed by: <span className="text-[#a0a0a0]">{wo.completed_by}</span></span>}
          </div>

          {/* Progress bar */}
          <div className="h-1.5 bg-[#2a2a2a] rounded-full mb-3 overflow-hidden">
            <div className={clsx("h-full rounded-full transition-all", pct === 100 ? "bg-emerald-500" : "bg-purple-500")}
              style={{ width: `${pct}%` }} />
          </div>

          {/* Safety precautions */}
          {wo.safety_precautions.length > 0 && (
            <div className="mb-3 p-2 bg-red-500/5 border border-red-500/20 rounded-lg">
              <div className="flex items-center gap-1.5 mb-1">
                <ShieldAlert size={12} className="text-red-400" />
                <span className="text-xs font-semibold text-red-400">Safety Precautions</span>
              </div>
              {wo.safety_precautions.map((p, i) => (
                <p key={i} className="text-xs text-red-300/70">⚠ {p}</p>
              ))}
            </div>
          )}

          {/* Steps */}
          <div className="space-y-2 mb-4">
            {wo.steps.map((step, idx) => (
              <StepItem key={idx} step={step} idx={idx} disabled={wo.status === "completed" || saving || !canWork}
                onToggle={(checked) => toggleStep(idx, checked)}
                onNoteChange={(notes) => updateStepNote(idx, notes)} />
            ))}
          </div>

          {/* Spare parts */}
          {wo.spare_parts.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {wo.spare_parts.map((p, i) => (
                <span key={i} className="text-xs px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded-lg text-purple-400">{p}</span>
              ))}
            </div>
          )}

          {/* Feedback / complete */}
          {canWork && wo.status !== "completed" && doneCount === wo.steps.length && !showFeedback && (
            <button onClick={() => setShowFeedback(true)}
              className="w-full py-2 text-xs text-emerald-400 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/10 transition-colors flex items-center justify-center gap-2">
              <Brain size={13} /> All steps done — Submit feedback to improve AI →
            </button>
          )}

          {showFeedback && (
            <FeedbackForm
              feedback={feedback}
              onChange={(f) => setFeedback(f)}
              onSubmit={submitFeedback}
              submitting={submitting}
            />
          )}

          {wo.status === "completed" && (
            <CompletionSummary wo={wo} />
          )}
        </div>
      )}
      {showChat && (
        <AIOpsChat itemId={wo.id} steps={wo.steps} onApply={onUpdate} />
      )}
    </div>
  );
}

// ── Step item ──────────────────────────────────────────────────────────────────

function StepItem({ step, idx, disabled, onToggle, onNoteChange }: {
  step: SavedWorkOrderStep; idx: number; disabled: boolean;
  onToggle: (checked: boolean) => void;
  onNoteChange: (notes: string) => void;
}) {
  const [editNote, setEditNote] = useState(false);
  const [note, setNote] = useState(step.actual_notes || "");
  const phaseCls = PHASE_COLOR[step.phase] ?? PHASE_COLOR.Execution;

  return (
    <div className={clsx(
      "rounded-lg border transition-all",
      step.checked ? "bg-[#141414] border-[#1e1e1e]" : "bg-[#1a1a1a] border-[#2a2a2a]",
    )}>
      <div className="flex items-start gap-2 p-2.5">
        <button
          onClick={() => onToggle(!step.checked)}
          disabled={disabled}
          className="flex-shrink-0 mt-0.5"
          aria-label={step.checked ? `Mark step ${step.step} incomplete` : `Mark step ${step.step} complete`}
        >
          {step.checked
            ? <CheckCircle2 size={18} className="text-emerald-400 fill-emerald-400/20" />
            : <Circle size={18} className="text-[#3a3a3a] hover:text-[#6b7280] transition-colors" />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-[#4b5563] font-mono">{step.step}.</span>
            <span className={clsx("text-xs px-1.5 py-0.5 rounded-full border", phaseCls)}>{step.phase}</span>
            <span className={clsx("text-xs font-semibold", step.checked ? "line-through text-[#4b5563]" : "text-[#f9f9f9]")}>{step.title}</span>
            {step.expected_duration_minutes > 0 && (
              <span className="text-xs text-[#4b5563] flex items-center gap-0.5"><Clock size={9} />{step.expected_duration_minutes}m</span>
            )}
            {step.safety_note && <AlertTriangle size={12} className="text-red-400 flex-shrink-0" />}
          </div>
          <p className="text-xs text-[#6b7280] mt-0.5 leading-relaxed">{step.description}</p>
          {step.safety_note && (
            <div className="flex gap-1.5 mt-1 p-1.5 bg-red-500/5 border border-red-500/20 rounded text-xs text-red-300/80">
              <ShieldAlert size={11} className="flex-shrink-0 mt-0.5 text-red-400" />{step.safety_note}
            </div>
          )}
          {step.checked && (
            editNote ? (
              <div className="mt-1.5 flex gap-1">
                <input
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  placeholder="Add note about this step..."
                  aria-label="Step note"
                  className="flex-1 bg-[#111] border border-[#2a2a2a] rounded px-2 py-1 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-emerald-500/50"
                  onKeyDown={e => { if (e.key === "Enter") { onNoteChange(note); setEditNote(false); } }}
                  autoFocus
                />
                <button onClick={() => { onNoteChange(note); setEditNote(false); }}
                  className="px-2 py-1 text-xs bg-emerald-500/20 text-emerald-400 rounded hover:bg-emerald-500/30">
                  Save
                </button>
              </div>
            ) : (
              <button onClick={() => setEditNote(true)} className="mt-1 text-xs text-[#4b5563] hover:text-[#6b7280] transition-colors">
                {step.actual_notes ? `📝 ${step.actual_notes}` : "+ Add note"}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// ── Feedback form ──────────────────────────────────────────────────────────────

function FeedbackForm({ feedback, onChange, onSubmit, submitting }: {
  feedback: { solution_worked: boolean | null; is_partial?: boolean; extra_steps_taken: string; outcome_notes: string; completed_by: string; actual_duration_hours: string };
  onChange: (f: any) => void;
  onSubmit: () => void;
  submitting: boolean;
}) {
  return (
    <div className="mt-3 p-4 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <Brain size={14} className="text-amber-400" />
        <p className="text-sm font-semibold text-[#f9f9f9]">Completion Feedback</p>
        <span className="text-xs text-[#6b7280]">— helps the AI learn from this outcome</span>
      </div>

      {/* Did it work */}
      <div>
        <p className="text-xs text-[#6b7280] mb-1.5">Did the recommended solution resolve the issue?</p>
        <div className="flex gap-2">
          {([
            { v: true,  partial: false, label: "Yes, worked",     icon: <ThumbsUp size={12} />,   cls: "text-emerald-400 bg-emerald-500/15 border-emerald-500/30 hover:bg-emerald-500/25" },
            { v: false, partial: false, label: "No, didn't work", icon: <ThumbsDown size={12} />, cls: "text-red-400 bg-red-500/15 border-red-500/30 hover:bg-red-500/25" },
            { v: null,  partial: true,  label: "Partially",        icon: <Minus size={12} />,      cls: "text-amber-400 bg-amber-500/15 border-amber-500/30 hover:bg-amber-500/25" },
          ] as const).map(opt => {
            const isSelected = opt.partial ? feedback.is_partial : (feedback.solution_worked === opt.v && !feedback.is_partial);
            return (
              <button key={opt.label} onClick={() => onChange({ ...feedback, solution_worked: opt.v, is_partial: opt.partial })}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors",
                  isSelected
                    ? opt.cls
                    : "text-[#6b7280] bg-[#2a2a2a] border-[#333] hover:border-[#444]",
                )}>
                {opt.icon} {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="text-xs text-[#6b7280] mb-1">Extra steps taken beyond the work order (if any)</p>
        <textarea value={feedback.extra_steps_taken}
          onChange={e => onChange({ ...feedback, extra_steps_taken: e.target.value })}
          placeholder="e.g. Also replaced coupling insert; found impeller scoring..."
          aria-label="Extra steps taken"
          rows={2}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#f9f9f9] placeholder-[#4b5563] resize-none focus:outline-none focus:border-amber-500/50" />
      </div>

      <div>
        <p className="text-xs text-[#6b7280] mb-1">Overall outcome / observations</p>
        <textarea value={feedback.outcome_notes}
          onChange={e => onChange({ ...feedback, outcome_notes: e.target.value })}
          placeholder="What was the actual root cause? What would you do differently next time?"
          aria-label="Overall outcome and observations"
          rows={3}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#f9f9f9] placeholder-[#4b5563] resize-none focus:outline-none focus:border-amber-500/50" />
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <p className="text-xs text-[#6b7280] mb-1">Completed by</p>
          <input value={feedback.completed_by}
            onChange={e => onChange({ ...feedback, completed_by: e.target.value })}
            placeholder="Technician name"
            aria-label="Completed by technician name"
            className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50" />
        </div>
        <div className="w-28">
          <p className="text-xs text-[#6b7280] mb-1">Actual duration (h)</p>
          <input type="number" value={feedback.actual_duration_hours}
            onChange={e => onChange({ ...feedback, actual_duration_hours: e.target.value })}
            placeholder="e.g. 9.5"
            aria-label="Actual duration in hours"
            className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50" />
        </div>
      </div>

      <button onClick={onSubmit} disabled={submitting}
        className="w-full flex items-center justify-center gap-2 py-2 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded-lg hover:bg-amber-500/30 transition-colors text-xs font-semibold disabled:opacity-50">
        {submitting ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
        Submit Feedback — Add to Knowledge Base
      </button>
    </div>
  );
}

// ── Completion summary ────────────────────────────────────────────────────────

function CompletionSummary({ wo }: { wo: SavedWorkOrder }) {
  return (
    <div className="mt-3 p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-xl space-y-1.5">
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 size={13} className="text-emerald-400" />
        <span className="text-xs font-semibold text-emerald-400">Completed {wo.completed_at?.slice(0, 10)}</span>
        {wo.is_partial && <span className="text-xs text-amber-400 flex items-center gap-1"><Minus size={11} /> Partially worked</span>}
        {!wo.is_partial && wo.solution_worked === true && <span className="text-xs text-emerald-400 flex items-center gap-1"><ThumbsUp size={11} /> Solution worked</span>}
        {!wo.is_partial && wo.solution_worked === false && <span className="text-xs text-red-400 flex items-center gap-1"><ThumbsDown size={11} /> Solution did not work</span>}
        {wo.actual_duration_hours && <span className="text-xs text-[#6b7280]">· {wo.actual_duration_hours}h actual</span>}
        {wo.completed_by && <span className="text-xs text-[#6b7280]">· {wo.completed_by}</span>}
      </div>
      {wo.extra_steps_taken && (
        <div>
          <p className="text-xs text-[#6b7280] font-semibold">Extra steps taken:</p>
          <p className="text-xs text-[#a0a0a0]">{wo.extra_steps_taken}</p>
        </div>
      )}
      {wo.outcome_notes && (
        <div>
          <p className="text-xs text-[#6b7280] font-semibold">Outcome notes:</p>
          <p className="text-xs text-[#a0a0a0]">{wo.outcome_notes}</p>
        </div>
      )}
      <div className="flex items-center gap-1.5 pt-1 text-xs text-amber-400/70">
        <Brain size={11} />
        <span>Feedback saved to knowledge base — AI will learn from this outcome</span>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

function WorkOrdersPageInner() {
  const [workOrders, setWorkOrders] = useState<SavedWorkOrder[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const wos = await listWorkOrders().catch(() => [] as SavedWorkOrder[]);
    setWorkOrders(wos);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-[#f9f9f9]">Work Orders</h1>
        <p className="text-xs text-[#6b7280] mt-1 flex items-center gap-1">
          <Brain size={12} className="text-amber-400" />
          Completion feedback is stored in the knowledge base and improves future AI responses
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-[#6b7280] py-10">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {workOrders.length === 0 ? (
            <EmptyState />
          ) : workOrders.map(wo => (
            <WorkOrderDetailCard key={wo.id} wo={wo} onUpdate={load} onDelete={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-[#9ca3af]">
      <Wrench size={36} className="mb-3 opacity-60 text-[#d1d5db]" />
      <p className="text-sm font-medium text-[#f9f9f9]">No work orders yet</p>
      <p className="text-xs mt-1 text-[#a0a0a0]">Run an AI query and use "Save to Work Orders" to create one</p>
      <a href="/query" className="mt-3 text-xs text-amber-400 hover:text-amber-300 font-medium underline underline-offset-2">→ Go to AI Query</a>
    </div>
  );
}

export default function WorkOrdersPage() {
  return (
    <Suspense fallback={<div className="p-6 text-[#6b7280] text-sm">Loading…</div>}>
      <WorkOrdersPageInner />
    </Suspense>
  );
}
