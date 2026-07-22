/**
 * AI Operations Brain — Integrations Dashboard Page
 * Shows all 10 integration sources: email, Slack, CMMS, DCS, historian, etc.
 */
"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import type { Integration, FeedItem, EmailMessage, SlackMessage } from "@/lib/integrationTypes";
import {
  Mail, MessageSquare, ClipboardList, Activity, TrendingUp,
  FolderOpen, Radio, Webhook, Smartphone, Users, RefreshCw,
  CheckCircle2, Settings, AlertTriangle, Zap, Clock, ChevronDown, ChevronUp, Bot,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";
import { format, parseISO } from "date-fns";

const ICON_MAP: Record<string, LucideIcon> = {
  Mail, MessageSquare, ClipboardList, Activity, TrendingUp,
  FolderOpen, Radio, Webhook, Smartphone, Users,
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

const STATUS_CONFIG = {
  connected: { label: "Connected",  color: "text-emerald-400", dot: "bg-emerald-500", variant: "low" as const },
  active:    { label: "Active",     color: "text-emerald-400", dot: "bg-emerald-500", variant: "low" as const },
  configure: { label: "Set Up",     color: "text-[#6b7280]",   dot: "bg-[#4b5563]",  variant: "muted" as const },
  error:     { label: "Error",      color: "text-red-400",     dot: "bg-red-500",    variant: "critical" as const },
};

const CATEGORY_ORDER = ["Communication", "CMMS / ERP", "Process Control", "Document Management", "IoT & Sensors", "API & Integration"];

// ─── Integration Card ──────────────────────────────────────────────────────

function IntegrationCard({ integration, onClick, selected }: {
  integration: Integration;
  onClick: () => void;
  selected: boolean;
}) {
  const Icon = ICON_MAP[integration.icon] ?? Zap;
  const st = STATUS_CONFIG[integration.status] ?? STATUS_CONFIG.configure;

  return (
    <button
      onClick={onClick}
      className={clsx(
        "w-full text-left p-4 rounded-xl border transition-all",
        selected
          ? "bg-amber-500/10 border-amber-500/40"
          : "bg-[#1f1f1f] border-[#2a2a2a] hover:border-[#444] hover:bg-[#242424]"
      )}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon size={16} className={integration.status === "connected" || integration.status === "active" ? "text-amber-400" : "text-[#6b7280]"} />
          <p className="text-xs font-semibold text-[#f9f9f9] leading-tight">{integration.name}</p>
        </div>
        <div className="flex items-center gap-1">
          <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
          <span className={`text-xs ${st.color}`}>{st.label}</span>
        </div>
      </div>
      <p className="text-xs text-[#6b7280] leading-relaxed line-clamp-2 mb-2">{integration.description}</p>
      <div className="flex items-center gap-2 flex-wrap">
        {integration.item_count > 0 && (
          <span className="text-xs text-[#a0a0a0]">{integration.item_count} items</span>
        )}
        {integration.action_required > 0 && (
          <Badge variant="high">{integration.action_required} actions</Badge>
        )}
        {integration.tags.slice(0, 2).map(t => (
          <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-[#2a2a2a] text-[#6b7280]">{t}</span>
        ))}
      </div>
    </button>
  );
}

// ─── Feed Item Row ──────────────────────────────────────────────────────────

function FeedRow({ item }: { item: FeedItem }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = ICON_MAP[item.icon] ?? Mail;

  return (
    <div className={clsx(
      "border-b border-[#2a2a2a] last:border-0",
      item.action_required && "bg-orange-500/5"
    )}>
      <button className="w-full text-left flex items-start gap-3 p-3 hover:bg-[#242424] transition-colors" onClick={() => setExpanded(e => !e)}>
        <div className="flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center" style={{ background: `${item.color}22` }}>
          <Icon size={12} style={{ color: item.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-medium text-[#f9f9f9] truncate">{item.title}</span>
            {item.action_required && <AlertTriangle size={10} className="text-orange-400 flex-shrink-0" />}
            {item.has_ai_reply && <Bot size={10} className="text-amber-400 flex-shrink-0" />}
          </div>
          <p className="text-xs text-[#6b7280] truncate">{item.preview}</p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {item.equipment.map(e => (
              <span key={e} className="text-xs px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono">{e}</span>
            ))}
            <span className="text-xs text-[#4b5563] ml-auto">
              {format(parseISO(item.timestamp), "HH:mm")}
            </span>
          </div>
        </div>
        <div className="flex-shrink-0 text-[#4b5563]">
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
      </button>
      {expanded && (
        <div className="px-3 pb-3 ml-10">
          <p className="text-xs text-[#a0a0a0] leading-relaxed whitespace-pre-wrap bg-[#1a1a1a] rounded-lg p-2 border border-[#2a2a2a]">
            {item.preview.replace("...", "")}
          </p>
          <p className="text-xs text-[#4b5563] mt-1">From: {item.from} · {format(parseISO(item.timestamp), "d MMM yyyy HH:mm")}</p>
        </div>
      )}
    </div>
  );
}

// ─── Slack Message Row ──────────────────────────────────────────────────────

function SlackRow({ msg }: { msg: SlackMessage }) {
  return (
    <div className={clsx("p-3 border-b border-[#2a2a2a] last:border-0", msg.action_required && "bg-orange-500/5")}>
      <div className="flex items-start gap-2">
        <div className="w-7 h-7 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-purple-400">{msg.user_avatar}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-semibold text-[#f9f9f9]">{msg.user_display}</span>
            <span className="text-xs text-[#6b7280]">{msg.channel}</span>
            {msg.action_required && <Badge variant="high">Action</Badge>}
            <span className="text-xs text-[#4b5563] ml-auto">{format(parseISO(msg.timestamp), "HH:mm")}</span>
          </div>
          <p className="text-xs text-[#a0a0a0] leading-relaxed">{msg.text}</p>
          {msg.equipment_mentions.length > 0 && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {msg.equipment_mentions.map(e => (
                <span key={e} className="text-xs px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-mono">{e}</span>
              ))}
            </div>
          )}
          {msg.thread_replies.map((reply, i) => (
            <div key={i} className="mt-2 pl-2 border-l-2 border-amber-500/30">
              <div className="flex items-center gap-1 mb-0.5">
                <Bot size={10} className="text-amber-400" />
                <span className="text-xs font-semibold text-amber-400">{reply.user}</span>
              </div>
              <p className="text-xs text-[#a0a0a0] whitespace-pre-wrap">{reply.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Setup Panel ────────────────────────────────────────────────────────────

function SetupPanel({ integration }: { integration: Integration }) {
  const isLive = integration.status === "connected" || integration.status === "active";
  const [enabled, setEnabled] = useState(isLive);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const MASK = "••••••••";

  // Load saved config on mount
  useEffect(() => {
    if (!integration.setup_fields.length) return;
    apiFetch<{ enabled: boolean; config: Record<string, string>; last_test_ok?: boolean; last_test_msg?: string }>(
      `/api/v1/integrations/${integration.id}/config`
    ).then(data => {
      setEnabled(data.enabled);
      setValues(data.config ?? {});
      if (data.last_test_ok !== undefined) {
        setTestResult({ ok: data.last_test_ok, message: data.last_test_msg ?? "" });
      }
    }).catch(_err => { /* not yet configured */ });
  }, [integration.id]);

  const handleSave = async () => {
    setSaving(true); setSaveMsg(null);
    try {
      await fetch(`${BASE}/api/v1/integrations/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integration.id, enabled, config: values }),
      });
      setSaveMsg("Saved");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch { setSaveMsg("Save failed"); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTesting(true); setTestResult(null);
    // Save first, then test
    try {
      await fetch(`${BASE}/api/v1/integrations/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ integration_id: integration.id, enabled, config: values }),
      });
      const res = await fetch(`${BASE}/api/v1/integrations/${integration.id}/test`, { method: "POST" });
      const data = await res.json();
      setTestResult({ ok: data.ok, message: data.message });
    } catch (e: unknown) {
      setTestResult({ ok: false, message: String(e) });
    } finally { setTesting(false); }
  };

  return (
    <div className="space-y-3">
      {/* Status banner */}
      <div className={clsx(
        "flex items-center justify-between p-3 rounded-lg border",
        isLive ? "bg-emerald-500/10 border-emerald-500/30" : "bg-[#1a1a1a] border-[#2a2a2a]"
      )}>
        <div className="flex items-center gap-2">
          {isLive ? <CheckCircle2 size={14} className="text-emerald-400" /> : <Settings size={14} className="text-[#6b7280]" />}
          <p className="text-xs font-semibold" style={{ color: isLive ? "#10b981" : "#a0a0a0" }}>
            {isLive ? "Integration active — receiving data" : "Configuration required"}
          </p>
        </div>
        {/* Enable toggle */}
        {integration.setup_fields.length > 0 && (
          <button
            onClick={() => setEnabled(e => !e)}
            className={clsx(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors",
              enabled
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400"
                : "bg-[#2a2a2a] border-[#3a3a3a] text-[#6b7280]"
            )}
          >
            <span className={clsx("w-1.5 h-1.5 rounded-full", enabled ? "bg-emerald-400" : "bg-[#4b5563]")} />
            {enabled ? "Enabled" : "Disabled"}
          </button>
        )}
      </div>

      {/* Webhook URL */}
      {integration.webhook_url && (
        <div className="p-3 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a]">
          <p className="text-xs text-[#6b7280] mb-1">Webhook URL (POST to this endpoint):</p>
          <code className="text-xs text-amber-400 font-mono break-all">{integration.webhook_url}</code>
        </div>
      )}

      {/* Config form fields */}
      {integration.setup_fields.length > 0 && (
        <div className="space-y-2">
          {integration.setup_fields.map(field => (
            <div key={field.key}>
              <label className="block text-xs text-[#6b7280] mb-1">{field.label}</label>
              <input
                type={field.secret ? "password" : "text"}
                value={values[field.key] ?? ""}
                placeholder={field.placeholder}
                onChange={e => setValues(v => ({ ...v, [field.key]: e.target.value }))}
                autoComplete="off"
                className="w-full bg-[#111] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/40 font-mono"
              />
            </div>
          ))}
        </div>
      )}

      {/* Test result */}
      {testResult && (
        <div className={clsx(
          "flex items-start gap-2 p-3 rounded-lg border text-xs",
          testResult.ok
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
            : "bg-red-500/10 border-red-500/30 text-red-400"
        )}>
          {testResult.ok
            ? <CheckCircle2 size={13} className="flex-shrink-0 mt-0.5" />
            : <AlertTriangle size={13} className="flex-shrink-0 mt-0.5" />}
          {testResult.message}
        </div>
      )}

      {/* Action buttons */}
      {integration.setup_fields.length > 0 && (
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/25 text-xs text-amber-400 hover:bg-amber-500/25 transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
            {saveMsg ?? "Save"}
          </button>
          <button
            onClick={handleTest}
            disabled={testing || saving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1a1a1a] border border-[#2a2a2a] text-xs text-[#a0a0a0] hover:border-amber-500/30 hover:text-amber-400 transition-colors disabled:opacity-50"
          >
            {testing ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
            Test Connection
          </button>
        </div>
      )}

      <div className="flex flex-wrap gap-1 pt-1">
        {integration.tags.map(t => (
          <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-[#2a2a2a] text-[#6b7280]">{t}</span>
        ))}
      </div>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [slackMessages, setSlackMessages] = useState<SlackMessage[]>([]);
  const [selected, setSelected] = useState<Integration | null>(null);
  const [activeTab, setActiveTab] = useState<"configure" | "feed" | "email" | "slack">("feed");
  const [stats, setStats] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<Integration[]>("/api/v1/integrations"),
      apiFetch<FeedItem[]>("/api/v1/integrations/feed"),
      apiFetch<SlackMessage[]>("/api/v1/integrations/slack/messages"),
      apiFetch<Record<string, number>>("/api/v1/integrations/stats"),
    ]).then(([ints, f, slack, s]) => {
      setIntegrations(ints);
      setFeed(f);
      setSlackMessages(slack);
      setStats(s);
      setSelected(ints.find(i => i.status === "connected") ?? ints[0]);
    }).finally(() => setLoading(false));
  }, []);

  const categories = CATEGORY_ORDER.filter(c => integrations.some(i => i.category === c));

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#f9f9f9]">Data Ingestion Integrations</h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Connect every data source — email, Slack, CMMS, DCS, historian, IoT — into the AI knowledge graph.
          </p>
        </div>
        <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1f1f1f] border border-[#2a2a2a] text-xs text-[#a0a0a0] hover:border-amber-500/30 transition-colors">
          <RefreshCw size={12} /> Sync All
        </button>
      </div>

      {/* KPI row */}
      {!loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Active Integrations",   value: stats.active_integrations ?? 0,    color: "#10b981" },
            { label: "Pending Setup",         value: stats.pending_configuration ?? 0,  color: "#f59e0b" },
            { label: "Items Ingested",        value: stats.total_items_ingested ?? 0,   color: "#3b82f6" },
            { label: "Actions Required",      value: stats.action_required ?? 0,        color: "#f97316" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-3 text-center">
              <p className="text-2xl font-bold" style={{ color }}>{value}</p>
              <p className="text-xs text-[#6b7280] mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left: Integration catalog */}
        <div className="xl:col-span-1 space-y-5">
          {loading ? (
            <p className="text-xs text-[#6b7280]">Loading integrations…</p>
          ) : categories.map(cat => (
            <div key={cat}>
              <p className="text-xs font-semibold text-[#6b7280] mb-2 uppercase tracking-wide">{cat}</p>
              <div className="space-y-2">
                {integrations.filter(i => i.category === cat).map(integration => (
                  <IntegrationCard
                    key={integration.id}
                    integration={integration}
                    onClick={() => {
                      setSelected(integration);
                      // Auto-open Configure tab when clicking a configurable integration
                      setActiveTab(integration.setup_fields.length > 0 ? "configure" : "feed");
                    }}
                    selected={selected?.id === integration.id}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Right: Detail panel */}
        <div className="xl:col-span-2 space-y-4">
          {/* Unified panel: Configure + Live Feed tabs */}
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl">
            {/* Tabs */}
            <div className="flex border-b border-[#2a2a2a]">
              {selected?.setup_fields.length ? (
                <button
                  onClick={() => setActiveTab("configure")}
                  className={clsx(
                    "flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-colors",
                    activeTab === "configure"
                      ? "text-amber-400 border-b-2 border-amber-500"
                      : "text-[#6b7280] hover:text-[#a0a0a0]"
                  )}
                >
                  <Settings size={11} /> Configure
                </button>
              ) : null}
              {(["feed", "email", "slack"] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={clsx(
                    "flex-1 py-3 text-xs font-medium capitalize transition-colors",
                    activeTab === tab
                      ? "text-amber-400 border-b-2 border-amber-500"
                      : "text-[#6b7280] hover:text-[#a0a0a0]"
                  )}
                >
                  {tab === "feed" ? "All Sources" : tab === "email" ? "Email" : "Slack"}
                  {tab === "feed" && <span className="ml-1 text-[#4b5563]">({feed.length})</span>}
                  {tab === "email" && <span className="ml-1 text-[#4b5563]">({feed.filter(f => f.source === "email").length})</span>}
                  {tab === "slack" && <span className="ml-1 text-[#4b5563]">({slackMessages.length})</span>}
                </button>
              ))}
            </div>

            {/* Tab header */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-[#2a2a2a]">
              <Clock size={12} className="text-[#6b7280]" />
              <p className="text-xs text-[#6b7280]">
                {activeTab === "configure" && `Configure ${selected?.name ?? "integration"} credentials`}
                {activeTab === "feed" && "Real-time ingestion feed from all connected sources"}
                {activeTab === "email" && "Maintenance emails processed by document intelligence"}
                {activeTab === "slack" && "Channel messages with AI bot replies"}
              </p>
              <div className="ml-auto flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs text-emerald-500">Live</span>
              </div>
            </div>

            {/* Content */}
            <div className={clsx(activeTab !== "configure" && "max-h-[520px] overflow-y-auto")}>
              {/* ── Configure tab ── */}
              {activeTab === "configure" && selected && (
                <div className="p-5">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h2 className="text-sm font-bold text-[#f9f9f9]">{selected.name}</h2>
                      <p className="text-xs text-[#6b7280] mt-0.5">{selected.description}</p>
                    </div>
                    <Badge variant={STATUS_CONFIG[selected.status]?.variant ?? "muted"}>
                      {STATUS_CONFIG[selected.status]?.label}
                    </Badge>
                  </div>
                  <SetupPanel integration={selected} />
                </div>
              )}
              {/* ── Feed tabs ── */}
              {activeTab === "feed" && feed.map(item => <FeedRow key={item.id} item={item} />)}
              {activeTab === "email" && feed.filter(f => f.source === "email").map(item => <FeedRow key={item.id} item={item} />)}
              {activeTab === "slack" && slackMessages.map(msg => <SlackRow key={msg.id} msg={msg} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
