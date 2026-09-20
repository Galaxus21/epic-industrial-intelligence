/**
 * EPIC — Chat-style Query Interface
 * Stateful session: carries conversation history through each multi-agent query.
 * Layout: sticky header (equipment selector) · scrollable chat thread · sticky input.
 */
"use client";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { streamAgentQuery, listEquipment, getEquipment, createChecklist, createWorkOrder } from "@/lib/api";
import { AgentPanel } from "./AgentPanel";
import { SynthesisPanel } from "./SynthesisPanel";
import { WorkOrderCard } from "./WorkOrderCard";
import { Badge } from "@/components/ui/Badge";
import type { AgentEvent, SynthesisResult, Equipment, SessionTurn } from "@/lib/types";
import { usePageState } from "@/lib/page-state";
import {
  BrainCircuit, Send, Mic, Loader2, ChevronDown, ChevronUp, Trash2,
  AlertTriangle, ClipboardList, Wrench, Save, CheckCircle2, Activity,
} from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import { toast } from "sonner";
import { formatSensorLabel, isSensorInAlarm, getSensorColor } from "@/lib/sensor-utils";

function SensorStrip({ equipment, onQuery }: { equipment: Equipment; onQuery: (q: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const readings = equipment.current_readings;
  if (!readings || Object.keys(readings).length === 0) return null;

  const entries = Object.entries(readings) as [string, { value: number; unit: string; normal?: number; alarm?: number; trip?: number; alarm_direction?: string }][];
  const alarmCount = entries.filter(([, r]) => isSensorInAlarm(r)).length;

  return (
    <div className="flex-shrink-0 border-b border-[#1e1e1e] bg-[#080808]">
      {/* Compact chip row */}
      <div className="flex items-center gap-2 px-3 sm:px-4 py-1.5 overflow-x-auto scrollbar-hide">
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1.5 flex-shrink-0 min-h-[44px] px-2.5 text-[11px] font-semibold uppercase tracking-wider text-[#6b7280] hover:text-[#f9f9f9] transition-colors"
        >
          <Activity size={12} />
          <span>Sensors</span>
          {alarmCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-400 text-[10px]">
              {alarmCount} ⚠
            </span>
          )}
          {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        </button>

        {entries.map(([key, r]) => {
          const color = getSensorColor(r);
          const isAlarm = isSensorInAlarm(r);
          return (
            <button
              key={key}
              onClick={() => onQuery(`${equipment.id}: ${formatSensorLabel(key)} is ${r.value} ${r.unit}${isAlarm ? " — IN ALARM" : ""}. Is this a concern?`)}
              title={`Click to ask AI about this reading`}
              className="flex items-center gap-1.5 flex-shrink-0 min-h-[44px] px-3 py-1.5 rounded-xl bg-[#111] border border-[#1e1e1e] hover:border-amber-500/25 transition-colors"
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
              <span className="text-[10px] text-[#8b949e] whitespace-nowrap">{formatSensorLabel(key)}</span>
              <span className="text-xs font-mono font-semibold whitespace-nowrap" style={{ color }}>{r.value}</span>
              <span className="text-[10px] text-[#555]">{r.unit}</span>
            </button>
          );
        })}
      </div>

      {/* Expanded detail grid */}
      {expanded && (
        <div className="px-4 pb-3 pt-1 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {entries.map(([key, r]) => {
            const color = getSensorColor(r);
            const max = r.trip ?? (r.alarm ? r.alarm * 1.5 : (r.normal ?? 10) * 2);
            const pct = Math.min(100, (r.value / max) * 100);
            const alarmPct = r.alarm ? (r.alarm / max) * 100 : null;
            const isAlarm = isSensorInAlarm(r);
            return (
              <button
                key={key}
                onClick={() => onQuery(`${equipment.id}: ${formatSensorLabel(key)} is ${r.value} ${r.unit}${isAlarm ? " — IN ALARM" : ""}. Is this a concern?`)}
                className={clsx(
                  "text-left p-2.5 rounded-xl border transition-colors hover:border-amber-500/20",
                  isAlarm ? "bg-orange-500/5 border-orange-500/20" : "bg-[#0f0f0f] border-[#1e1e1e]"
                )}
              >
                <p className="text-[9px] text-[#8b949e] mb-1 truncate">{formatSensorLabel(key)}</p>
                <div className="flex items-baseline gap-0.5">
                  <span className="text-sm font-bold font-mono" style={{ color }}>{r.value}</span>
                  <span className="text-[9px] text-[#333]">{r.unit}</span>
                </div>
                <div className="relative h-0.5 bg-[#252525] rounded-full mt-1.5 overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                  {alarmPct !== null && (
                    <div className="absolute top-0 h-full w-px bg-orange-500/60" style={{ left: `${alarmPct}%` }} />
                  )}
                </div>
                {r.alarm !== undefined && (
                  <p className="text-[8px] text-[#2e2e2e] mt-0.5">alarm {r.alarm}</p>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Context-aware query suggestion generator ─────────────────────────────────

function buildSuggestions(eq: Equipment | null): string[] {
  if (!eq) return [];
  const suggestions: string[] = [];
  const typeL = eq.type.toLowerCase();

  // State-specific first — most actionable
  if (eq.status?.toLowerCase().includes("alert") || eq.status?.toLowerCase().includes("alarm"))
    suggestions.push(`${eq.id} has an active alert (${eq.status}) — can I continue operating and what needs to be done?`);

  if (eq.health_score != null && eq.health_score < 75)
    suggestions.push(`Health score is ${eq.health_score}% — what are the likely causes and what should I inspect?`);

  if (eq.failure_probability != null && eq.failure_probability > 20)
    suggestions.push(`Failure probability is ${eq.failure_probability}% — what are the immediate risks and required actions?`);

  if (eq.maintenance_due_days != null && eq.maintenance_due_days <= 14) {
    const urgency = eq.maintenance_due_days <= 0 ? "overdue" : `due in ${eq.maintenance_due_days} day${eq.maintenance_due_days !== 1 ? "s" : ""}`;
    suggestions.push(`Maintenance is ${urgency} — what tasks are required and what is the priority?`);
  }

  if (eq.compliance_score != null && eq.compliance_score < 90)
    suggestions.push(`Compliance score is ${eq.compliance_score}% — what regulations need attention?`);

  // Equipment-type suggestions to fill remaining slots
  if (suggestions.length < 3) {
    if (typeL.includes("pump")) {
      suggestions.push(`${eq.id} is showing signs of vibration or cavitation — what are the risks?`);
      suggestions.push(`Check seal integrity and flag any compliance gaps for ${eq.id}.`);
    } else if (typeL.includes("compressor")) {
      suggestions.push(`Discharge pressure on ${eq.id} has dropped — can I keep running?`);
      suggestions.push(`Review lube oil temperature trends for ${eq.id} and flag any anomalies.`);
    } else if (typeL.includes("heat") || typeL.includes("exchanger")) {
      suggestions.push(`Outlet temperature on ${eq.id} has dropped — is fouling the cause?`);
      suggestions.push(`What is the thermal efficiency of ${eq.id} vs. design spec?`);
    } else if (typeL.includes("vessel") || typeL.includes("drum") || typeL.includes("tank")) {
      suggestions.push(`Level on ${eq.id} is fluctuating — what are the likely causes?`);
      suggestions.push(`Is ${eq.id} operating within its design pressure envelope?`);
    } else {
      suggestions.push(`Are there any anomalies or risks with ${eq.id} under current conditions?`);
      suggestions.push(`Are there compliance issues or overdue maintenance tasks for ${eq.id}?`);
    }
  }

  suggestions.push(`Generate a work order for inspection and maintenance of ${eq.id}.`);
  return suggestions.slice(0, 4);
}

// ── Compact agent progress bar (per turn) ─────────────────────────────────────

const AGENT_SHORT: Record<string, string> = {
  equipment_brain: "Brain",
  maintenance_advisor: "Maint.",
  compliance_agent: "Compl.",
  lessons_learned: "Lessons",
  document_intelligence: "Docs",
  synthesizer: "Synth.",
};
const AGENT_ORDER_KEYS = Object.keys(AGENT_SHORT);

function AgentStatusRow({ turn }: { turn: SessionTurn }) {
  const [expanded, setExpanded] = useState(false);
  const done  = turn.agentEvents.filter(e => e.status === "done").length;
  const total = AGENT_ORDER_KEYS.length;
  const active = turn.agentEvents.find(e => e.status === "active");

  return (
    <div className="flex justify-center my-2">
      <div className="w-full max-w-3xl">
        <button
          onClick={() => setExpanded(x => !x)}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse agent execution details" : "Expand agent execution details"}
          className="w-full flex items-center gap-3 px-3 py-1.5 bg-[#181818] border border-[#252525] rounded-lg hover:border-[#333] transition-colors"
        >
          {/* Progress segments */}
          <div className="flex items-center gap-0.5 flex-1">
            {AGENT_ORDER_KEYS.map(key => {
              const ev = turn.agentEvents.find(e => e.agent === key);
              const agentName = AGENT_SHORT[key] ?? key;
              return (
                <div
                  key={key}
                  title={!ev ? `${agentName} — waiting` : ev.status === "done" ? `${agentName} — done` : `${agentName} — running…`}
                  className={clsx(
                    "h-1 flex-1 rounded-full transition-all duration-300",
                    !ev             ? "bg-[#252525]" :
                    ev.status === "done"   ? "bg-emerald-500" :
                                            "bg-amber-400 animate-pulse",
                  )}
                />
              );
            })}
          </div>
          <span className="text-[10px] text-[#6b7280] flex-shrink-0 min-w-[100px] text-right">
            {turn.isRunning
              ? (active ? AGENT_SHORT[active.agent] ?? "…" : "Starting…")
              : `${done}/${total} agents${turn.elapsed ? " · " + (turn.elapsed / 1000).toFixed(1) + "s" : ""}`
            }
          </span>
          {expanded
            ? <ChevronUp size={10} className="text-[#4b5563] flex-shrink-0" />
            : <ChevronDown size={10} className="text-[#4b5563] flex-shrink-0" />}
        </button>
        {expanded && (
          <div className="mt-1 px-4 py-3 bg-[#141414] border border-[#252525] rounded-lg">
            <AgentPanel events={turn.agentEvents} isRunning={turn.isRunning} />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Inline helpers ────────────────────────────────────────────────────────────

function renderInlineMarkdown(text: string): React.ReactNode[] {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g);
  return tokens.map((token, i) => {
    if (token.startsWith("`") && token.endsWith("`") && token.length >= 2) {
      return (
        <code key={i} className="px-1.5 py-0.5 rounded bg-[#252525] text-amber-300 font-mono text-xs">
          {token.slice(1, -1)}
        </code>
      );
    }
    if (token.startsWith("**") && token.endsWith("**") && token.length >= 4) {
      return (
        <strong key={i} className="font-semibold text-[#f0f0f0]">
          {token.slice(2, -2)}
        </strong>
      );
    }
    if (token.startsWith("*") && token.endsWith("*") && token.length >= 2) {
      return (
        <em key={i} className="italic text-[#d0d0d0]">
          {token.slice(1, -1)}
        </em>
      );
    }
    return token;
  });
}

function SafeMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: React.ReactNode[] = [];

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="list-disc pl-5 my-1.5 space-y-1">
          {listItems}
        </ul>
      );
      listItems = [];
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      listItems.push(
        <li key={`li-${idx}`} className="text-sm text-[#e0e0e0] leading-relaxed">
          {renderInlineMarkdown(trimmed.slice(2))}
        </li>
      );
    } else {
      flushList();
      if (trimmed.length > 0) {
        elements.push(
          <p key={`p-${idx}`} className="text-sm text-[#e0e0e0] leading-relaxed mb-1.5 last:mb-0">
            {renderInlineMarkdown(line)}
          </p>
        );
      }
    }
  });

  flushList();
  return <div className="space-y-1">{elements}</div>;
}

function ChatMessage({ message }: { message: string }) {
  const [displayed, setDisplayed] = useState("");
  const isTyping = displayed.length < message.length;
  useEffect(() => {
    setDisplayed("");
    let pos = 0;
    let raf: number;
    const step = () => {
      pos = Math.min(pos + 5, message.length);
      setDisplayed(message.slice(0, pos));
      if (pos < message.length) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [message]);
  return (
    <div className="bg-[#161616] border border-[#252525] rounded-2xl rounded-tl-md px-4 py-3">
      <SafeMarkdown content={displayed} />
      {isTyping && <span className="inline-block w-0.5 h-3.5 bg-[#e0e0e0]/60 ml-0.5 animate-pulse align-middle rounded-sm" />}
    </div>
  );
}

function fmtInline(text: string): React.ReactNode[] {
  return renderInlineMarkdown(text);
}

const RISK_STYLE: Record<string, { icon: string; variant: "critical"|"high"|"medium"|"low"; color: string }> = {
  Critical: { icon: "🔴", variant: "critical", color: "#ef4444" },
  High:     { icon: "🟠", variant: "high",     color: "#f97316" },
  Medium:   { icon: "🟡", variant: "medium",   color: "#f59e0b" },
  Low:      { icon: "🟢", variant: "low",      color: "#10b981" },
};

function ProseResponse({
  result, equipmentId, showFull, onToggleFull, woActive, onShowWO, clActive, onShowCL,
}: {
  result: SynthesisResult; equipmentId: string;
  showFull: boolean; onToggleFull: () => void;
  woActive: boolean; onShowWO: () => void;
  clActive: boolean; onShowCL: () => void;
}) {
  const [riskSummary, setRiskSummary] = useState("");
  const isTyping = riskSummary.length < result.risk_summary.length;
  const rStyle = RISK_STYLE[result.risk_level] ?? RISK_STYLE["Medium"];

  useEffect(() => {
    setRiskSummary("");
    let pos = 0;
    let raf: number;
    const step = () => {
      pos = Math.min(pos + 5, result.risk_summary.length);
      setRiskSummary(result.risk_summary.slice(0, pos));
      if (pos < result.risk_summary.length) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [result.risk_summary]);

  return (
    <div
      className="bg-[#161616] border border-[#252525] rounded-2xl rounded-tl-md p-4"
      style={{ borderLeftColor: rStyle.color, borderLeftWidth: "3px" }}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl flex-shrink-0 mt-0.5">{rStyle.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <Badge variant={rStyle.variant}>{result.risk_level} Risk</Badge>
            <span className="text-[10px] text-[#6b7280]">· {equipmentId}</span>
            {result.predicted_failure_window && (
              <span className="text-[10px] text-orange-400 flex items-center gap-1">
                <AlertTriangle size={9} className="flex-shrink-0" />
                {result.predicted_failure_window}
              </span>
            )}
          </div>
          <p className="text-sm text-[#f9f9f9] font-medium leading-relaxed">
            {riskSummary}
            {isTyping && <span className="inline-block w-0.5 h-3.5 bg-[#f9f9f9]/70 ml-0.5 animate-pulse align-middle rounded-sm" />}
          </p>
          {result.explanation && (
            <p className="text-xs text-[#a0a0a0] mt-1.5 leading-relaxed">{fmtInline(result.explanation)}</p>
          )}
        </div>
      </div>

      {result.immediate_actions.length > 0 && (
        <div className="mt-3 ml-9 border-l-2 border-[#252525] pl-3 space-y-1.5">
          {result.immediate_actions.slice(0, 3).map((action, i) => (
            <div key={i} className="flex items-start gap-2 text-xs">
              <span className="flex-shrink-0 text-[#4b5563] font-mono text-[10px] mt-0.5">{i + 1}.</span>
              <p className="flex-1 text-[#c0c0c0] leading-relaxed">{action.action}</p>
              <span className={clsx(
                "flex-shrink-0 text-[10px] font-medium whitespace-nowrap ml-1",
                action.timeframe === "immediately" ? "text-red-400" :
                action.timeframe?.includes("1h") ? "text-orange-400" : "text-amber-400/80"
              )}>{action.timeframe}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5 mt-3 ml-9 flex-wrap">
        <button onClick={onToggleFull} className={clsx(
          "text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1",
          showFull ? "bg-amber-500/15 border-amber-500/30 text-amber-400"
                   : "bg-[#1a1a1a] border-[#252525] text-[#6b7280] hover:border-amber-500/30 hover:text-amber-400"
        )}>
          {showFull ? <ChevronUp size={10} /> : <ChevronDown size={10} />} Full analysis
        </button>
        {result.inspection_checklist.length > 0 && (
          <button onClick={onShowCL} className={clsx(
            "text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1",
            clActive ? "bg-blue-500/15 border-blue-500/30 text-blue-400"
                     : "bg-[#1a1a1a] border-[#252525] text-[#6b7280] hover:border-blue-500/30 hover:text-blue-400"
          )}>
            <ClipboardList size={10} /> Checklist ({result.inspection_checklist.length})
          </button>
        )}
        {result.work_order && (
          <button onClick={onShowWO} className={clsx(
            "text-[11px] px-2.5 py-1 rounded-full border transition-colors flex items-center gap-1",
            woActive ? "bg-purple-500/15 border-purple-500/30 text-purple-400"
                     : "bg-[#1a1a1a] border-[#252525] text-[#6b7280] hover:border-purple-500/30 hover:text-purple-400"
          )}>
            <Wrench size={10} /> Work Order
          </button>
        )}
      </div>
    </div>
  );
}

function QuickChecklist({ result, equipmentId }: { result: SynthesisResult; equipmentId: string }) {
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const handleSave = async () => {
    setSaving(true);
    try {
      const cl = await createChecklist({
        equipment_id: equipmentId, query_text: result.risk_summary,
        risk_level: result.risk_level, items: result.inspection_checklist,
      });
      setSavedId(cl.id);
      toast.success("Checklist saved");
    } catch (err: any) {
      toast.error(err?.status === 403 ? "Your role cannot do this" : (err?.message || "Failed to save checklist"));
    } finally { setSaving(false); }
  };
  return (
    <div className="bg-[#161616] border border-[#1e1e1e] rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ClipboardList size={13} className="text-blue-400" />
          <span className="text-xs font-semibold text-[#a0a0a0]">Inspection Checklist</span>
          <span className="text-xs text-[#6b7280]">{result.inspection_checklist.length} items</span>
        </div>
        {savedId ? (
          <a href="/work-orders?tab=checklists" className="text-xs text-emerald-400 hover:underline flex items-center gap-1">
            <CheckCircle2 size={11} /> Saved · {savedId}
          </a>
        ) : (
          <button onClick={handleSave} disabled={saving || result.ai_available === false}
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors">
            {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
            Save Checklist
          </button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-1">
        {result.inspection_checklist.map((item, i) => (
          <div key={i} className="flex items-start gap-2 py-1">
            <span className="border border-[#333] rounded w-4 h-4 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-[#a0a0a0]">{item}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function QuickWorkOrder({ result, equipmentId }: { result: SynthesisResult; equipmentId: string }) {
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const wo = result.work_order;
  const handleSave = async () => {
    if (!wo || result.ai_available === false) return;
    setSaving(true);
    try {
      const saved = await createWorkOrder({
        equipment_id: equipmentId, query_text: result.risk_summary,
        risk_level: result.risk_level, wo_type: wo.type,
        description: wo.description,
        estimated_duration_hours: wo.estimated_duration_hours,
        required_technicians: wo.required_technicians,
        steps: wo.procedure_steps ?? [], spare_parts: wo.spare_parts,
        safety_precautions: wo.safety_precautions,
        required_permits: result.required_permits ?? [],
      });
      setSavedId(saved.id);
      toast.success("Work order saved");
    } catch (err: any) {
      toast.error(err?.status === 403 ? "Your role cannot do this" : (err?.message || "Failed to save work order"));
    } finally { setSaving(false); }
  };
  if (!wo || result.ai_available === false) return null;
  return (
    <div className="border border-[#1e1e1e] rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e1e] bg-[#0f0f0f]">
        <div className="flex items-center gap-2">
          <Wrench size={13} className="text-purple-400" />
          <span className="text-xs font-semibold text-[#a0a0a0]">Work Order</span>
          <span className="text-xs text-[#6b7280]">{wo.type}</span>
        </div>
        {savedId ? (
          <a href="/work-orders" className="text-xs text-emerald-400 hover:underline flex items-center gap-1">
            <CheckCircle2 size={11} /> Saved · {savedId}
          </a>
        ) : (
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 disabled:opacity-50 transition-colors">
            {saving ? <Loader2 size={11} className="animate-spin" /> : <Save size={11} />}
            Save Work Order
          </button>
        )}
      </div>
      <WorkOrderCard workOrder={wo} requiredPermits={result.required_permits ?? []} equipmentId={equipmentId} />
    </div>
  );
}

// ── Single conversation turn ──────────────────────────────────────────────────

function TurnView({ turn }: { turn: SessionTurn }) {
  const qL = turn.query.toLowerCase();
  const [showFull, setShowFull] = useState(
    qL.includes("analysis") || qL.includes("cause") || qL.includes("why") || qL.includes("diagnos")
  );
  const [showWO, setShowWO] = useState(
    qL.includes("work order") || qL.includes("generate") || qL.includes("repair") || qL.includes("maintenance plan")
  );
  const [showCL, setShowCL] = useState(
    qL.includes("checklist") || qL.includes("inspect") || qL.includes("what to check")
  );

  return (
    <div className="mb-6">
      {/* User query — right-aligned bubble */}
      <div className="flex justify-end mb-2">
        <div className="max-w-2xl">
          <div className="flex items-center justify-end gap-2 mb-1">
            <span className="text-[10px] font-mono text-[#6b7280]">
              {turn.equipmentId && turn.equipmentId !== "Resolving…" ? turn.equipmentId : turn.isRunning ? "Resolving asset…" : "Plant-wide"}
            </span>
          </div>
          <div className="bg-amber-500/15 border border-amber-500/25 rounded-2xl rounded-tr-md px-4 py-2.5">
            <p className="text-sm text-[#f0f0f0] leading-relaxed">{turn.query}</p>
          </div>
        </div>
      </div>

      {/* Agent pipeline progress */}
      {turn.agentEvents.length > 0 && <AgentStatusRow turn={turn} />}
      {turn.isRunning && turn.agentEvents.length === 0 && (
        <div className="flex justify-center my-3">
          <div className="flex items-center gap-2 text-xs text-[#6b7280]">
            <Loader2 size={12} className="animate-spin text-amber-400" />
            Connecting to agent pipeline…
          </div>
        </div>
      )}

      {/* AI response — chat first */}
      {turn.synthesis && (
        <div className="flex justify-start mt-2">
          <div className="w-full space-y-2">
            {Boolean(turn.synthesis.degraded) && (
              <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
                <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />
                <div className="flex-1 leading-snug">
                  <span className="font-semibold text-amber-200">Degraded Fallback Mode:</span>{" "}
                  {turn.synthesis.degraded_reason || "Operating in fallback mode (vector search degraded). Response synthesized using relational records and keyword matching."}
                </div>
              </div>
            )}
            <div className="flex items-center gap-2 pl-1">
              <BrainCircuit size={12} className="text-amber-400" />
              <span className="text-[10px] text-[#6b7280]">EPIC</span>
            </div>

            {turn.synthesis.response_type === "chat" ? (
              /* ── Simple conversational response ── */
              <ChatMessage message={turn.synthesis.message ?? ""} />
            ) : (
              /* ── Full diagnostic response ── */
              <>
                <ProseResponse
                  result={turn.synthesis}
                  equipmentId={turn.equipmentId}
                  showFull={showFull}
                  onToggleFull={() => setShowFull(f => !f)}
                  woActive={showWO}
                  onShowWO={() => setShowWO(w => !w)}
                  clActive={showCL}
                  onShowCL={() => setShowCL(c => !c)}
                />

                {showCL && turn.synthesis.inspection_checklist.length > 0 && (
                  <QuickChecklist result={turn.synthesis} equipmentId={turn.equipmentId} />
                )}

                {showWO && turn.synthesis.work_order && (
                  <QuickWorkOrder result={turn.synthesis} equipmentId={turn.equipmentId} />
                )}

                {showFull && (
                  <div className="border border-[#1e1e1e] rounded-2xl overflow-hidden">
                    <SynthesisPanel result={turn.synthesis} equipmentId={turn.equipmentId} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main interface ────────────────────────────────────────────────────────────

export function QueryInterface() {
  const searchParams = useSearchParams();
  // ── Persistent state (survives navigation) ──────────────────────────────────
  const { query: qState, updateQuery, setQueryTurns } = usePageState();
  const turns       = qState.turns;
  const setTurns    = setQueryTurns;
  const equipmentId = qState.equipmentId || (searchParams.get("equipment") ?? "");
  const setEquipmentId = (id: string) => updateQuery({ equipmentId: id });
  const query       = qState.draft;
  const setQuery    = (q: string) => updateQuery({ draft: q });
  // ── Transient state (always reset on mount) ──────────────────────────────────
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [selectedEquipment, setSelectedEquipment] = useState<Equipment | null>(null);
  const [globalRunning, setGlobalRunning] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef   = useRef<HTMLTextAreaElement>(null);
  const activeStreamAbortRef = useRef<AbortController | null>(null);
  const suggestions = buildSuggestions(selectedEquipment);

  // Load backend health + equipment list on mount
  const [backendHealth, setBackendHealth] = useState<{ qdrant_active: boolean; degraded: boolean } | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetch("/api/v1/knowledge-graph/status")
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (isMounted) setBackendHealth(d); })
      .catch(() => {});

    listEquipment().catch(() => [] as Equipment[]).then(list => {
      if (!isMounted) return;
      setEquipmentList(list.filter(e => !e._discovered));
    });

    return () => {
      isMounted = false;
      activeStreamAbortRef.current?.abort();
    };
  }, []);

  // Fetch selected equipment detail whenever id changes with staleness & abort guard
  useEffect(() => {
    if (!equipmentId || equipmentId === "__all_equipment__") {
      setSelectedEquipment(null);
      return;
    }
    let isCurrent = true;
    const controller = new AbortController();

    getEquipment(equipmentId, { signal: controller.signal })
      .then(data => {
        if (isCurrent) setSelectedEquipment(data);
      })
      .catch((err) => {
        if (isCurrent && !(err instanceof DOMException && err.name === "AbortError")) {
          setSelectedEquipment(null);
        }
      });

    return () => {
      isCurrent = false;
      controller.abort();
    };
  }, [equipmentId]);

  // Auto-scroll to bottom whenever turns update
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  /** Build history from last 4 turns for context threading */
  const buildHistory = (): Array<{ role: string; content: string }> =>
    turns.slice(-4).flatMap(t => [
      { role: "user", content: `[${t.equipmentId}] ${t.query}` },
      ...(t.synthesis
        ? [{
            role: "assistant" as const,
            content: `${t.synthesis.risk_level} risk — ${t.synthesis.risk_summary} ${t.synthesis.explanation ?? ""}`.trim(),
          }]
        : []),
    ]);

  const handleSubmit = async () => {
    const text = query.trim();
    if (!text || globalRunning) return;

    if (activeStreamAbortRef.current) {
      activeStreamAbortRef.current.abort();
    }
    const streamController = new AbortController();
    activeStreamAbortRef.current = streamController;

    const turnId  = `turn-${Date.now()}`;
    const history = buildHistory();
    const eq = equipmentId;

    setQuery("");
    setGlobalRunning(true);
    const t0 = Date.now();

    const newTurn: SessionTurn = {
      id: turnId, equipmentId: eq || "Resolving…", query: text,
      agentEvents: [], synthesis: null, elapsed: null, isRunning: true,
    };
    setTurns(prev => [...prev, newTurn]);

    const update = (fn: (t: SessionTurn) => SessionTurn) =>
      setTurns(prev => prev.map(t => t.id === turnId ? fn(t) : t));

    try {
      for await (const event of streamAgentQuery(
        eq,
        text,
        history,
        streamController.signal,
      )) {
        if (streamController.signal.aborted) break;
        update(t => {
          const idx = t.agentEvents.findIndex(e => e.agent === event.agent);
          const events = idx >= 0
            ? t.agentEvents.map((e, i) => i === idx ? event : e)
            : [...t.agentEvents, event];
          const syn = event.agent === "synthesizer" && event.status === "done" && event.data
            ? event.data as SynthesisResult
            : t.synthesis;

          let currentEqId = t.equipmentId;
          const eventData = event.data as { resolved_equipment_id?: string; scope?: string } | undefined;
          if (eventData?.resolved_equipment_id) {
            currentEqId = eventData.resolved_equipment_id;
          } else if (eventData?.scope === "plant_wide" && (currentEqId === "Resolving…" || currentEqId === "__all_equipment__" || !currentEqId)) {
            currentEqId = "Plant-wide";
          }

          return { ...t, equipmentId: currentEqId, agentEvents: events, synthesis: syn };
        });
      }
    } catch (err: any) {
      if (!streamController.signal.aborted) {
        const errorMsg = err?.message || String(err) || "Stream interrupted";
        const isAuthError = errorMsg.includes("401") || errorMsg.includes("Not authenticated");
        update(t => ({
          ...t,
          isRunning: false,
          synthesis: t.synthesis || ({
            response_type: "chat",
            message: `**Query Error:** ${errorMsg}`,
            risk_level: "Unknown",
            risk_summary: "Query stream interrupted",
            ai_available: false,
            immediate_actions: [],
            inspection_checklist: [],
            similar_incidents: [],
            compliance_issues: [],
            probable_causes: [],
          } as any),
        }));
        if (isAuthError && typeof window !== "undefined" && window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      }
    } finally {
      if (activeStreamAbortRef.current === streamController) {
        activeStreamAbortRef.current = null;
      }
      update(t => ({ ...t, isRunning: false, elapsed: Date.now() - t0 }));
      setGlobalRunning(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
  };

  const handleVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window)) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rec = new (window as any).webkitSpeechRecognition();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rec.onresult = (e: any) => setQuery(e.results[0][0].transcript);
    rec.start();
  };

  return (
    <div className="flex flex-col h-full">

      {/* ── Sticky header ─────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-b border-[#1e1e1e] bg-[#0a0a0a]">
        {/* Service degradation warning banner */}
        {backendHealth?.degraded && (
          <div className="flex items-center justify-between px-5 py-2 bg-amber-500/10 border-b border-amber-500/25 text-amber-300 text-xs">
            <div className="flex items-center gap-2">
              <AlertTriangle size={14} className="text-amber-400 flex-shrink-0" />
              <span>
                <strong>Service Degradation:</strong> Qdrant vector search offline. Operating in keyword and relational fallback mode.
              </span>
            </div>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 flex-shrink-0">
              Degraded Mode
            </span>
          </div>
        )}
        {/* Title row */}
        <div className="flex items-center gap-2.5 px-3 sm:px-5 py-2.5">
          <BrainCircuit size={18} className="text-amber-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-[#f9f9f9] leading-none">EPIC Field Companion</p>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 font-mono">
                PWA
              </span>
            </div>
            <p className="text-[10px] text-[#4b5563] mt-0.5 truncate">
              {turns.length === 0
                ? "5 specialized agents · mobile-ready plant diagnostics"
                : `${turns.length} turn${turns.length !== 1 ? "s" : ""} · session active`}
            </p>
          </div>
          {turns.length > 0 && (
            <button
              onClick={() => setTurns([])}
              disabled={globalRunning}
              className="flex-shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
              title="Clear session"
              aria-label="Clear session"
            >
              <Trash2 size={15} />
            </button>
          )}
        </div>

        {/* Equipment selector */}
        <div className="flex items-center gap-2 px-3 sm:px-5 pb-2.5 flex-wrap">
          <div className="relative w-full sm:w-auto sm:flex-initial">
            <select
              value={equipmentId}
              onChange={e => setEquipmentId(e.target.value)}
              className="w-full sm:w-auto min-h-[44px] bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl pl-3.5 pr-8 py-2.5 text-xs text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50"
            >
              <option value="">Auto-resolve / Plant-wide</option>
              <option value="__all_equipment__">All Equipment</option>
              {equipmentList.length === 0
                ? (equipmentId && equipmentId !== "__all_equipment__" ? <option value={equipmentId}>{equipmentId}</option> : null)
                : equipmentList.map(eq => (
                    <option key={eq.id} value={eq.id}>
                      {eq.id} — {eq.name}
                      {eq.health_score != null && eq.health_score < 75 ? " ⚠" : ""}
                    </option>
                  ))
              }
            </select>
            <ChevronDown size={11} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
          </div>
        </div>
      </div>

      {/* ── Live sensor strip ─────────────────────────────────────────────── */}
      {selectedEquipment && (
        <SensorStrip equipment={selectedEquipment} onQuery={setQuery} />
      )}

      {/* ── Chat thread ───────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-5 py-4 sm:py-5">
        {turns.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center gap-2">
            <BrainCircuit size={44} className="text-[#252525] mb-2" />
            <p className="text-[#4b5563] text-sm font-medium">Select equipment and ask a question.</p>
            <p className="text-xs text-[#333]">Follow-up questions carry session context automatically.</p>
            {suggestions.length > 0 && (
              <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-xl">
                {suggestions.map(s => (
                  <button
                    key={s}
                    onClick={() => setQuery(s)}
                    className="text-xs px-3.5 py-2.5 min-h-[44px] flex items-center rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#a0a0a0] hover:border-amber-500/30 hover:text-amber-400 transition-colors text-left"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          turns.map(turn => <TurnView key={turn.id} turn={turn} />)
        )}
        <div ref={chatEndRef} />
      </div>

      {/* ── Sticky input area ─────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-[#1e1e1e] bg-[#0a0a0a] px-3 sm:px-5 py-3">
        {/* Quick suggestions (shown after first turn so they don't duplicate the empty-state) */}
        {turns.length > 0 && suggestions.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-2 mb-2 scrollbar-hide">
            {suggestions.map(s => (
              <button
                key={s}
                onClick={() => setQuery(s)}
                disabled={globalRunning}
                className="flex-shrink-0 min-h-[40px] text-xs px-3.5 py-2 rounded-full bg-[#1a1a1a] border border-[#252525] text-[#8b949e] hover:border-amber-500/30 hover:text-amber-400 transition-colors disabled:opacity-40"
              >
                {s.length > 55 ? s.slice(0, 55) + "…" : s}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          <button
            onClick={handleVoiceInput}
            disabled={globalRunning}
            className="flex-shrink-0 min-h-[44px] min-w-[44px] flex items-center justify-center p-2.5 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#8b949e] hover:text-amber-400 hover:border-amber-500/30 transition-colors mb-0.5 disabled:opacity-40"
            title="Voice input"
            aria-label="Voice input"
          >
            <Mic size={17} />
          </button>
          <textarea
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={globalRunning ? "Agents are processing…" : "Ask a question or describe a symptom…"}
            rows={1}
            disabled={globalRunning}
            className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 transition-colors disabled:opacity-50 min-h-[44px] max-h-32 resize-none"
            onInput={e => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 128) + "px";
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={globalRunning || !query.trim()}
            aria-label={globalRunning ? "Processing query" : "Submit query"}
            className={clsx(
              "flex-shrink-0 flex items-center justify-center gap-1.5 px-4 min-h-[44px] rounded-xl text-sm font-semibold transition-all mb-0.5",
              globalRunning || !query.trim()
                ? "bg-[#2a2a2a] text-[#4b5563] cursor-not-allowed"
                : "bg-amber-500 hover:bg-amber-400 text-black",
            )}
          >
            {globalRunning
              ? <Loader2 size={16} className="animate-spin" />
              : <Send size={16} />}
            <span>{globalRunning ? "…" : "Ask"}</span>
          </button>
        </div>

        {turns.length > 0 && !globalRunning && (
          <p className="text-[10px] text-[#2e2e2e] text-center mt-1.5">
            Session context: last {Math.min(turns.length, 4)} turn{turns.length !== 1 ? "s" : ""} included ·{" "}
            <button onClick={() => setTurns([])} className="text-[#3a3a3a] hover:text-red-400 transition-colors">
              clear session
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
