/**
 * AI Operations Brain — Work Orders & Checklists Page
 * Two-tab interface for managing saved inspection checklists and work orders.
 * Technicians can check off items, add notes, and submit completion feedback
 * which is stored in the knowledge base to improve future AI responses.
 */
"use client";

import { useEffect, useRef, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";

export const dynamic = "force-dynamic";
import {
  listWorkOrders, listChecklists,
  updateWorkOrderStep, completeWorkOrder,
  updateChecklistItem, completeChecklist,
  deleteChecklist, deleteWorkOrder, updateChecklist, updateWorkOrder,
  chatWithWorkOrder, chatWithChecklist, addChecklistItems, addWorkOrderSteps,
} from "@/lib/api";
import type { OpsProposedChanges } from "@/lib/api";
import type { SavedWorkOrder, SavedChecklist, OpsStatus, SavedWorkOrderStep } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import {
  ClipboardList, Wrench, CheckCircle2, Circle, AlertTriangle,
  Clock, Users, Package, ChevronDown, ChevronUp, ShieldAlert,
  ThumbsUp, ThumbsDown, Minus, Send, Loader2, Brain, Trash2, Pencil, MessageSquare,
} from "lucide-react";
import clsx from "clsx";

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

// ── Checklist card ────────────────────────────────────────────────────────────

function ChecklistCard({ cl, onUpdate, onDelete }: { cl: SavedChecklist; onUpdate: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(cl.status !== "completed");
  const [outcomeNotes, setOutcomeNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [showCompleteForm, setShowCompleteForm] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editValues, setEditValues] = useState({ query_text: cl.query_text, risk_level: cl.risk_level ?? "" });
  const [showChat, setShowChat] = useState(false);
  const confirmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up confirm-dismiss timer on unmount to prevent state update on unmounted component
  useEffect(() => () => { if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); }, []);

  const handleDelete = async () => { setDeleting(true); await deleteChecklist(cl.id).catch(() => {}); onDelete(); };
  const handleEdit = async () => {
    setSaving(true);
    await updateChecklist(cl.id, { query_text: editValues.query_text, risk_level: editValues.risk_level || null }).catch(() => {});
    setSaving(false); setEditMode(false); onUpdate();
  };

  const doneCount = cl.items.filter(i => i.checked).length;
  const pct = cl.items.length > 0 ? Math.round((doneCount / cl.items.length) * 100) : 0;

  const toggleItem = async (idx: number, checked: boolean) => {
    setSaving(true);
    await updateChecklistItem(cl.id, { index: idx, checked, notes: cl.items[idx].notes });
    onUpdate();
    setSaving(false);
  };

  const submitComplete = async () => {
    setCompleting(true);
    await completeChecklist(cl.id, { outcome_notes: outcomeNotes });
    onUpdate();
    setCompleting(false);
    setShowCompleteForm(false);
  };

  return (
    <div className={clsx(
      "border rounded-xl overflow-hidden transition-all",
      cl.status === "completed" ? "bg-[#141414] border-[#1e1e1e] opacity-80" : "bg-[#1f1f1f] border-[#2a2a2a]",
    )}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#242424] transition-colors select-none"
      >
        <ClipboardList size={16} className="text-blue-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#f9f9f9]">{cl.id}</span>
            <span className="text-xs font-mono text-amber-400">{cl.equipment_id}</span>
            {cl.risk_level && <Badge variant={cl.risk_level === "High" || cl.risk_level === "Critical" ? "high" : "medium"}>{cl.risk_level}</Badge>}
            <span className={clsx("text-xs px-2 py-0.5 rounded-full border capitalize",
              cl.status === "completed" ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" :
              cl.status === "in_progress" ? "bg-amber-500/15 text-amber-400 border-amber-500/30" :
              "bg-[#2a2a2a] text-[#6b7280] border-[#333]"
            )}>{cl.status.replace("_", " ")}</span>
          </div>
          <p className="text-xs text-[#6b7280] truncate mt-0.5">{cl.query_text}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-[#6b7280]">{doneCount}/{cl.items.length} · {pct}%</span>
          <button onClick={e => { e.stopPropagation(); setEditMode(m => !m); setOpen(true); }}
            className="p-1 rounded text-[#4b5563] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit">
            <Pencil size={12} />
          </button>
          <button onClick={e => { e.stopPropagation(); setShowChat(c => !c); }}
            className={clsx("p-1 rounded transition-colors", showChat ? "text-purple-400 bg-purple-500/10" : "text-[#4b5563] hover:text-purple-400 hover:bg-purple-500/10")} title="AI Assistant">
            <MessageSquare size={12} />
          </button>
          {confirmDelete ? (
            <button onClick={e => { e.stopPropagation(); handleDelete(); }}
              className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors flex items-center gap-1">
              {deleting ? <Loader2 size={10} className="animate-spin" /> : "Confirm?"}
            </button>
          ) : (
            <button onClick={e => { e.stopPropagation(); setConfirmDelete(true); if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); confirmTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000); }}
              className="p-1 rounded text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
              <Trash2 size={12} />
            </button>
          )}
          {open ? <ChevronUp size={14} className="text-[#4b5563]" /> : <ChevronDown size={14} className="text-[#4b5563]" />}
        </div>
      </div>

      {open && (
        <div className="border-t border-[#222] px-4 pb-4">
          {/* Inline edit panel */}
          {editMode && (
            <div className="mt-3 mb-3 p-3 bg-[#181818] border border-[#2a2a2a] rounded-lg space-y-2">
              <p className="text-xs font-semibold text-[#a0a0a0]">Edit Checklist</p>
              <div>
                <p className="text-xs text-[#6b7280] mb-1">Risk Level</p>
                <select value={editValues.risk_level} onChange={e => setEditValues(v => ({ ...v, risk_level: e.target.value }))}
                  className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] focus:outline-none focus:border-amber-500/50">
                  <option value="">None</option>
                  {["Low","Medium","High","Critical"].map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <p className="text-xs text-[#6b7280] mb-1">Query / Description</p>
                <textarea value={editValues.query_text} onChange={e => setEditValues(v => ({ ...v, query_text: e.target.value }))}
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
          {/* Progress */}
          <div className="h-1 bg-[#2a2a2a] rounded-full my-3 overflow-hidden">
            <div className={clsx("h-full rounded-full transition-all", pct === 100 ? "bg-emerald-500" : "bg-blue-500")}
              style={{ width: `${pct}%` }} />
          </div>

          {/* Items */}
          <div className="space-y-1.5 mb-4">
            {cl.items.map((item, idx) => (
              <div key={idx} className="flex items-start gap-2 group">
                <button
                  onClick={() => toggleItem(idx, !item.checked)}
                  disabled={cl.status === "completed" || saving}
                  className="flex-shrink-0 mt-0.5"
                >
                  {item.checked
                    ? <CheckCircle2 size={18} className="text-emerald-400 fill-emerald-400/20" />
                    : <Circle size={18} className="text-[#3a3a3a] hover:text-[#6b7280] transition-colors" />}
                </button>
                <p className={clsx("text-xs leading-relaxed flex-1",
                  item.checked ? "line-through text-[#4b5563]" : "text-[#a0a0a0]"
                )}>{item.text}</p>
              </div>
            ))}
          </div>

          {/* Complete form */}
          {cl.status !== "completed" && doneCount === cl.items.length && !showCompleteForm && (
            <button onClick={() => setShowCompleteForm(true)}
              className="w-full py-2 text-xs text-emerald-400 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/10 transition-colors">
              All checked — Mark complete & add notes →
            </button>
          )}

          {showCompleteForm && (
            <div className="space-y-2 mt-2 p-3 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a]">
              <p className="text-xs font-semibold text-[#a0a0a0]">Completion notes (optional)</p>
              <textarea
                value={outcomeNotes}
                onChange={e => setOutcomeNotes(e.target.value)}
                placeholder="What was found? Any deviations? Notes for the team..."
                rows={3}
                className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#f9f9f9] placeholder-[#4b5563] resize-none focus:outline-none focus:border-emerald-500/50"
              />
              <button onClick={submitComplete} disabled={completing}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/30 transition-colors disabled:opacity-50">
                {completing ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
                Confirm Complete
              </button>
            </div>
          )}

          {cl.status === "completed" && cl.outcome_notes && (
            <div className="mt-2 p-2 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
              <p className="text-xs text-emerald-400 font-semibold mb-1">Outcome notes</p>
              <p className="text-xs text-[#a0a0a0]">{cl.outcome_notes}</p>
            </div>
          )}
        </div>
      )}
      {showChat && (
        <AIOpsChat itemId={cl.id} itemType="checklist" onApply={onUpdate} />
      )}
    </div>
  );
}

// ── Work order card ────────────────────────────────────────────────────────────

function WorkOrderDetailCard({ wo, onUpdate, onDelete }: { wo: SavedWorkOrder; onUpdate: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(wo.status !== "completed");
  const [showFeedback, setShowFeedback] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState({
    solution_worked: null as boolean | null,
    extra_steps_taken: "",
    outcome_notes: "",
    completed_by: "",
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

  const handleDelete = async () => { setDeleting(true); await deleteWorkOrder(wo.id).catch(() => {}); onDelete(); };
  const handleEdit = async () => {
    setSaving(true);
    await updateWorkOrder(wo.id, {
      description: editValues.description,
      wo_type: editValues.wo_type,
      risk_level: editValues.risk_level || null,
      estimated_duration_hours: parseFloat(editValues.estimated_duration_hours) || 0,
    }).catch(() => {});
    setSaving(false); setEditMode(false); onUpdate();
  };

  const doneCount = wo.steps.filter(s => s.checked).length;
  const pct = wo.steps.length > 0 ? Math.round((doneCount / wo.steps.length) * 100) : 0;

  const toggleStep = async (idx: number, checked: boolean) => {
    setSaving(true);
    await updateWorkOrderStep(wo.id, { step_index: idx, checked, actual_notes: wo.steps[idx].actual_notes });
    onUpdate();
    setSaving(false);
  };

  const updateStepNote = async (idx: number, notes: string) => {
    await updateWorkOrderStep(wo.id, { step_index: idx, checked: wo.steps[idx].checked, actual_notes: notes });
    onUpdate();
  };

  const submitFeedback = async () => {
    setSubmitting(true);
    await completeWorkOrder(wo.id, {
      solution_worked: feedback.solution_worked,
      extra_steps_taken: feedback.extra_steps_taken,
      outcome_notes: feedback.outcome_notes,
      completed_by: feedback.completed_by,
      actual_duration_hours: feedback.actual_duration_hours ? parseFloat(feedback.actual_duration_hours) : null,
    });
    onUpdate();
    setSubmitting(false);
    setShowFeedback(false);
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
              "bg-[#2a2a2a] text-[#6b7280] border-[#333]"
            )}>{wo.status.replace("_", " ")}</span>
            {wo.solution_worked === true && <ThumbsUp size={13} className="text-emerald-400" />}
            {wo.solution_worked === false && <ThumbsDown size={13} className="text-red-400" />}
          </div>
          <p className="text-xs text-[#6b7280] truncate mt-0.5">{wo.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="flex items-center gap-1 text-xs text-[#6b7280]">
            <Clock size={11} />{wo.estimated_duration_hours}h
          </div>
          <span className="text-xs text-[#6b7280]">{doneCount}/{wo.steps.length} steps</span>
          <button onClick={e => { e.stopPropagation(); setEditMode(m => !m); setOpen(true); }}
            className="p-1 rounded text-[#4b5563] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit">
            <Pencil size={12} />
          </button>
          <button onClick={e => { e.stopPropagation(); setShowChat(c => !c); }}
            className={clsx("p-1 rounded transition-colors", showChat ? "text-purple-400 bg-purple-500/10" : "text-[#4b5563] hover:text-purple-400 hover:bg-purple-500/10")} title="AI Assistant">
            <MessageSquare size={12} />
          </button>
          {confirmDelete ? (
            <button onClick={e => { e.stopPropagation(); handleDelete(); }}
              className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors flex items-center gap-1">
              {deleting ? <Loader2 size={10} className="animate-spin" /> : "Confirm?"}
            </button>
          ) : (
            <button onClick={e => { e.stopPropagation(); setConfirmDelete(true); if (confirmTimerRef.current) clearTimeout(confirmTimerRef.current); confirmTimerRef.current = setTimeout(() => setConfirmDelete(false), 3000); }}
              className="p-1 rounded text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
              <Trash2 size={12} />
            </button>
          )}
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
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] w-36 focus:outline-none focus:border-amber-500/50" />
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] mb-1">Risk Level</p>
                  <select value={editValues.risk_level} onChange={e => setEditValues(v => ({ ...v, risk_level: e.target.value }))}
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] focus:outline-none focus:border-amber-500/50">
                    <option value="">None</option>
                    {["Low","Medium","High","Critical"].map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <p className="text-xs text-[#6b7280] mb-1">Est. Duration (h)</p>
                  <input type="number" value={editValues.estimated_duration_hours}
                    onChange={e => setEditValues(v => ({ ...v, estimated_duration_hours: e.target.value }))}
                    className="bg-[#1a1a1a] border border-[#333] rounded px-2 py-1 text-xs text-[#f9f9f9] w-24 focus:outline-none focus:border-amber-500/50" />
                </div>
              </div>
              <div>
                <p className="text-xs text-[#6b7280] mb-1">Description</p>
                <textarea value={editValues.description} onChange={e => setEditValues(v => ({ ...v, description: e.target.value }))}
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
              <StepItem key={idx} step={step} idx={idx} disabled={wo.status === "completed" || saving}
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
          {wo.status !== "completed" && doneCount === wo.steps.length && !showFeedback && (
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
        <AIOpsChat itemId={wo.id} itemType="work_order" onApply={onUpdate} />
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
        <button onClick={() => onToggle(!step.checked)} disabled={disabled} className="flex-shrink-0 mt-0.5">
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
  feedback: { solution_worked: boolean | null; extra_steps_taken: string; outcome_notes: string; completed_by: string; actual_duration_hours: string };
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
            { v: true,  label: "Yes, worked",    icon: <ThumbsUp size={12} />,   cls: "text-emerald-400 bg-emerald-500/15 border-emerald-500/30 hover:bg-emerald-500/25" },
            { v: false, label: "No, didn't work", icon: <ThumbsDown size={12} />, cls: "text-red-400 bg-red-500/15 border-red-500/30 hover:bg-red-500/25" },
            { v: null,  label: "Partially",       icon: <Minus size={12} />,      cls: "text-amber-400 bg-amber-500/15 border-amber-500/30 hover:bg-amber-500/25" },
          ] as const).map(opt => (
            <button key={String(opt.v)} onClick={() => onChange({ ...feedback, solution_worked: opt.v })}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors",
                feedback.solution_worked === opt.v
                  ? opt.cls
                  : "text-[#6b7280] bg-[#2a2a2a] border-[#333] hover:border-[#444]",
              )}>
              {opt.icon} {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs text-[#6b7280] mb-1">Extra steps taken beyond the work order (if any)</p>
        <textarea value={feedback.extra_steps_taken}
          onChange={e => onChange({ ...feedback, extra_steps_taken: e.target.value })}
          placeholder="e.g. Also replaced coupling insert; found impeller scoring..."
          rows={2}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#f9f9f9] placeholder-[#4b5563] resize-none focus:outline-none focus:border-amber-500/50" />
      </div>

      <div>
        <p className="text-xs text-[#6b7280] mb-1">Overall outcome / observations</p>
        <textarea value={feedback.outcome_notes}
          onChange={e => onChange({ ...feedback, outcome_notes: e.target.value })}
          placeholder="What was the actual root cause? What would you do differently next time?"
          rows={3}
          className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg p-2 text-xs text-[#f9f9f9] placeholder-[#4b5563] resize-none focus:outline-none focus:border-amber-500/50" />
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <p className="text-xs text-[#6b7280] mb-1">Completed by</p>
          <input value={feedback.completed_by}
            onChange={e => onChange({ ...feedback, completed_by: e.target.value })}
            placeholder="Technician name"
            className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg px-2 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50" />
        </div>
        <div className="w-28">
          <p className="text-xs text-[#6b7280] mb-1">Actual duration (h)</p>
          <input type="number" value={feedback.actual_duration_hours}
            onChange={e => onChange({ ...feedback, actual_duration_hours: e.target.value })}
            placeholder="e.g. 9.5"
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
        {wo.solution_worked === true && <span className="text-xs text-emerald-400 flex items-center gap-1"><ThumbsUp size={11} /> Solution worked</span>}
        {wo.solution_worked === false && <span className="text-xs text-red-400 flex items-center gap-1"><ThumbsDown size={11} /> Solution did not work</span>}
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

// ── Markdown renderer (no external dep) ──────────────────────────────────────

function inlineFmt(text: string): React.ReactNode[] {
  // Split on **bold**, *italic*, `code`
  const parts = text.split(/(\*\*(?:[^*]|\*(?!\*))+\*\*|\*[^*]+\*|`[^`]+`)/);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4)
      return <strong key={i} className="font-semibold text-[#f0f0f0]">{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2)
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2)
      return <code key={i} className="bg-[#2a2a2a] rounded px-1 font-mono text-amber-400 text-[10px]">{part.slice(1, -1)}</code>;
    return part;
  });
}

function MdText({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let k = 0;
  let olItems: string[] = [];
  let ulItems: string[] = [];

  const flushOl = () => {
    if (!olItems.length) return;
    blocks.push(
      <ol key={k++} className="list-decimal list-inside space-y-0.5 pl-1">
        {olItems.map((t, i) => <li key={i}>{inlineFmt(t)}</li>)}
      </ol>
    );
    olItems = [];
  };
  const flushUl = () => {
    if (!ulItems.length) return;
    blocks.push(
      <ul key={k++} className="list-disc list-inside space-y-0.5 pl-1">
        {ulItems.map((t, i) => <li key={i}>{inlineFmt(t)}</li>)}
      </ul>
    );
    ulItems = [];
  };

  for (const raw of text.split("\n")) {
    const t = raw.trim();
    const olM = t.match(/^\d+\.\s+(.*)/);
    const ulM = t.match(/^[-*]\s+(.*)/);
    const hM  = t.match(/^#{1,3}\s+(.*)/);

    if (olM) { flushUl(); olItems.push(olM[1]); continue; }
    if (ulM) { flushOl(); ulItems.push(ulM[1]); continue; }

    flushOl(); flushUl();

    if (!t)  { blocks.push(<div key={k++} className="h-1" />); continue; }
    if (hM)  { blocks.push(<p key={k++} className="font-semibold text-[#e8e8e8] mt-1">{inlineFmt(hM[1])}</p>); continue; }
    blocks.push(<p key={k++}>{inlineFmt(t)}</p>);
  }
  flushOl(); flushUl();

  return <div className="space-y-1">{blocks}</div>;
}

// ── AI chat panel ─────────────────────────────────────────────────────────────

type AIChatMsg = {
  role: "user" | "assistant";
  content: string;
  proposedChanges?: OpsProposedChanges | null;
  applied?: boolean;
};

function AIOpsChat({
  itemId, itemType, onApply,
}: {
  itemId: string;
  itemType: "work_order" | "checklist";
  onApply: () => void;
}) {
  const [msgs, setMsgs] = useState<AIChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    const prevMsgs = msgs;
    setMsgs(prev => [...prev, { role: "user", content: text }]);
    setLoading(true);
    const history = prevMsgs.map(m => ({ role: m.role, content: m.content }));
    try {
      const fn = itemType === "work_order" ? chatWithWorkOrder : chatWithChecklist;
      const res = await fn(itemId, { message: text, history });
      setMsgs(prev => [...prev, { role: "assistant", content: res.answer, proposedChanges: res.proposed_changes }]);
    } catch {
      setMsgs(prev => [...prev, { role: "assistant", content: "Error contacting AI. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  const applyChanges = async (changes: OpsProposedChanges, idx: number) => {
    setApplying(true);
    try {
      if (itemType === "work_order") {
        if (changes.description || changes.risk_level) {
          await updateWorkOrder(itemId, {
            ...(changes.description && { description: changes.description }),
            ...(changes.risk_level  && { risk_level:  changes.risk_level  }),
          });
        }
        if (changes.toggle_steps?.length) {
          await Promise.all(
            changes.toggle_steps.map(t =>
              updateWorkOrderStep(itemId, { step_index: t.step_index, checked: t.checked, actual_notes: "" })
            )
          );
        }
        if (changes.add_steps?.length) await addWorkOrderSteps(itemId, changes.add_steps);
      } else {
        if (changes.description || changes.risk_level) {
          await updateChecklist(itemId, {
            ...(changes.description && { query_text: changes.description }),
            ...(changes.risk_level  && { risk_level: changes.risk_level  }),
          });
        }
        if (changes.toggle_items?.length) {
          await Promise.all(
            changes.toggle_items.map(t =>
              updateChecklistItem(itemId, { index: t.index, checked: t.checked, notes: "" })
            )
          );
        }
        if (changes.add_items?.length) await addChecklistItems(itemId, changes.add_items);
      }
      setMsgs(prev => prev.map((m, i) => i === idx ? { ...m, applied: true } : m));
      onApply();
    } catch { /* ignore */ }
    finally { setApplying(false); }
  };

  return (
    <div className="border-t border-[#1a1a1a] bg-[#131313]">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#1e1e1e]">
        <Brain size={12} className="text-purple-400" />
        <span className="text-xs font-semibold text-[#a0a0a0]">AI Assistant</span>
        <span className="text-xs text-[#4b5563]">· ask anything · request changes</span>
      </div>

      {msgs.length > 0 && (
        <div className="px-4 pt-3 pb-1 space-y-3 max-h-64 overflow-y-auto">
          {msgs.map((msg, i) => (
            <div key={i} className={clsx("flex gap-2", msg.role === "user" && "flex-row-reverse")}>
              <div className={clsx(
                "max-w-[88%] rounded-xl px-3 py-2 text-xs leading-relaxed",
                msg.role === "user"
                  ? "bg-purple-500/20 border border-purple-500/30 text-[#f9f9f9]"
                  : "bg-[#1c1c1c] border border-[#2a2a2a] text-[#d0d0d0]",
              )}>
                <p className="whitespace-pre-wrap">{msg.role === "user" ? msg.content : ""}</p>
                {msg.role === "assistant" && <MdText text={msg.content} />}

                {msg.role === "assistant" && msg.proposedChanges && !msg.applied && (
                  <div className="mt-2.5 pt-2 border-t border-[#333] space-y-1.5">
                    <p className="text-[11px] font-semibold text-purple-400">Proposed changes</p>
                    <div className="space-y-0.5 text-[11px] text-[#a0a0a0]">
                      {msg.proposedChanges.description && <p>• Update description</p>}
                      {msg.proposedChanges.risk_level && (
                        <p>• Risk level → <span className="text-amber-400">{msg.proposedChanges.risk_level}</span></p>
                      )}
                      {msg.proposedChanges.toggle_items?.map((t, j) => (
                        <p key={j}>• {t.checked ? "✓ Check" : "○ Uncheck"} item #{t.index + 1}</p>
                      ))}
                      {msg.proposedChanges.toggle_steps?.map((t, j) => (
                        <p key={j}>• {t.checked ? "✓ Check" : "○ Uncheck"} step #{t.step_index + 1}</p>
                      ))}
                      {msg.proposedChanges.add_items?.map((item, j) => (
                        <p key={j}>• Add item: <span className="text-[#f9f9f9]">&ldquo;{item}&rdquo;</span></p>
                      ))}
                      {msg.proposedChanges.add_steps?.map((step, j) => (
                        <p key={j}>• Add step: <span className="text-[#f9f9f9]">&ldquo;{step.title}&rdquo;</span></p>
                      ))}
                    </div>
                    <button
                      onClick={() => applyChanges(msg.proposedChanges!, i)}
                      disabled={applying}
                      className="mt-1 flex items-center gap-1 text-[11px] px-2.5 py-1 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg hover:bg-purple-500/30 transition-colors disabled:opacity-50"
                    >
                      {applying ? <Loader2 size={9} className="animate-spin" /> : <CheckCircle2 size={9} />}
                      Apply changes
                    </button>
                  </div>
                )}

                {msg.role === "assistant" && msg.applied && (
                  <p className="mt-1 text-[11px] text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 size={9} /> Changes applied
                  </p>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex gap-2">
              <div className="bg-[#1c1c1c] border border-[#2a2a2a] rounded-xl px-3 py-2.5">
                <Loader2 size={12} className="animate-spin text-purple-400" />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      <div className="flex gap-2 px-4 py-3">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={`Ask about this ${itemType === "work_order" ? "work order" : "checklist"}…`}
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-purple-500/50 transition-colors"
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          className="p-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg hover:bg-purple-500/30 transition-colors disabled:opacity-40"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

function WorkOrdersPageInner() {
  const searchParams = useSearchParams();
  const defaultTab = (searchParams.get("tab") as "checklists" | "work-orders") ?? "work-orders";
  const [tab, setTab] = useState<"checklists" | "work-orders">(defaultTab);
  const [workOrders, setWorkOrders] = useState<SavedWorkOrder[]>([]);
  const [checklists, setChecklists] = useState<SavedChecklist[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [wos, cls] = await Promise.all([
      listWorkOrders().catch(() => [] as SavedWorkOrder[]),
      listChecklists().catch(() => [] as SavedChecklist[]),
    ]);
    setWorkOrders(wos);
    setChecklists(cls);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCount = workOrders.filter(w => w.status !== "completed").length;
  const clOpenCount = checklists.filter(c => c.status !== "completed").length;

  return (
    <div className="p-6">
      <div className="mb-5">
        <h1 className="text-xl font-bold text-[#f9f9f9]">Work Orders & Checklists</h1>
        <p className="text-xs text-[#6b7280] mt-1 flex items-center gap-1">
          <Brain size={12} className="text-amber-400" />
          Completion feedback is stored in the knowledge base and improves future AI responses
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 p-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-fit">
        {([
          { key: "work-orders" as const, label: "Work Orders", icon: <Wrench size={13} />, count: openCount },
          { key: "checklists" as const, label: "Checklists", icon: <ClipboardList size={13} />, count: clOpenCount },
        ]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={clsx(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all",
              tab === t.key
                ? "bg-[#2a2a2a] text-[#f9f9f9] font-medium"
                : "text-[#6b7280] hover:text-[#a0a0a0]",
            )}>
            {t.icon} {t.label}
            {t.count > 0 && (
              <span className="px-1.5 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400 leading-none">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-[#6b7280] py-10">
          <Loader2 size={16} className="animate-spin" /> Loading…
        </div>
      ) : tab === "work-orders" ? (
        <div className="space-y-3">
          {workOrders.length === 0 ? (
            <EmptyState type="work-orders" />
          ) : workOrders.map(wo => (
            <WorkOrderDetailCard key={wo.id} wo={wo} onUpdate={load} onDelete={load} />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {checklists.length === 0 ? (
            <EmptyState type="checklists" />
          ) : checklists.map(cl => (
            <ChecklistCard key={cl.id} cl={cl} onUpdate={load} onDelete={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({ type }: { type: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-[#4b5563]">
      {type === "work-orders" ? <Wrench size={36} className="mb-3 opacity-40" /> : <ClipboardList size={36} className="mb-3 opacity-40" />}
      <p className="text-sm">No {type} yet</p>
      <p className="text-xs mt-1">Run an AI query and use "Save Work Order" or "Save to Work Orders" to create one</p>
      <a href="/query" className="mt-3 text-xs text-amber-400 hover:underline">→ Go to AI Query</a>
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
