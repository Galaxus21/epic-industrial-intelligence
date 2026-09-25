/**
 * AI Operations Brain — Page State Store
 *
 * Single Zustand store that persists meaningful UI state across route
 * navigations in Next.js App Router (React 18 equivalent of React 19's
 * <Activity> keep-alive pattern — state lives in JS module scope, outside
 * the React component lifecycle, so it survives unmount/remount on nav).
 *
 * WHAT IS PERSISTED (per page):
 *   query           — chat turns, selected equipment ID, draft input text
 *   sensors         — selected equipment ID
 *   documents       — selected document ID
 *
 * WHAT IS NOT PERSISTED (stays in local useState):
 *   loading / saving / error — always re-derived on each visit
 *   modal open/close states  — intentionally reset
 *   API response data        — re-fetched on each visit
 *   form fields              — always start fresh
 */

import { create } from "zustand";
import type { SessionTurn } from "./types";

// ── Slice types ────────────────────────────────────────────────────────────────

export interface QuerySlice {
  turns: SessionTurn[];
  equipmentId: string;
  draft: string;
}

export interface SensorsSlice {
  equipmentId: string;
}

export interface DocumentsSlice {
  selectedDocId: string | null;
}

// ── Store interface ────────────────────────────────────────────────────────────

interface PageStateStore {
  query: QuerySlice;
  sensors: SensorsSlice;
  documents: DocumentsSlice;

  // Shallow-merge updaters
  updateQuery: (patch: Partial<QuerySlice>) => void;
  /** Supports both direct arrays and functional (prev => next) updaters for turns. */
  setQueryTurns: (updater: SessionTurn[] | ((prev: SessionTurn[]) => SessionTurn[])) => void;
  updateSensors: (patch: Partial<SensorsSlice>) => void;
  updateDocuments: (patch: Partial<DocumentsSlice>) => void;
}

// ── Store ──────────────────────────────────────────────────────────────────────

export const usePageState = create<PageStateStore>()((set) => ({
  // Initial values mirror the original useState defaults in each page
  query:              { turns: [], equipmentId: "", draft: "" },
  sensors:            { equipmentId: "" },
  documents:          { selectedDocId: null },

  updateQuery: (patch) =>
    set((s) => ({ query: { ...s.query, ...patch } })),

  setQueryTurns: (updater) =>
    set((s) => ({
      query: {
        ...s.query,
        turns: typeof updater === "function" ? updater(s.query.turns) : updater,
      },
    })),

  updateSensors: (patch) =>
    set((s) => ({ sensors: { ...s.sensors, ...patch } })),

  updateDocuments: (patch) =>
    set((s) => ({ documents: { ...s.documents, ...patch } })),
}));
