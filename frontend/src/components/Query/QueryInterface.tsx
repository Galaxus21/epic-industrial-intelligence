/**
 * AI Operations Brain — Chat-style Query Interface
 * Stateful session: carries conversation history through each multi-agent query.
 * Layout: sticky header (equipment selector) · scrollable chat thread · sticky input.
 */
"use client";

import { useState, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { streamAgentQuery, listEquipment, getEquipment, createChecklist, createWorkOrder, getProjectHierarchy } from "@/lib/api";
import type { ProjectHierarchy, HierarchyPlant } from "@/lib/api";
import { AgentPanel } from "./AgentPanel";
import { SynthesisPanel } from "./SynthesisPanel";
import { WorkOrderCard } from "./WorkOrderCard";
import { Badge } from "@/components/ui/Badge";
import type { AgentEvent, SynthesisResult, Equipment, SessionTurn } from "@/lib/types";
import { usePageState } from "@/lib/page-state";
import {
  BrainCircuit, Send, Mic, Loader2, ChevronDown, ChevronUp, Trash2,
  AlertTriangle, ClipboardList, Wrench, Save, CheckCircle2, Activity,
  FormInput, Building2, FolderKanban,
} from "lucide-react";
import Link from "next/link";
import clsx from "clsx";

// ── Sensor strip ──────────────────────────────────────────────────────────────

function sensorColor(r: { value: number; normal?: number; alarm?: number; trip?: number }): string {
  if (r.trip !== undefined && r.value >= r.trip) return "#ef4444";
  if (r.alarm !== undefined && r.value > r.alarm) return "#f97316";
  if (r.normal !== undefined && r.value > r.normal * 1.1) return "#f59e0b";
  return "#10b981";
}

function sensorLabel(key: string): string {
  return key.replace(/_/g, " ")
    .replace(/\bde\b/i, "DE").replace(/\bnde\b/i, "NDE")
    .replace(/\b\w/g, c => c.toUpperCase());
}

function SensorStrip({ equipment, onQuery }: { equipment: Equipment; onQuery: (q: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const readings = equipment.current_readings;
  if (!readings || Object.keys(readings).length === 0) return null;

  const entries = Object.entries(readings) as [string, { value: number; unit: string; normal?: number; alarm?: number; trip?: number }][];
  const alarmCount = entries.filter(([, r]) => r.alarm !== undefined && r.value > r.alarm).length;

  return (
    <div className="flex-shrink-0 border-b border-[#1e1e1e] bg-[#080808]">
      {/* Compact chip row */}
      <div className="flex items-center gap-2 px-4 py-1.5 overflow-x-auto scrollbar-hide">
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1.5 flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider text-[#4b5563] hover:text-[#6b7280] transition-colors"
        >
          <Activity size={11} />
          <span>Sensors</span>
          {alarmCount > 0 && (
            <span className="px-1 py-0 rounded bg-orange-500/20 text-orange-400 text-[9px]">
              {alarmCount} ⚠
            </span>
          )}
          {expanded ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
        </button>

        {entries.map(([key, r]) => {
          const color = sensorColor(r);
          return (
            <button
              key={key}
              onClick={() => onQuery(`${equipment.id}: ${sensorLabel(key)} is ${r.value} ${r.unit}${r.alarm && r.value > r.alarm ? " — ABOVE ALARM" : ""}. Is this a concern?`)}
              title={`Click to ask AI about this reading`}
              className="flex items-center gap-1 flex-shrink-0 px-2 py-0.5 rounded bg-[#111] border border-[#1e1e1e] hover:border-amber-500/25 transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
              <span className="text-[9px] text-[#4b5563] whitespace-nowrap">{key.replace(/_/g, "\u00a0")}</span>
              <span className="text-[10px] font-mono font-semibold whitespace-nowrap" style={{ color }}>{r.value}</span>
              <span className="text-[9px] text-[#333]">{r.unit}</span>
            </button>
          );
        })}

        <Link
          href={`/forms?equipment=${equipment.id}`}
          className="flex-shrink-0 ml-auto flex items-center gap-1 px-2 py-0.5 rounded border border-[#252525] text-[10px] text-[#4b5563] hover:border-amber-500/30 hover:text-amber-400 transition-colors"
        >
          <FormInput size={10} /> Log Data
        </Link>
      </div>

      {/* Expanded detail grid */}
      {expanded && (
        <div className="px-4 pb-3 pt-1 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7 gap-2">
          {entries.map(([key, r]) => {
            const color = sensorColor(r);
            const max = r.trip ?? (r.alarm ? r.alarm * 1.5 : (r.normal ?? 10) * 2);
            const pct = Math.min(100, (r.value / max) * 100);
            const alarmPct = r.alarm ? (r.alarm / max) * 100 : null;
            const isAlarm = r.alarm !== undefined && r.value > r.alarm;
            return (
              <button
                key={key}
                onClick={() => onQuery(`${equipment.id}: ${sensorLabel(key)} is ${r.value} ${r.unit}${isAlarm ? " — ABOVE ALARM" : ""}. Is this a concern?`)}
                className={clsx(
                  "text-left p-2.5 rounded-xl border transition-colors hover:border-amber-500/20",
                  isAlarm ? "bg-orange-500/5 border-orange-500/20" : "bg-[#0f0f0f] border-[#1e1e1e]"
                )}
              >
                <p className="text-[9px] text-[#4b5563] mb-1 truncate">{sensorLabel(key)}</p>
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
      <p className="text-sm text-[#e0e0e0] leading-relaxed">
        {displayed}
        {isTyping && <span className="inline-block w-0.5 h-3.5 bg-[#e0e0e0]/60 ml-0.5 animate-pulse align-middle rounded-sm" />}
      </p>
    </div>
  );
}

function fmtInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i} className="font-semibold text-[#e8e8e8]">{part.slice(2, -2)}</strong>
      : part
  );
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
    } catch { } finally { setSaving(false); }
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
          <button onClick={handleSave} disabled={saving}
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
    if (!wo) return;
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
    } catch { } finally { setSaving(false); }
  };
  if (!wo) return null;
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
            <span className="text-[10px] font-mono text-[#6b7280]">{turn.equipmentId}</span>
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
            <div className="flex items-center gap-2 pl-1">
              <BrainCircuit size={12} className="text-amber-400" />
              <span className="text-[10px] text-[#6b7280]">AI Operations Brain</span>
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
  const suggestions = buildSuggestions(selectedEquipment);

  // ── Hierarchy state ──────────────────────────────────────────────────────────
  const [hierarchy, setHierarchy] = useState<ProjectHierarchy | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("__all__");
  const [selectedPlantId, setSelectedPlantId]     = useState<string>("__all__");

  // Derive filtered plant / equipment lists from hierarchy selection
  const visiblePlants: HierarchyPlant[] = (() => {
    if (!hierarchy) return [];
    if (selectedProjectId === "__all__") return hierarchy.projects.flatMap(p => p.plants);
    return hierarchy.projects.find(p => p.id === selectedProjectId)?.plants ?? [];
  })();

  const visibleEquipmentIds: string[] = (() => {
    if (!hierarchy) return [];
    if (selectedPlantId === "__all__") return visiblePlants.flatMap(p => p.equipment.map(e => e.id));
    return visiblePlants.find(p => p.id === selectedPlantId)?.equipment.map(e => e.id) ?? [];
  })();

  // Show ALL equipment when no project/plant filter is active;
  // otherwise restrict to the equipment linked to the selected plant/project.
  const filteredEquipmentList =
    (selectedProjectId === "__all__" && selectedPlantId === "__all__")
      ? equipmentList
      : visibleEquipmentIds.length > 0
        ? equipmentList.filter(e => visibleEquipmentIds.includes(e.id))
        : equipmentList;

  // Load hierarchy + flat equipment list on mount
  useEffect(() => {
    Promise.all([
      listEquipment().catch(() => [] as Equipment[]),
      getProjectHierarchy().catch(() => null),
    ]).then(([list, hier]) => {
      const active = list.filter(e => !e._discovered);
      setEquipmentList(active);
      setHierarchy(hier);
      if (!equipmentId && active.length > 0) setEquipmentId(active[0].id);
    });
  }, []);

  // Fetch selected equipment detail whenever id changes
  useEffect(() => {
    if (!equipmentId || equipmentId === "__all_equipment__") {
      setSelectedEquipment(null);
      return;
    }
    getEquipment(equipmentId).then(setSelectedEquipment).catch(() => setSelectedEquipment(null));
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

    const turnId  = `turn-${Date.now()}`;
    const history = buildHistory();
    // Resolve "All Equipment" to the first equipment in the filtered list,
    // or a generic plant-level context label if nothing is loaded yet.
    const eq = equipmentId === "__all_equipment__"
      ? (filteredEquipmentList[0]?.id ?? "")
      : equipmentId;

    setQuery("");
    setGlobalRunning(true);
    const t0 = Date.now();

    const newTurn: SessionTurn = {
      id: turnId, equipmentId: eq, query: text,
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
        selectedPlantId !== "__all__" ? selectedPlantId : undefined,
        selectedProjectId !== "__all__" ? selectedProjectId : undefined,
      )) {
        update(t => {
          const idx = t.agentEvents.findIndex(e => e.agent === event.agent);
          const events = idx >= 0
            ? t.agentEvents.map((e, i) => i === idx ? event : e)
            : [...t.agentEvents, event];
          const syn = event.agent === "synthesizer" && event.status === "done" && event.data
            ? event.data as SynthesisResult
            : t.synthesis;
          return { ...t, agentEvents: events, synthesis: syn };
        });
      }
    } finally {
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
        {/* Title row */}
        <div className="flex items-center gap-3 px-5 py-2.5">
          <BrainCircuit size={18} className="text-amber-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[#f9f9f9] leading-none">AI Operations Brain</p>
            <p className="text-[10px] text-[#4b5563] mt-0.5">
              {turns.length === 0
                ? "5 specialized agents · real-time analysis"
                : `${turns.length} turn${turns.length !== 1 ? "s" : ""} · session active`}
            </p>
          </div>
          {turns.length > 0 && (
            <button
              onClick={() => setTurns([])}
              disabled={globalRunning}
              className="flex-shrink-0 p-1.5 rounded-lg text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
              title="Clear session"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>

        {/* Cascade selectors row: Project → Plant → Equipment */}
        <div className="flex items-center gap-2 px-5 pb-2.5 flex-wrap">
          {/* Project */}
          <div className="relative flex-shrink-0">
            <FolderKanban size={10} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
            <select
              value={selectedProjectId}
              onChange={e => { setSelectedProjectId(e.target.value); setSelectedPlantId("__all__"); }}
              className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-7 pr-6 py-1.5 text-[11px] text-[#c0c0c0] appearance-none focus:outline-none focus:border-amber-500/50"
            >
              <option value="__all__">All Projects</option>
              {(hierarchy?.projects ?? []).map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <ChevronDown size={9} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
          </div>

          <span className="text-[#333] text-xs">›</span>

          {/* Plant */}
          <div className="relative flex-shrink-0">
            <Building2 size={10} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
            <select
              value={selectedPlantId}
              onChange={e => { setSelectedPlantId(e.target.value); }}
              disabled={visiblePlants.length === 0}
              className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-7 pr-6 py-1.5 text-[11px] text-[#c0c0c0] appearance-none focus:outline-none focus:border-amber-500/50 disabled:opacity-40"
            >
              <option value="__all__">All Plants</option>
              {visiblePlants.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
              ))}
            </select>
            <ChevronDown size={9} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
          </div>

          <span className="text-[#333] text-xs">›</span>

          {/* Equipment */}
          <div className="relative flex-shrink-0">
            <select
              value={equipmentId}
              onChange={e => setEquipmentId(e.target.value)}
              className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-3 pr-8 py-1.5 text-[11px] text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50"
            >
              <option value="__all_equipment__">All Equipment</option>
              {filteredEquipmentList.length === 0
                ? <option value={equipmentId}>{equipmentId || "Loading…"}</option>
                : filteredEquipmentList.map(eq => (
                    <option key={eq.id} value={eq.id}>
                      {eq.id} — {eq.name}
                      {eq.health_score != null && eq.health_score < 75 ? " ⚠" : ""}
                    </option>
                  ))
              }
            </select>
            <ChevronDown size={11} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#6b7280] pointer-events-none" />
          </div>

          {/* Context badge */}
          {(selectedProjectId !== "__all__" || selectedPlantId !== "__all__") && (
            <span className="text-[10px] text-amber-400/70 flex items-center gap-1 ml-1">
              <BrainCircuit size={9} />
              {[
                selectedProjectId !== "__all__" && hierarchy?.projects.find(p => p.id === selectedProjectId)?.code,
                selectedPlantId   !== "__all__" && visiblePlants.find(p => p.id === selectedPlantId)?.code,
              ].filter(Boolean).join(" › ")} context active
            </span>
          )}
        </div>
      </div>

      {/* ── Live sensor strip ─────────────────────────────────────────────── */}
      {selectedEquipment && (
        <SensorStrip equipment={selectedEquipment} onQuery={setQuery} />
      )}

      {/* ── Chat thread ───────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-5 py-5">
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
                    className="text-xs px-3 py-1.5 rounded-full bg-[#1a1a1a] border border-[#2a2a2a] text-[#a0a0a0] hover:border-amber-500/30 hover:text-amber-400 transition-colors text-left"
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
      <div className="flex-shrink-0 border-t border-[#1e1e1e] bg-[#0a0a0a] px-5 py-3">
        {/* Quick suggestions (shown after first turn so they don't duplicate the empty-state) */}
        {turns.length > 0 && suggestions.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-2 mb-2 scrollbar-hide">
            {suggestions.map(s => (
              <button
                key={s}
                onClick={() => setQuery(s)}
                disabled={globalRunning}
                className="flex-shrink-0 text-[11px] px-3 py-1 rounded-full bg-[#1a1a1a] border border-[#252525] text-[#6b7280] hover:border-amber-500/30 hover:text-amber-400 transition-colors disabled:opacity-40"
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
            className="flex-shrink-0 p-2.5 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] text-[#6b7280] hover:text-amber-400 hover:border-amber-500/30 transition-colors mb-0.5 disabled:opacity-40"
            title="Voice input"
          >
            <Mic size={15} />
          </button>
          <textarea
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={globalRunning ? "Agents are processing…" : "Ask a question or describe a symptom…"}
            rows={1}
            disabled={globalRunning}
            className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 transition-colors disabled:opacity-50 min-h-[42px] max-h-32 resize-none"
            onInput={e => {
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 128) + "px";
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={globalRunning || !query.trim()}
            className={clsx(
              "flex-shrink-0 flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all mb-0.5",
              globalRunning || !query.trim()
                ? "bg-[#2a2a2a] text-[#4b5563] cursor-not-allowed"
                : "bg-amber-500 hover:bg-amber-400 text-black",
            )}
          >
            {globalRunning
              ? <Loader2 size={14} className="animate-spin" />
              : <Send size={14} />}
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
