/**
 * AI Operations Brain — Compliance Dashboard Page
 * Shows OISD/ISO compliance status powered by AI analysis and action items.
 * Client component — fetches both static compliance data and AI analysis on mount.
 *
 * Sections:
 *  1. KPI strip  — overall risk, avg score, open issues
 *  2. AI Analysis panel — summary, trend, key findings, AI action items
 *  3. Compliance score bar chart (SVG) — per-equipment scores
 *  4. Regulatory breakdown — violations per regulation
 *  5. Equipment compliance list — detailed per-equipment card
 */
"use client";

import { useEffect, useState } from "react";
import { listCompliance, getComplianceAIAnalysis } from "@/lib/api";
import type { ComplianceStatus, ComplianceAIAnalysis, RiskLevel } from "@/lib/types";
import {
  ShieldCheck, AlertTriangle, CheckCircle2, Brain, TrendingUp, TrendingDown,
  Minus, ChevronRight, Clock, User, Activity, RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const RISK_COLOR: Record<string, string> = {
  Critical: "#ef4444",
  High: "#f97316",
  Medium: "#f59e0b",
  Low: "#10b981",
};

const DEADLINE_ORDER: Record<string, number> = {
  immediately: 0,
  "within 24h": 1,
  "within 7 days": 2,
  "within 30 days": 3,
};

function riskColor(risk: string) {
  return RISK_COLOR[risk] ?? "#6b7280";
}

function scoreColor(score: number) {
  if (score >= 90) return "#10b981";
  if (score >= 70) return "#f59e0b";
  return "#ef4444";
}

// ─── SVG compliance score chart ──────────────────────────────────────────────

function ComplianceScoreChart({ data }: { data: { label: string; score: number }[] }) {
  if (!data.length) return null;
  const W = 600;
  const barH = 28;
  const gap = 10;
  const labelW = 140;
  const chartW = W - labelW - 60;
  const H = data.length * (barH + gap) + 40;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 420 }}>
      {/* Title */}
      <text x={0} y={16} fill="#a0a0a0" fontSize={11} fontFamily="monospace">
        Equipment Compliance Scores
      </text>
      {data.map((d, i) => {
        const y = 28 + i * (barH + gap);
        const barLen = Math.max((d.score / 100) * chartW, 2);
        const color = scoreColor(d.score);
        return (
          <g key={d.label}>
            {/* Label */}
            <text x={0} y={y + barH / 2 + 4} fill="#d0d0d0" fontSize={10} fontFamily="monospace">
              {d.label.length > 18 ? d.label.slice(0, 17) + "…" : d.label}
            </text>
            {/* Track */}
            <rect x={labelW} y={y} width={chartW} height={barH} rx={4} fill="#1a1a1a" />
            {/* Fill */}
            <rect x={labelW} y={y} width={barLen} height={barH} rx={4} fill={color} opacity={0.85} />
            {/* Score label */}
            <text x={labelW + barLen + 6} y={y + barH / 2 + 4} fill={color} fontSize={11} fontWeight="bold" fontFamily="monospace">
              {d.score}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Regulatory breakdown mini-chart ─────────────────────────────────────────

function RegBreakdownChart({ data }: { data: { regulation: string; total: number; high: number }[] }) {
  if (!data.length) return null;
  const maxVal = Math.max(...data.map(d => d.total), 1);
  const W = 500;
  const barH = 22;
  const gap = 8;
  const labelW = 160;
  const chartW = W - labelW - 50;
  const H = data.length * (barH + gap) + 30;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 300 }}>
      <text x={0} y={14} fill="#a0a0a0" fontSize={11} fontFamily="monospace">
        Violations per Regulation
      </text>
      {data.map((d, i) => {
        const y = 22 + i * (barH + gap);
        const totalLen = (d.total / maxVal) * chartW;
        const highLen = (d.high / maxVal) * chartW;
        return (
          <g key={d.regulation}>
            <text x={0} y={y + barH / 2 + 4} fill="#c0c0c0" fontSize={9} fontFamily="monospace">
              {d.regulation.length > 22 ? d.regulation.slice(0, 21) + "…" : d.regulation}
            </text>
            {/* Total track */}
            <rect x={labelW} y={y} width={totalLen} height={barH} rx={3} fill="#f59e0b" opacity={0.35} />
            {/* High violations overlay */}
            <rect x={labelW} y={y} width={highLen} height={barH} rx={3} fill="#ef4444" opacity={0.8} />
            <text x={labelW + totalLen + 6} y={y + barH / 2 + 4} fill="#a0a0a0" fontSize={10} fontFamily="monospace">
              {d.high > 0 ? `${d.high}H / ` : ""}{d.total}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Action item card ─────────────────────────────────────────────────────────

function ActionItemCard({ item, index }: { item: ComplianceAIAnalysis["action_items"][0]; index: number }) {
  const color = riskColor(item.severity);
  return (
    <div
      className="flex gap-3 p-3 rounded-xl border"
      style={{ borderColor: `${color}33`, background: `${color}08` }}
    >
      {/* Priority badge */}
      <div
        className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
        style={{ background: `${color}22`, color }}
      >
        {item.priority}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2 mb-1">
          <p className="text-sm font-semibold text-[#f9f9f9] leading-tight">{item.title}</p>
          <Badge variant={item.severity === "Critical" || item.severity === "High" ? "high" : item.severity === "Medium" ? "medium" : "low"}>
            {item.severity}
          </Badge>
        </div>
        <p className="text-xs text-[#a0a0a0] mb-2 leading-relaxed">{item.description}</p>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="flex items-center gap-1 text-amber-400">
            <ChevronRight size={10} />{item.regulation}
          </span>
          <span className="flex items-center gap-1 text-[#6b7280]">
            <Clock size={10} />{item.deadline}
          </span>
          <span className="flex items-center gap-1 text-[#6b7280]">
            <User size={10} />{item.owner}
          </span>
          <span className="flex items-center gap-1 text-[#6b7280]">
            <Activity size={10} />{item.estimated_effort}
          </span>
        </div>
        {item.equipment_ids?.length > 0 && (
          <div className="flex gap-1 mt-1.5 flex-wrap">
            {item.equipment_ids.map(eid => (
              <span key={eid} className="px-1.5 py-0.5 bg-[#1a1a1a] border border-[#2a2a2a] rounded text-xs font-mono text-[#a0a0a0]">
                {eid}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CompliancePage() {
  const [compliance, setCompliance] = useState<ComplianceStatus[]>([]);
  const [analysis, setAnalysis] = useState<ComplianceAIAnalysis | null>(null);
  const [loadingStatic, setLoadingStatic] = useState(true);
  const [loadingAI, setLoadingAI] = useState(true);
  const [aiError, setAiError] = useState<string | null>(null);

  useEffect(() => {
    listCompliance()
      .then(setCompliance)
      .catch(() => setCompliance([]))
      .finally(() => setLoadingStatic(false));

    getComplianceAIAnalysis()
      .then(setAnalysis)
      .catch(err => setAiError(String(err)))
      .finally(() => setLoadingAI(false));
  }, []);

  const totalIssues = compliance.reduce((s, c) => s + (c.total_issues ?? 0), 0);
  const highIssues = compliance.reduce((s, c) => s + (c.high_issues ?? 0), 0);
  const avgScore = compliance.length
    ? Math.round(compliance.reduce((s, c) => s + c.overall_score, 0) / compliance.length)
    : 0;

  const scoreChartData = [...compliance]
    .sort((a, b) => a.overall_score - b.overall_score)
    .map(c => ({ label: c.equipment_name ?? c.equipment_id, score: c.overall_score }));

  const regChartData = (analysis?.regulatory_breakdown ?? []).map(r => ({
    regulation: r.regulation,
    total: r.total_violations,
    high: r.high_violations,
  }));

  const trendIcon = analysis?.compliance_score_trend === "Improving"
    ? <TrendingUp size={14} className="text-emerald-400" />
    : analysis?.compliance_score_trend === "Declining"
    ? <TrendingDown size={14} className="text-red-400" />
    : <Minus size={14} className="text-amber-400" />;

  const overallRisk = analysis?.overall_risk ?? (highIssues > 0 ? "High" : "Medium");

  return (
    <div className="p-6 space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#f9f9f9]">Compliance Dashboard</h1>
          <p className="text-sm text-[#6b7280] mt-1">OISD-117 · ISO 10816-3 · Factory Act · Internal SOPs</p>
        </div>
        {analysis && (
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-semibold"
            style={{ borderColor: `${riskColor(overallRisk)}55`, color: riskColor(overallRisk), background: `${riskColor(overallRisk)}10` }}
          >
            <ShieldCheck size={14} />
            {overallRisk} Risk
          </div>
        )}
      </div>

      {/* ── KPI strip ── */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <ShieldCheck size={18} className="mx-auto mb-2 text-emerald-400" />
          <p className="text-2xl font-bold text-emerald-400">{avgScore}%</p>
          <p className="text-xs text-[#6b7280]">Avg Compliance Score</p>
        </div>
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <AlertTriangle size={18} className="mx-auto mb-2 text-red-400" />
          <p className="text-2xl font-bold text-red-400">{highIssues}</p>
          <p className="text-xs text-[#6b7280]">High Severity Issues</p>
        </div>
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4 text-center">
          <CheckCircle2 size={18} className="mx-auto mb-2 text-amber-400" />
          <p className="text-2xl font-bold text-amber-400">{totalIssues}</p>
          <p className="text-xs text-[#6b7280]">Total Open Issues</p>
        </div>
      </div>

      {/* ── AI Analysis panel ── */}
      <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Brain size={16} className="text-violet-400" />
          <h2 className="text-sm font-semibold text-[#f9f9f9]">AI Compliance Analysis</h2>
          {loadingAI && <RefreshCw size={13} className="text-[#6b7280] animate-spin ml-1" />}
          {analysis && (
            <span className="flex items-center gap-1 text-xs ml-auto" style={{ color: analysis.compliance_score_trend === "Improving" ? "#10b981" : analysis.compliance_score_trend === "Declining" ? "#ef4444" : "#f59e0b" }}>
              {trendIcon}
              {analysis.compliance_score_trend}
            </span>
          )}
        </div>

        {loadingAI && !analysis && (
          <p className="text-xs text-[#6b7280]">Running AI analysis across all equipment…</p>
        )}

        {aiError && (
          <p className="text-xs text-red-400">AI analysis unavailable: {aiError}</p>
        )}

        {analysis && (
          <div className="space-y-5">
            {/* Summary */}
            <p className="text-sm text-[#c0c0c0] leading-relaxed border-l-2 border-violet-500 pl-3">
              {analysis.overall_summary}
            </p>

            {/* Key findings */}
            {analysis.key_findings?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-2">Key Findings</p>
                <div className="space-y-2">
                  {analysis.key_findings.map((f, i) => (
                    <div key={i} className="p-3 bg-[#161616] rounded-lg border border-[#2a2a2a]">
                      <p className="text-xs font-semibold text-[#f0f0f0] mb-0.5">🔍 {f.finding}</p>
                      <p className="text-xs text-[#f59e0b] mb-0.5">Impact: {f.impact}</p>
                      <p className="text-xs text-emerald-400">→ {f.recommendation}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action items */}
            {analysis.action_items?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-2">
                  Prioritised Action Items ({analysis.action_items.length})
                </p>
                <div className="space-y-2">
                  {[...analysis.action_items]
                    .sort((a, b) => (DEADLINE_ORDER[a.deadline] ?? 99) - (DEADLINE_ORDER[b.deadline] ?? 99))
                    .map((item, i) => (
                      <ActionItemCard key={i} item={item} index={i} />
                    ))}
                </div>
              </div>
            )}

            {/* Regulations at risk */}
            {analysis.top_regulations_at_risk?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-2">Top Regulations at Risk</p>
                <div className="grid grid-cols-2 gap-2">
                  {analysis.top_regulations_at_risk.map((r, i) => (
                    <div key={i} className="p-2.5 bg-[#161616] rounded-lg border border-[#2a2a2a]">
                      <p className="text-xs font-semibold text-amber-400">{r.regulation}</p>
                      <p className="text-xs text-[#a0a0a0] mt-0.5">{r.equipment_count} equipment · {r.avg_severity} severity</p>
                      <p className="text-xs text-[#6b7280] mt-0.5">{r.risk_note}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Score chart + Regulatory breakdown ── */}
      {!loadingStatic && compliance.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
            <ComplianceScoreChart data={scoreChartData} />
          </div>
          {regChartData.length > 0 && (
            <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
              <RegBreakdownChart data={regChartData} />
              <div className="flex gap-3 mt-2">
                <span className="flex items-center gap-1 text-xs text-red-400"><span className="w-2 h-2 rounded-full bg-red-400 inline-block" /> High severity</span>
                <span className="flex items-center gap-1 text-xs text-amber-400"><span className="w-2 h-2 rounded-full bg-amber-400 opacity-40 inline-block" /> Total</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Equipment risk ranking (AI) ── */}
      {analysis?.equipment_risk_ranking && analysis.equipment_risk_ranking.length > 0 && (
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Equipment Risk Ranking (AI)</p>
          <div className="space-y-1.5">
            {analysis.equipment_risk_ranking.slice(0, 8).map((eq, i) => (
              <div key={eq.equipment_id} className="flex items-center gap-3 p-2 rounded-lg bg-[#161616]">
                <span className="text-xs font-mono text-[#6b7280] w-4">{i + 1}</span>
                <span className="text-xs font-mono text-[#a0a0a0] w-16">{eq.equipment_id}</span>
                <div className="flex-1 h-1.5 bg-[#2a2a2a] rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${eq.compliance_score}%`, background: scoreColor(eq.compliance_score) }} />
                </div>
                <span className="text-xs font-bold w-10 text-right" style={{ color: scoreColor(eq.compliance_score) }}>{eq.compliance_score}%</span>
                <Badge variant={eq.risk_level === "Critical" || eq.risk_level === "High" ? "high" : eq.risk_level === "Medium" ? "medium" : "low"}>
                  {eq.risk_level}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Detailed equipment compliance list ── */}
      <div>
        <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-3">Equipment Detail</p>
        <div className="space-y-3">
          {compliance.map(c => (
            <div key={c.equipment_id} className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-xs font-mono text-[#6b7280]">{c.equipment_id}</p>
                  <p className="text-sm font-semibold text-[#f9f9f9]">{c.equipment_name ?? c.equipment_id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold" style={{ color: scoreColor(c.overall_score) }}>
                    {c.overall_score}%
                  </span>
                  <Badge variant={c.status === "Warning" ? "high" : c.status === "Compliant" ? "low" : "medium"}>
                    {c.status ?? "Unknown"}
                  </Badge>
                </div>
              </div>

              <div className="h-1.5 w-full bg-[#2a2a2a] rounded-full mb-3 overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${c.overall_score}%`, background: scoreColor(c.overall_score) }} />
              </div>

              {(c.issues ?? []).length > 0 && (
                <div className="space-y-2">
                  {(c.issues as Array<{ id: string; regulation: string; description: string; severity: string; action: string }>).map(issue => (
                    <div key={issue.id} className="flex items-start gap-2 p-2 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a]">
                      <Badge variant={issue.severity === "High" ? "high" : issue.severity === "Medium" ? "medium" : "low"}>
                        {issue.severity}
                      </Badge>
                      <div>
                        <p className="text-xs text-amber-400 font-medium">{issue.regulation}</p>
                        <p className="text-xs text-[#a0a0a0] mt-0.5">{issue.description}</p>
                        <p className="text-xs text-emerald-400 mt-1">→ {issue.action}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {!loadingStatic && compliance.length === 0 && (
            <p className="text-center text-sm text-[#6b7280] py-8">No compliance data available.</p>
          )}

          {loadingStatic && (
            <p className="text-center text-sm text-[#6b7280] py-8">Loading compliance data…</p>
          )}
        </div>
      </div>
    </div>
  );
}

