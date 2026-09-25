/**
 * AI Operations Brain — Work-order AI assistant
 * Chats about one work order and applies the changes it proposes through the same role-guarded routes a person
 * uses. The server cuts each proposal to what the signed-in role may apply and names what it withheld.
 */
"use client";

import { useEffect, useRef, useState } from "react";
import { addWorkOrderSteps, chatWithWorkOrder, errorText, updateWorkOrder, updateWorkOrderStep } from "@/lib/api";
import type { OpsProposedChanges } from "@/lib/api";
import type { SavedWorkOrderStep } from "@/lib/types";
import { approverRoles, fieldRoles } from "@/lib/roles";
import { MdText } from "@/components/WorkOrders/ChatMarkdown";
import { Brain, CheckCircle2, Loader2, Send } from "lucide-react";
import clsx from "clsx";
import { toast } from "sonner";

type AIChatMsg = {
  role: "user" | "assistant";
  content: string;
  proposedChanges?: OpsProposedChanges | null;
  withheldChanges?: string[];
  applied?: boolean;
};

// The server keeps the newest turns that fit the model's window; older ones would only be cut there.
const CHAT_HISTORY_TURNS = 12;

const WITHHELD_LABELS: Record<string, string> = {
  description: `description (${approverRoles.join(" or ")})`,
  risk_level: `risk level (${approverRoles.join(" or ")})`,
  toggle_steps: `step ticks (${fieldRoles.join(" or ")})`,
  add_steps: `new steps (${fieldRoles.join(" or ")})`,
};

export function AIOpsChat({
  itemId, steps, onApply,
}: {
  itemId: string;
  steps: SavedWorkOrderStep[];
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
    const history = prevMsgs.slice(-CHAT_HISTORY_TURNS).map(m => ({ role: m.role, content: m.content }));
    try {
      const res = await chatWithWorkOrder(itemId, { message: text, history });
      setMsgs(prev => [...prev, {
        role: "assistant", content: res.answer,
        proposedChanges: res.proposed_changes, withheldChanges: res.withheld_changes,
      }]);
    } catch {
      setMsgs(prev => [...prev, { role: "assistant", content: "Error contacting AI. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  const applyChanges = async (changes: OpsProposedChanges, idx: number) => {
    setApplying(true);
    try {
      if (changes.description || changes.risk_level) {
        await updateWorkOrder(itemId, {
          ...(changes.description && { description: changes.description }),
          ...(changes.risk_level  && { risk_level:  changes.risk_level  }),
        });
      }
      for (const t of changes.toggle_steps ?? []) {
        const notes = steps[t.step_index]?.actual_notes ?? "";
        await updateWorkOrderStep(itemId, { step_index: t.step_index, checked: t.checked, actual_notes: notes });
      }
      if (changes.add_steps?.length) await addWorkOrderSteps(itemId, changes.add_steps);

      setMsgs(prev => prev.map((m, i) => i === idx ? { ...m, applied: true } : m));
      onApply();
    } catch (err) {
      toast.error(errorText(err, "Could not apply the change"));
      onApply();
    } finally { setApplying(false); }
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
                      {msg.proposedChanges.toggle_steps?.map((t, j) => (
                        <p key={j}>
                          • {t.checked ? "✓ Check" : "○ Uncheck"} step #{t.step_index + 1}
                          {steps[t.step_index]?.title && <span className="text-[#f9f9f9]"> &ldquo;{steps[t.step_index].title}&rdquo;</span>}
                        </p>
                      ))}
                      {msg.proposedChanges.add_steps?.map((step, j) => (
                        <p key={j}>• Add step: <span className="text-[#f9f9f9]">&ldquo;{step.title || step.description}&rdquo;</span></p>
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

                {msg.role === "assistant" && !!msg.withheldChanges?.length && (
                  <p className="mt-2 text-[11px] text-amber-400/80">
                    Left out because your role cannot apply them:{" "}
                    {msg.withheldChanges.map(field => WITHHELD_LABELS[field] ?? field).join(", ")}.
                  </p>
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
          placeholder="Ask about this work order…"
          aria-label="Ask about this work order"
          className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-xs text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-purple-500/50 transition-colors"
        />
        <button
          onClick={send}
          disabled={!input.trim() || loading}
          aria-label="Send message to AI assistant"
          className="p-2 bg-purple-500/20 text-purple-400 border border-purple-500/30 rounded-lg hover:bg-purple-500/30 transition-colors disabled:opacity-40"
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}
