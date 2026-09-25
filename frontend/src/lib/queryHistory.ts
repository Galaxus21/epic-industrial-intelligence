/**
 * The conversation sent with a query: the last few turns, each as the user asked it and as the assistant answered.
 * A chat reply (a greeting, a clarification, "not registered") answers in `message`; only an analysis has a risk
 * level and summary. Each turn is clamped well below backend/app/api/chatTurn.py MAX_TURN_CHARS (8,000), which
 * refuses the whole query with a 422 when one history turn is longer.
 */
import type { SessionTurn, SynthesisResult } from "./types";

export const HISTORY_TURNS = 4;
export const HISTORY_TURN_CHARS = 2000;
// A turn carries this label until the stream names its equipment; one that stopped before then was plant-wide.
export const RESOLVING_LABEL = "Resolving…";
const PLANT_WIDE_LABEL = "Plant-wide";

export type HistoryMessage = { role: "user" | "assistant"; content: string };

export function buildQueryHistory(turns: Pick<SessionTurn, "equipmentId" | "query" | "synthesis">[]): HistoryMessage[] {
  return turns.slice(-HISTORY_TURNS).flatMap(turn => {
    const asked: HistoryMessage = { role: "user", content: clamp(`[${scopeLabel(turn.equipmentId)}] ${turn.query}`) };
    const answer = turn.synthesis ? assistantText(turn.synthesis) : "";
    return answer ? [asked, { role: "assistant", content: clamp(answer) }] : [asked];
  });
}

function assistantText(synthesis: SynthesisResult): string {
  if (synthesis.response_type === "chat") return (synthesis.message ?? "").trim();
  return `${synthesis.risk_level} risk — ${synthesis.risk_summary} ${synthesis.explanation ?? ""}`.trim();
}

function scopeLabel(equipmentId: string): string {
  return equipmentId && equipmentId !== RESOLVING_LABEL ? equipmentId : PLANT_WIDE_LABEL;
}

function clamp(text: string): string {
  return text.length > HISTORY_TURN_CHARS ? text.slice(0, HISTORY_TURN_CHARS) : text;
}
