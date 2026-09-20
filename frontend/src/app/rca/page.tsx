/**
 * AI Operations Brain — Root Cause Analysis Engine
 * Takes a reported symptom / production event, collects evidence from the
 * knowledge graph, and returns a ranked causal chain with probability scores.
 *
 * Layout: Quick-event chips → symptom input → causal chain + ranked causes.
 */
"use client";

import { useState } from "react";
import { analyzeRootCause, getRCAEvents } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import {
  GitBranch, AlertTriangle, Loader2, Send, ChevronRight, Zap,
  BarChart2, Wrench, CheckCircle2, Clock,
} from "lucide-react";
import clsx from "clsx";
import { useEffect } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

type QuickEvent = { id: string; title: string; description: string; equipment_hint: string | null; severity: string };

type CausalStep = { step: number; event: string; type: string; equipment_id: string | null };

type ProbableCause = {
  rank: number;
  cause: string;
  probability: number;
  evidence: string[];
  equipment_affected: string[];
  recommended_action: string;
  timeframe: string;
};

type RCAResult = {
  event: string;
  equipment_id: string | null;
  analysis_timestamp: string;
  probable_causes: ProbableCause[];
  causal_chain: CausalStep[];
  sensor_anomalies: { equipment_id: string; sensor: string; value: number; unit: string; alarm: number; excess_pct: number }[];
  contributing_factors: string[];
  recommended_next_steps: string[];
  confidence: string;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const STEP_TYPE_STYLE: Record<string, { border: string; badge: string; icon: string }> = {
  root_cause:  { border: "border-red-500",    badge: "bg-red-500/20 text-red-400",    icon: "🔴" },
  propagation: { border: "border-amber-500",  badge: "bg-amber-500/20 text-amber-400", icon: "🟠" },
  symptom:     { border: "border-sky-500",    badge: "bg-sky-500/20 text-sky-400",    icon: "🔵" },
};

const SEV_COLOR: Record<string, string> = {
  Critical: "text-red-400", High: "text-orange-400", Medium: "text-amber-400", Low: "text-emerald-400",
};

function ProbabilityBar({ pct }: { pct: number }) {
  const color = pct >= 70 ? "#ef4444" : pct >= 40 ? "#f97316" : "#f59e0b";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-[#252525] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono font-semibold" style={{ color }}>{pct}%</span>
    </div>
  );
}

// ── Causal Chain Visualization ─────────────────────────────────────────────────

function CausalChain({ chain }: { chain: CausalStep[] }) {
  return (
    <div className="space-y-0">
      {chain.map((step, i) => {
        const style = STEP_TYPE_STYLE[step.type] ?? STEP_TYPE_STYLE.propagation;
        return (
          <div key={step.step} className="flex items-stretch gap-3">
            {/* Vertical connector */}
            <div className="flex flex-col items-center flex-shrink-0 w-8">
              <div className={clsx("w-8 h-8 rounded-full border-2 flex items-center justify-center text-sm flex-shrink-0", style.border)}>
                {style.icon}
              </div>
              {i < chain.length - 1 && <div className="w-0.5 flex-1 bg-[#252525] my-1" />}
            </div>
            {/* Step content */}
            <div className="pb-4 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className={clsx("text-[10px] font-semibold px-1.5 py-0.5 rounded", style.badge)}>
                  {step.type.replace("_", " ").toUpperCase()}
                </span>
                {step.equipment_id && (
                  <span className="text-[10px] font-mono text-[#6b7280]">{step.equipment_id}</span>
                )}
              </div>
              <p className="text-sm text-[#e0e0e0]">{step.event}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function RCAPage() {
  const [quickEvents, setQuickEvents] = useState<QuickEvent[]>([]);
  const [symptom, setSymptom] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RCAResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getRCAEvents().then(e => setQuickEvents(e as QuickEvent[])).catch(() => {});
  }, []);

  const handleAnalyze = async () => {
    if (!symptom.trim() || running) return;
    setRunning(true);
    setResult(null);
    setError("");
    try {
      const res = await analyzeRootCause({
        symptom,
        equipment_id: equipmentId || undefined,
      }) as RCAResult;
      setResult(res);
    } catch {
      setError("Analysis failed. Please try again.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Page header */}
      <div className="flex items-center gap-3 mb-6">
        <GitBranch size={22} className="text-amber-400" />
        <div>
          <h1 className="text-xl font-bold text-[#f9f9f9]">Root Cause Analysis Engine</h1>
          <p className="text-xs text-[#6b7280] mt-0.5">
            Describe a symptom or production event — AI traces the causal chain across equipment, sensors, and history.
          </p>
        </div>
      </div>

      {/* Quick events */}
      <div className="mb-5">
        <p className="text-xs font-semibold text-[#6b7280] mb-2 uppercase tracking-wider">
          Quick start — live plant events
        </p>
        {quickEvents.length === 0 ? (
          <p className="text-xs text-[#4b5563] italic">
            No active alarms, open incidents, or overdue maintenance found. Enter a symptom below to begin.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {quickEvents.map(ev => (
              <button
                key={ev.id}
                onClick={() => { setSymptom(ev.description); if (ev.equipment_hint) setEquipmentId(ev.equipment_hint); }}
                className={clsx(
                  "text-xs px-3 py-1.5 rounded-full border transition-colors text-left",
                  "bg-[#1a1a1a] border-[#2a2a2a] text-[#a0a0a0] hover:border-amber-500/30 hover:text-amber-400"
                )}
              >
                <span className={clsx("mr-1.5", SEV_COLOR[ev.severity] ?? "text-[#6b7280]")}>●</span>
                {ev.title}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5 mb-6">
        <div className="flex gap-3 mb-3">
          <div className="flex-1">
            <label htmlFor="rca-symptom" className="text-xs font-semibold text-[#a0a0a0] block mb-1.5">Symptom / Event Description</label>
            <textarea
              id="rca-symptom"
              value={symptom}
              onChange={e => setSymptom(e.target.value)}
              placeholder="e.g. Production throughput dropped 12% over the last 6 hours without any planned change…"
              aria-label="Symptom or Event Description"
              rows={3}
              className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-4 py-2.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 resize-none"
            />
          </div>
          <div className="w-36">
            <label htmlFor="rca-equipment" className="text-xs font-semibold text-[#a0a0a0] block mb-1.5">Equipment (optional)</label>
            <input
              id="rca-equipment"
              value={equipmentId}
              onChange={e => setEquipmentId(e.target.value)}
              placeholder="P-101"
              aria-label="Equipment ID (optional)"
              className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            onClick={handleAnalyze}
            disabled={running || !symptom.trim()}
            className={clsx(
              "flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all",
              running || !symptom.trim()
                ? "bg-[#2a2a2a] text-[#4b5563] cursor-not-allowed"
                : "bg-amber-500 hover:bg-amber-400 text-black",
            )}
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {running ? "Analyzing…" : "Analyze Root Cause"}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-xl mb-4 text-sm text-red-400">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-5">
          {/* Confidence + timestamp */}
          <div className="flex items-center gap-3">
            <Badge variant={result.confidence === "High" ? "low" : result.confidence === "Medium" ? "medium" : "high"}>
              {result.confidence} Confidence
            </Badge>
            <span className="text-xs text-[#4b5563]">
              {new Date(result.analysis_timestamp).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* LEFT: Causal chain */}
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <GitBranch size={14} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-[#f9f9f9]">Causal Chain</h2>
              </div>
              <CausalChain chain={result.causal_chain} />
            </div>

            {/* RIGHT: Probable causes */}
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <BarChart2 size={14} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-[#f9f9f9]">Probable Causes</h2>
              </div>
              <div className="space-y-4">
                {result.probable_causes.map(cause => (
                  <div key={cause.rank} className="border-l-2 border-[#252525] pl-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[10px] text-[#4b5563] font-mono">#{cause.rank}</span>
                      <span className={clsx(
                        "text-[10px] font-semibold px-1.5 py-0.5 rounded",
                        "bg-[#1e1e1e] text-[#a0a0a0]"
                      )}>
                        {cause.timeframe}
                      </span>
                    </div>
                    <p className="text-sm text-[#e0e0e0] mb-2">{cause.cause}</p>
                    <ProbabilityBar pct={cause.probability} />
                    <div className="mt-2 space-y-1">
                      {cause.evidence.map((ev, i) => (
                        <p key={i} className="text-xs text-[#6b7280] flex items-start gap-1.5">
                          <span className="text-[#333] mt-0.5 flex-shrink-0">›</span> {ev}
                        </p>
                      ))}
                    </div>
                    <div className="mt-2 flex items-start gap-1.5 bg-[#1a1a1a] rounded-lg px-3 py-2">
                      <Wrench size={11} className="text-amber-400 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-[#a0a0a0]">{cause.recommended_action}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sensor anomalies */}
          {result.sensor_anomalies.length > 0 && (
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={14} className="text-orange-400" />
                <h2 className="text-sm font-semibold text-[#f9f9f9]">Active Sensor Anomalies</h2>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {result.sensor_anomalies.map((a, i) => (
                  <div key={i} className="bg-[#1a1a1a] border border-orange-500/20 rounded-xl p-3">
                    <p className="text-[10px] font-mono text-[#6b7280] mb-0.5">{a.equipment_id}</p>
                    <p className="text-xs text-[#a0a0a0] mb-1">{a.sensor.replace("_", " ")}</p>
                    <p className="text-base font-bold text-orange-400">{a.value}<span className="text-xs ml-0.5 text-[#6b7280]">{a.unit}</span></p>
                    <p className="text-[10px] text-[#4b5563]">alarm {a.alarm} · <span className="text-orange-400">+{a.excess_pct}%</span></p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Contributing factors + next steps */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5">
              <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Contributing Factors</p>
              <ul className="space-y-1.5">
                {result.contributing_factors.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#a0a0a0]">
                    <span className="text-amber-500 mt-1 flex-shrink-0">•</span> {f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5">
              <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Recommended Next Steps</p>
              <ol className="space-y-1.5">
                {result.recommended_next_steps.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[#a0a0a0]">
                    <span className="text-[#4b5563] font-mono text-[10px] mt-0.5 flex-shrink-0">{i + 1}.</span>
                    <CheckCircle2 size={12} className="text-emerald-500 mt-0.5 flex-shrink-0" />
                    {s}
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!result && !running && (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <GitBranch size={40} className="text-[#252525] mb-2" />
          <p className="text-[#4b5563] text-sm font-medium">Enter a symptom or pick a quick event above.</p>
          <p className="text-xs text-[#2e2e2e] max-w-sm">
            The engine correlates sensor anomalies, maintenance history, and incidents to rank probable causes.
          </p>
        </div>
      )}
    </div>
  );
}
