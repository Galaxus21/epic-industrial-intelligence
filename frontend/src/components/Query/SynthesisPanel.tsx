/**
 * AI Operations Brain — Synthesis Panel
 * Renders the GPT-4.1 synthesized result: risk, causes, actions, checklist,
 * lessons learned, compliance, work order, and sources with attribution.
 */
"use client";

import { useState, useEffect } from "react";
import type { SynthesisResult, QuerySourceType } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DocumentModal } from "@/components/ui/DocumentModal";
import { WorkOrderCard } from "@/components/Query/WorkOrderCard";
import { createChecklist, createWorkOrder } from "@/lib/api";
import { toast } from "sonner";
import {
  AlertTriangle, CheckCircle2, ClipboardList, History, ShieldCheck,
  Wrench, BookOpen, ChevronRight, FileText, Upload, Database,
  Cpu, ClipboardCheck, ExternalLink, Save, Loader2,
} from "lucide-react";
import clsx from "clsx";

interface SynthesisPanelProps {
  result: SynthesisResult;
  equipmentId: string;
}

// ── Source type config ────────────────────────────────────────────────────────

const SOURCE_CONFIG: Record<QuerySourceType, {
  label: string;
  icon: React.ReactNode;
  badge: string;
  bg: string;
  border: string;
  text: string;
  clickable: boolean;
}> = {
  uploaded_doc: {
    label: "Uploaded Material",
    icon: <Upload size={11} />,
    badge: "bg-sky-500/15 text-sky-400 border-sky-500/30",
    bg: "bg-sky-500/5",
    border: "border-sky-500/20",
    text: "text-sky-400",
    clickable: true,
  },
  knowledge_base: {
    label: "Knowledge Base",
    icon: <Database size={11} />,
    badge: "bg-purple-500/15 text-purple-400 border-purple-500/30",
    bg: "bg-purple-500/5",
    border: "border-purple-500/20",
    text: "text-purple-400",
    clickable: true,
  },
  incident_history: {
    label: "Incident History",
    icon: <ClipboardCheck size={11} />,
    badge: "bg-orange-500/15 text-orange-400 border-orange-500/30",
    bg: "bg-orange-500/5",
    border: "border-orange-500/20",
    text: "text-orange-400",
    clickable: false,
  },
  maintenance_record: {
    label: "Maintenance Record",
    icon: <Wrench size={11} />,
    badge: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    bg: "bg-blue-500/5",
    border: "border-blue-500/20",
    text: "text-blue-400",
    clickable: false,
  },
  ai_inference: {
    label: "AI Inference",
    icon: <Cpu size={11} />,
    badge: "bg-[#2a2a2a] text-[#6b7280] border-[#333]",
    bg: "bg-[#1a1a1a]",
    border: "border-[#2a2a2a]",
    text: "text-[#6b7280]",
    clickable: false,
  },
  feedback: {
    label: "Work Order Feedback",
    icon: <ClipboardCheck size={11} />,
    badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
    bg: "bg-emerald-500/5",
    border: "border-emerald-500/20",
    text: "text-emerald-400",
    clickable: true,
  },
};

const RISK_CONFIG = {
  Critical: { variant: "critical" as const, bg: "bg-red-500/10 border-red-500/30", icon: "🔴" },
  High:     { variant: "high" as const,     bg: "bg-orange-500/10 border-orange-500/30", icon: "🟠" },
  Medium:   { variant: "medium" as const,   bg: "bg-amber-500/10 border-amber-500/30", icon: "🟡" },
  Low:      { variant: "low" as const,      bg: "bg-emerald-500/10 border-emerald-500/30", icon: "🟢" },
};

// ── Typewriter hook ──────────────────────────────────────────────────────────────────

function useTypewriter(text: string, charsPerFrame = 5): string {
  const [displayed, setDisplayed] = useState("");
  useEffect(() => {
    setDisplayed("");
    let pos = 0;
    let raf: number;
    const step = () => {
      pos = Math.min(pos + charsPerFrame, text.length);
      setDisplayed(text.slice(0, pos));
      if (pos < text.length) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [text, charsPerFrame]);
  return displayed;
}

// ── Inline markdown formatter (handles **bold**) ───────────────────────────

function fmt(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i} className="font-semibold text-[#e8e8e8]">{part.slice(2, -2)}</strong>
      : part
  );
}

// ── Staggered reveal wrapper ───────────────────────────────────────────────────

function RevealSection({ delay, children }: { delay: number; children: React.ReactNode }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(t);
  }, [delay]);
  return (
    <div className={clsx(
      "transition-all duration-500 ease-out",
      visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2",
    )}>
      {children}
    </div>
  );
}

export function SynthesisPanel({ result, equipmentId }: SynthesisPanelProps) {
  const riskCfg = RISK_CONFIG[result.risk_level] ?? RISK_CONFIG.Medium;
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [savingCL, setSavingCL] = useState(false);
  const [savedCLId, setSavedCLId] = useState<string | null>(null);
  const [savingWO, setSavingWO] = useState(false);
  const [savedWOId, setSavedWOId] = useState<string | null>(null);
  const riskSummary  = useTypewriter(result.risk_summary, 5);
  const isTyping     = riskSummary.length < result.risk_summary.length;

  const handleSaveChecklist = async () => {
    if (result.ai_available === false) {
      toast.error("Cannot save checklist generated in degraded mode");
      return;
    }
    if (result.inspection_checklist.length === 0) return;
    setSavingCL(true);
    try {
      const cl = await createChecklist({
        equipment_id: equipmentId,
        query_text: result.risk_summary,
        risk_level: result.risk_level,
        items: result.inspection_checklist,
      });
      setSavedCLId(cl.id);
      toast.success("Checklist saved");
    } catch (err: unknown) {
      const apiErr = err as { status?: number; message?: string };
      toast.error(apiErr?.status === 403 ? "Your role cannot do this" : (apiErr?.message || "Failed to save checklist"));
    } finally {
      setSavingCL(false);
    }
  };

  const handleSaveWorkOrder = async () => {
    if (result.ai_available === false) {
      toast.error("Cannot save work order generated in degraded mode");
      return;
    }
    if (!result.work_order) return;
    setSavingWO(true);
    try {
      const wo = await createWorkOrder({
        equipment_id: equipmentId,
        query_text: result.risk_summary,
        risk_level: result.risk_level,
        wo_type: result.work_order.type,
        description: result.work_order.description,
        estimated_duration_hours: result.work_order.estimated_duration_hours,
        required_technicians: result.work_order.required_technicians,
        steps: result.work_order.procedure_steps ?? [],
        spare_parts: result.work_order.spare_parts,
        safety_precautions: result.work_order.safety_precautions,
        required_permits: result.required_permits ?? [],
      });
      setSavedWOId(wo.id);
      toast.success("Work order saved");
    } catch (err: unknown) {
      const apiErr = err as { status?: number; message?: string };
      toast.error(apiErr?.status === 403 ? "Your role cannot do this" : (apiErr?.message || "Failed to save work order"));
    } finally {
      setSavingWO(false);
    }
  };

  return (
  <>
    <div className="space-y-4 p-4">
      {/* Risk Banner */}
      <RevealSection delay={0}>
      <div className={clsx("flex items-start gap-3 p-4 rounded-xl border", riskCfg.bg)}>
        <span className="text-2xl">{riskCfg.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant={riskCfg.variant}>{result.risk_level} Risk</Badge>
            <span className="text-xs text-[#6b7280]">Equipment {equipmentId}</span>
          </div>
          <p className="text-sm text-[#f9f9f9] font-medium leading-relaxed">
            {riskSummary}
            {isTyping && (
              <span className="inline-block w-0.5 h-3.5 bg-[#f9f9f9]/70 ml-0.5 animate-pulse align-middle rounded-sm" />
            )}
          </p>
          <p className="text-xs text-[#a0a0a0] mt-1.5 leading-relaxed">{fmt(result.explanation ?? "")}</p>
        </div>
      </div>
      </RevealSection>

      {/* Predicted Failure Window */}
      {result.predicted_failure_window && (
        <RevealSection delay={300}>
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg">
          <AlertTriangle size={14} className="text-orange-400 flex-shrink-0" />
          <p className="text-xs text-[#a0a0a0]">
            <span className="text-orange-400 font-semibold">Predicted failure: </span>
            {result.predicted_failure_window}
          </p>
        </div>
        </RevealSection>
      )}

      {/* 2-column layout */}
      <RevealSection delay={480}>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Probable Causes */}
        <Section icon={<AlertTriangle size={14} className="text-orange-400" />} title="Probable Causes">
          {result.probable_causes.map((cause, i) => (
            <div key={i} className="flex items-start gap-3 py-2 border-b border-[#2a2a2a] last:border-0">
              <div className="flex-shrink-0 w-10 text-center">
                <span
                  className="text-sm font-bold"
                  style={{ color: cause.probability >= 60 ? "#f97316" : "#f59e0b" }}
                  title={`Probability: ${cause.probability}% — likelihood this is the root cause based on available evidence`}
                >
                  {cause.probability}%
                </span>
                <div
                  className="h-1 bg-[#2a2a2a] rounded-full mt-1 overflow-hidden"
                  title={`${cause.probability}% probability`}
                >
                  <div className="h-full rounded-full" style={{ width: `${cause.probability}%`, background: cause.probability >= 60 ? "#f97316" : "#f59e0b" }} />
                </div>
              </div>
              <div>
                <p className="text-xs text-[#f9f9f9]">{cause.cause}</p>
                <p className="text-xs text-[#6b7280] mt-0.5">{cause.evidence}</p>
              </div>
            </div>
          ))}
        </Section>

        {/* Immediate Actions */}
        <Section icon={<CheckCircle2 size={14} className="text-emerald-400" />} title="Immediate Actions">
          {result.immediate_actions.map((action, i) => (
            <div key={i} className="flex items-start gap-2 py-2 border-b border-[#2a2a2a] last:border-0">
              <span
              className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-[#2a2a2a] text-xs font-bold text-[#a0a0a0]"
              title={`Priority ${action.priority} — address in this order`}
            >{action.priority}</span>
              <div className="flex-1">
                <p className="text-xs text-[#f9f9f9]">{action.action}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span
                    className={clsx("text-xs font-semibold", action.timeframe === "immediately" ? "text-red-400" : action.timeframe.includes("1h") ? "text-orange-400" : "text-amber-400")}
                    title={`Required timing: ${action.timeframe}`}
                  >
                    ⏱ {action.timeframe}
                  </span>
                  <span className="text-xs text-[#6b7280]">→ {action.owner}</span>
                </div>
              </div>
            </div>
          ))}
        </Section>

        {/* Similar Incidents */}
        {result.similar_incidents.length > 0 && (
          <Section icon={<History size={14} className="text-amber-400" />} title="Historical Pattern Match">
            {result.similar_incidents.map((inc, i) => (
              <div key={i} className="py-2 border-b border-[#2a2a2a] last:border-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-[#6b7280]">{inc.incident_id}</span>
                  <span className="text-xs text-[#6b7280]">{inc.date}</span>
                  <span
                    className="ml-auto text-xs font-semibold text-amber-400"
                    title={`${inc.similarity_score}% similarity to current situation — based on symptom pattern matching across incident history`}
                  >
                    {inc.similarity_score}% match
                  </span>
                </div>
                <p className="text-xs text-[#a0a0a0]">{inc.lesson}</p>
              </div>
            ))}
          </Section>
        )}

        {/* Compliance Issues */}
        {result.compliance_issues.length > 0 && (
          <Section icon={<ShieldCheck size={14} className="text-red-400" />} title="Compliance Issues">
            {result.compliance_issues.map((issue, i) => (
              <div key={i} className="flex items-start gap-2 py-2 border-b border-[#2a2a2a] last:border-0">
                <Badge variant={issue.severity === "High" ? "high" : issue.severity === "Medium" ? "medium" : "low"}>
                  {issue.severity}
                </Badge>
                <div>
                  <p className="text-xs text-amber-400 font-medium">{issue.regulation}</p>
                  <p className="text-xs text-[#a0a0a0] mt-0.5">{issue.issue}</p>
                </div>
              </div>
            ))}
          </Section>
        )}
      </div>
      </RevealSection>

      {/* Inspection Checklist */}
      {result.inspection_checklist.length > 0 && (
        <RevealSection delay={660}>
        <Section
          icon={<ClipboardList size={14} className="text-blue-400" />}
          title="Inspection Checklist"
          action={
            result.ai_available === false ? (
              <span className="text-xs text-[#6b7280]">AI unavailable</span>
            ) : savedCLId ? (
              <a href="/work-orders?tab=checklists" className="text-xs text-emerald-400 hover:underline flex items-center gap-1">
                <CheckCircle2 size={11} /> Saved · {savedCLId}
              </a>
            ) : (
              <button
                onClick={handleSaveChecklist}
                disabled={savingCL}
                className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
                title="Save this checklist to Work Orders so a technician can execute it step by step"
              >
                {savingCL ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                Save to Work Orders
              </button>
            )
          }
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
            {result.inspection_checklist.map((item, i) => (
              <div key={i} className="flex items-start gap-2 py-1">
                <span className="text-xs text-[#2a2a2a] border border-[#333] rounded w-4 h-4 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-[#a0a0a0]">{item}</p>
              </div>
            ))}
          </div>
        </Section>
        </RevealSection>
      )}

      {/* Work Order */}
      {result.work_order && (
        <RevealSection delay={840}>
        <div>
          <div className="flex items-center justify-end mb-1.5">
            {result.ai_available === false ? (
              <span className="text-xs text-[#6b7280]">AI unavailable</span>
            ) : savedWOId ? (
              <a href={`/work-orders?tab=work-orders&id=${savedWOId}`} className="text-xs text-emerald-400 hover:underline flex items-center gap-1">
                <CheckCircle2 size={11} /> Saved · {savedWOId} — Open in Work Orders →
              </a>
            ) : (
              <button
                onClick={handleSaveWorkOrder}
                disabled={savingWO}
                className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors disabled:opacity-50"
                title="Save this work order so a technician can execute it with step-by-step tracking"
              >
                {savingWO ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
                Save Work Order
              </button>
            )}
          </div>
          <WorkOrderCard
            workOrder={result.work_order}
            requiredPermits={result.required_permits ?? []}
            equipmentId={equipmentId}
          />
        </div>
        </RevealSection>
      )}

      {/* Sources */}
      {result.sources.length > 0 && (
        <RevealSection delay={1000}>
        <Section icon={<BookOpen size={14} className="text-[#6b7280]" />} title="Evidence Sources">
          {/* Group summary bar */}
          <div className="flex flex-wrap gap-2 mb-3 pb-3 border-b border-[#2a2a2a]">
            {(["uploaded_doc", "knowledge_base", "incident_history", "maintenance_record", "ai_inference", "feedback"] as QuerySourceType[]).map(type => {
              const count = result.sources.filter(s => (s.source_type ?? "knowledge_base") === type).length;
              if (count === 0) return null;
              const cfg = SOURCE_CONFIG[type] ?? SOURCE_CONFIG.knowledge_base;
              return (
                <span key={type} className={clsx("flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border", cfg.badge)}>
                  {cfg.icon} {cfg.label} · {count}
                </span>
              );
            })}
          </div>
          <div className="space-y-2">
            {result.sources.map((source, i) => {
              const type: QuerySourceType = (source.source_type as QuerySourceType) ?? "knowledge_base";
              const cfg = SOURCE_CONFIG[type] ?? SOURCE_CONFIG.knowledge_base;
              const isClickable = cfg.clickable && !!source.doc_id;
              return (
                <div
                  key={i}
                  className={clsx(
                    "flex items-start gap-3 p-3 rounded-lg border transition-all",
                    cfg.bg, cfg.border,
                    isClickable && "cursor-pointer hover:brightness-125",
                  )}
                  onClick={isClickable ? () => setSelectedDocId(source.doc_id!) : undefined}
                >
                  {/* Source type icon */}
                  <span className={clsx("flex-shrink-0 mt-0.5", cfg.text)}>{cfg.icon}</span>

                  <div className="flex-1 min-w-0">
                    {/* Header row */}
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <span className={clsx("text-xs font-semibold truncate max-w-xs", cfg.text)}>
                        {source.document}
                      </span>
                      <span className={clsx("text-xs px-1.5 py-0.5 rounded border flex items-center gap-1", cfg.badge)}>
                        {cfg.icon} {cfg.label}
                      </span>
                      {isClickable && (
                        <span className={clsx("text-xs flex items-center gap-0.5", cfg.text)}>
                          <ExternalLink size={10} /> view
                        </span>
                      )}
                      {source.doc_id && (
                        <span className="text-xs text-[#4b5563] font-mono">{source.doc_id}</span>
                      )}
                    </div>

                    {/* Section */}
                    <p className="text-xs text-[#6b7280]">{source.section}</p>

                    {/* Excerpt */}
                    {source.excerpt && (
                      <p className="text-xs text-[#5a5a6a] mt-1.5 italic leading-relaxed border-l-2 border-[#333] pl-2">
                        &ldquo;{source.excerpt.substring(0, 140)}{source.excerpt.length > 140 ? "…" : ""}&rdquo;
                      </p>
                    )}
                  </div>

                  {/* Confidence */}
                  <div className="flex-shrink-0 flex flex-col items-end gap-1">
                    <span
                      className={clsx(
                        "text-xs font-bold px-1.5 py-0.5 rounded",
                        source.confidence >= 85 ? "bg-emerald-500/20 text-emerald-400" :
                        source.confidence >= 65 ? "bg-amber-500/20 text-amber-400" :
                                                 "bg-[#2a2a2a] text-[#6b7280]",
                      )}
                      title={`AI confidence: ${source.confidence}% — how relevant this source is to the current query`}
                    >
                      {source.confidence}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
        </RevealSection>
      )}
    </div>

    <DocumentModal docId={selectedDocId} onClose={() => setSelectedDocId(null)} />
  </>
  );
}

function Section({ icon, title, action, children }: {
  icon: React.ReactNode; title: string;
  action?: React.ReactNode; children: React.ReactNode
}) {
  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold text-[#a0a0a0]">{title}</h3>
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </div>
  );
}
