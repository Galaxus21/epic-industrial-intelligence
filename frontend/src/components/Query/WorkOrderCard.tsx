/**
 * AI Operations Brain — Work Order Card
 * Interactive step-by-step procedure with checkable steps, phase grouping,
 * safety alerts, and live progress tracking.
 */
"use client";

import { useState, useMemo } from "react";
import {
  Wrench, AlertTriangle, CheckCircle2, Circle, Clock,
  ChevronDown, ChevronUp, ShieldAlert, Package, Users,
  FileText, Printer,
} from "lucide-react";
import type { WorkOrder, WorkOrderPhase } from "@/lib/types";
import clsx from "clsx";

// ── Phase config ──────────────────────────────────────────────────────────────

const PHASE_CONFIG: Record<WorkOrderPhase, { color: string; bg: string; border: string; dot: string }> = {
  Preparation:  { color: "text-blue-400",   bg: "bg-blue-500/10",   border: "border-blue-500/30",   dot: "#60a5fa" },
  Isolation:    { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30", dot: "#fb923c" },
  Execution:    { color: "text-amber-400",  bg: "bg-amber-500/10",  border: "border-amber-500/30",  dot: "#fbbf24" },
  Verification: { color: "text-teal-400",   bg: "bg-teal-500/10",   border: "border-teal-500/30",   dot: "#2dd4bf" },
  Restart:      { color: "text-emerald-400",bg: "bg-emerald-500/10",border: "border-emerald-500/30",dot: "#34d399" },
};

const WO_TYPE_COLOR: Record<string, string> = {
  Emergency: "text-red-400 bg-red-500/15 border-red-500/30",
  Corrective: "text-orange-400 bg-orange-500/15 border-orange-500/30",
  "Emergency Corrective": "text-red-400 bg-red-500/15 border-red-500/30",
  Preventive: "text-emerald-400 bg-emerald-500/15 border-emerald-500/30",
};

// ── Step row ──────────────────────────────────────────────────────────────────

interface StepRowProps {
  step: WorkOrder["procedure_steps"][number];
  checked: boolean;
  onToggle: () => void;
  isLast: boolean;
}

function StepRow({ step, checked, onToggle, isLast }: StepRowProps) {
  const [expanded, setExpanded] = useState(false);
  const phase = (step.phase ?? "Execution") as WorkOrderPhase;
  const pCfg = PHASE_CONFIG[phase] ?? PHASE_CONFIG.Execution;
  const hasDetail = !!step.safety_note || step.description.length > 80;

  return (
    <div className={clsx("relative pl-8", !isLast && "pb-0")}>
      {/* Vertical connector line */}
      {!isLast && (
        <div className="absolute left-[14px] top-7 bottom-0 w-px bg-[#2a2a2a]" />
      )}

      {/* Step number + check circle */}
      <button
        onClick={onToggle}
        className="absolute left-0 top-1 w-7 h-7 flex items-center justify-center"
        aria-label={checked ? "Mark incomplete" : "Mark complete"}
      >
        {checked ? (
          <CheckCircle2 size={24} className="text-emerald-400 fill-emerald-400/20" />
        ) : (
          <Circle size={24} className="text-[#3a3a3a] hover:text-[#6b7280] transition-colors" />
        )}
      </button>

      {/* Card */}
      <div className={clsx(
        "mb-3 rounded-lg border transition-all overflow-hidden",
        checked
          ? "bg-[#141414] border-[#222] opacity-70"
          : "bg-[#1a1a1a] border-[#2a2a2a] hover:border-[#3a3a3a]",
      )}>
        {/* Header */}
        <div
          className="flex items-center gap-2 px-3 py-2.5 cursor-pointer"
          onClick={hasDetail ? () => setExpanded(e => !e) : undefined}
        >
          {/* Step number */}
          <span className="text-xs font-mono text-[#4b5563] flex-shrink-0 w-5">{step.step}.</span>

          {/* Phase tag */}
          <span className={clsx(
            "text-xs px-1.5 py-0.5 rounded-full border flex-shrink-0 font-medium",
            pCfg.color, pCfg.bg, pCfg.border,
          )}>
            {phase}
          </span>

          {/* Title */}
          <p className={clsx(
            "text-xs font-semibold flex-1",
            checked ? "line-through text-[#4b5563]" : "text-[#f9f9f9]",
          )}>
            {step.title}
          </p>

          {/* Duration */}
          {step.expected_duration_minutes > 0 && (
            <span className="text-xs text-[#4b5563] flex items-center gap-1 flex-shrink-0">
              <Clock size={10} /> {step.expected_duration_minutes}m
            </span>
          )}

          {/* Safety indicator */}
          {step.safety_note && (
            <AlertTriangle size={13} className="text-red-400 flex-shrink-0" />
          )}

          {/* Expand toggle */}
          {hasDetail && (
            expanded
              ? <ChevronUp size={12} className="text-[#4b5563] flex-shrink-0" />
              : <ChevronDown size={12} className="text-[#4b5563] flex-shrink-0" />
          )}
        </div>

        {/* Expanded detail */}
        {(expanded || !hasDetail) && (
          <div className="px-3 pb-3 border-t border-[#222] pt-2 space-y-2">
            <p className="text-xs text-[#a0a0a0] leading-relaxed">{step.description}</p>
            {step.safety_note && (
              <div className="flex gap-2 p-2 bg-red-500/8 border border-red-500/25 rounded-lg">
                <ShieldAlert size={12} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-red-300 leading-relaxed">{step.safety_note}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface WorkOrderCardProps {
  workOrder: WorkOrder;
  requiredPermits: string[];
  equipmentId: string;
}

export function WorkOrderCard({ workOrder, requiredPermits, equipmentId }: WorkOrderCardProps) {
  const steps = workOrder.procedure_steps ?? [];
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [allExpanded, setAllExpanded] = useState(true);

  const toggle = (stepNum: number) =>
    setChecked(prev => {
      const next = new Set(prev);
      next.has(stepNum) ? next.delete(stepNum) : next.add(stepNum);
      return next;
    });

  const completedCount = checked.size;
  const totalSteps = steps.length;
  const progressPct = totalSteps > 0 ? Math.round((completedCount / totalSteps) * 100) : 0;
  const allDone = completedCount === totalSteps && totalSteps > 0;

  // Group steps by phase for the phase summary
  const phases = useMemo(() => {
    const map = new Map<string, number>();
    steps.forEach(s => map.set(s.phase, (map.get(s.phase) ?? 0) + 1));
    return map;
  }, [steps]);

  const typeColor = WO_TYPE_COLOR[workOrder.type] ?? "text-amber-400 bg-amber-500/15 border-amber-500/30";

  return (
    <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#2a2a2a] bg-[#1a1a1a]">
        <Wrench size={16} className="text-purple-400 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#f9f9f9]">Work Order</span>
            <span className={clsx("text-xs px-2 py-0.5 rounded-full border font-medium", typeColor)}>
              {workOrder.type}
            </span>
            <span className="text-xs text-[#6b7280]">· {equipmentId}</span>
          </div>
          <p className="text-xs text-[#6b7280] mt-0.5 truncate">{workOrder.description}</p>
        </div>
        <button
          onClick={() => setAllExpanded(e => !e)}
          className="text-xs text-[#4b5563] hover:text-[#a0a0a0] transition-colors flex-shrink-0"
        >
          {allExpanded ? "Collapse all" : "Expand all"}
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border-b border-[#2a2a2a]">
        {[
          { icon: <Clock size={12} />, label: "Est. Duration", value: `${workOrder.estimated_duration_hours}h` },
          { icon: <Users size={12} />, label: "Technicians", value: `${workOrder.required_technicians} required` },
          { icon: <Package size={12} />, label: "Spare Parts", value: `${workOrder.spare_parts.length} items` },
          { icon: <FileText size={12} />, label: "Permits", value: `${requiredPermits.length > 0 ? requiredPermits.length : "PTW"} required` },
        ].map((stat, i) => (
          <div key={i} className="flex items-center gap-2 px-4 py-2.5 border-r border-[#2a2a2a] last:border-0">
            <span className="text-[#4b5563]">{stat.icon}</span>
            <div>
              <p className="text-xs text-[#4b5563]">{stat.label}</p>
              <p className="text-xs font-semibold text-[#a0a0a0]">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Phase breakdown */}
      {phases.size > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-[#2a2a2a] overflow-x-auto">
          {Array.from(phases.entries()).map(([phase, count]) => {
            const pCfg = PHASE_CONFIG[phase as WorkOrderPhase] ?? PHASE_CONFIG.Execution;
            return (
              <span key={phase} className={clsx(
                "flex-shrink-0 text-xs px-2 py-0.5 rounded-full border",
                pCfg.color, pCfg.bg, pCfg.border,
              )}>
                {phase} · {count}
              </span>
            );
          })}
        </div>
      )}

      {/* Progress bar */}
      {totalSteps > 0 && (
        <div className="px-4 py-3 border-b border-[#2a2a2a]">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-[#6b7280]">
              {allDone
                ? "✓ All steps complete"
                : `${completedCount} / ${totalSteps} steps completed`}
            </span>
            <span className={clsx("text-xs font-bold", allDone ? "text-emerald-400" : "text-amber-400")}>
              {progressPct}%
            </span>
          </div>
          <div className="h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
            <div
              className={clsx(
                "h-full rounded-full transition-all duration-300",
                allDone ? "bg-emerald-500" : "bg-amber-500",
              )}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}

      <div className={clsx("transition-all", allExpanded ? "block" : "hidden")}>
        {/* Safety precautions */}
        {workOrder.safety_precautions.length > 0 && (
          <div className="mx-4 mt-4 mb-2 p-3 bg-red-500/5 border border-red-500/20 rounded-lg">
            <div className="flex items-center gap-1.5 mb-2">
              <ShieldAlert size={13} className="text-red-400" />
              <span className="text-xs font-semibold text-red-400">Safety Precautions — Read Before Starting</span>
            </div>
            <ul className="space-y-1">
              {workOrder.safety_precautions.map((p, i) => (
                <li key={i} className="flex gap-2 text-xs text-red-300/80">
                  <span className="text-red-500 flex-shrink-0">⚠</span>
                  {p}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Permits required */}
        {requiredPermits.length > 0 && (
          <div className="mx-4 my-2 flex flex-wrap gap-1.5">
            {requiredPermits.map((p, i) => (
              <span key={i} className="text-xs px-2 py-1 bg-amber-500/10 border border-amber-500/25 rounded-lg text-amber-400 flex items-center gap-1">
                <FileText size={10} /> {p}
              </span>
            ))}
          </div>
        )}

        {/* Procedure steps */}
        {steps.length > 0 && (
          <div className="px-4 pt-3 pb-2">
            <p className="text-xs font-semibold text-[#6b7280] mb-3 uppercase tracking-wide">
              Procedure Steps
            </p>
            {steps.map((step, i) => (
              <StepRow
                key={step.step}
                step={step}
                checked={checked.has(step.step)}
                onToggle={() => toggle(step.step)}
                isLast={i === steps.length - 1}
              />
            ))}
          </div>
        )}

        {/* Spare parts */}
        {workOrder.spare_parts.length > 0 && (
          <div className="px-4 pb-4">
            <div className="flex items-center gap-1.5 mb-2">
              <Package size={12} className="text-purple-400" />
              <span className="text-xs font-semibold text-[#6b7280]">Required Spare Parts</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {workOrder.spare_parts.map((p, i) => (
                <span key={i} className="text-xs px-2 py-1 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t border-[#2a2a2a] bg-[#1a1a1a]">
        <span className="text-xs text-[#4b5563]">
          Click each step to mark complete · Safety warnings expand automatically
        </span>
        <button
          onClick={() => setChecked(new Set())}
          className="text-xs text-[#4b5563] hover:text-[#a0a0a0] transition-colors"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
