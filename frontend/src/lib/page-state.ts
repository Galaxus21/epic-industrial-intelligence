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
 *   permits         — filterStatus, filterType
 *   inspections     — activeTab (inspections | actions)
 *   managedWorkOrders — filterStatus
 *   procedures      — search text, filterStatus, filterType
 *   drawings        — selected drawing ID, scope project/plant, expanded tree, search
 *   audit           — tab, all filters (eqFilter, objType, actionFilter, days, relEq)
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

export interface PermitsSlice {
  filterStatus: string;
  filterType: string;
}

export interface InspectionsSlice {
  activeTab: "inspections" | "actions";
}

export interface ManagedWorkOrdersSlice {
  filterStatus: string;
}

export interface ProceduresSlice {
  search: string;
  filterStatus: string;
  filterType: string;
}

export interface DrawingsSlice {
  selectedId: string | null;
  scopeProjectId: string | undefined;
  scopePlantId: string | undefined;
  expandedProjectIds: string[];
  search: string;
}

export interface AuditSlice {
  tab: "log" | "relations";
  objType: string;
  eqFilter: string;
  actionFilter: string;
  days: number;
  relEq: string;
}

export interface DocumentsSlice {
  selectedDocId: string | null;
}

export interface PlantSlice {
  /** Per-area open/collapsed state: key = area.id, value = explicit boolean */
  areaOpenStates: Record<string, boolean>;
}

// ── Store interface ────────────────────────────────────────────────────────────

interface PageStateStore {
  query: QuerySlice;
  sensors: SensorsSlice;
  permits: PermitsSlice;
  inspections: InspectionsSlice;
  managedWorkOrders: ManagedWorkOrdersSlice;
  procedures: ProceduresSlice;
  drawings: DrawingsSlice;
  audit: AuditSlice;
  documents: DocumentsSlice;
  plant: PlantSlice;

  // Shallow-merge updaters
  updateQuery: (patch: Partial<QuerySlice>) => void;
  /** Supports both direct arrays and functional (prev => next) updaters for turns. */
  setQueryTurns: (updater: SessionTurn[] | ((prev: SessionTurn[]) => SessionTurn[])) => void;
  updateSensors: (patch: Partial<SensorsSlice>) => void;
  updatePermits: (patch: Partial<PermitsSlice>) => void;
  updateInspections: (patch: Partial<InspectionsSlice>) => void;
  updateManagedWorkOrders: (patch: Partial<ManagedWorkOrdersSlice>) => void;
  updateProcedures: (patch: Partial<ProceduresSlice>) => void;
  updateDrawings: (patch: Partial<DrawingsSlice>) => void;
  updateAudit: (patch: Partial<AuditSlice>) => void;
  updateDocuments: (patch: Partial<DocumentsSlice>) => void;
  updatePlant: (patch: Partial<PlantSlice>) => void;
}

// ── Store ──────────────────────────────────────────────────────────────────────

export const usePageState = create<PageStateStore>()((set) => ({
  // Initial values mirror the original useState defaults in each page
  query:              { turns: [], equipmentId: "", draft: "" },
  sensors:            { equipmentId: "" },
  permits:            { filterStatus: "all", filterType: "all" },
  inspections:        { activeTab: "inspections" },
  managedWorkOrders:  { filterStatus: "all" },
  procedures:         { search: "", filterStatus: "all", filterType: "all" },
  drawings:           { selectedId: null, scopeProjectId: undefined, scopePlantId: undefined, expandedProjectIds: [], search: "" },
  audit:              { tab: "log", objType: "", eqFilter: "", actionFilter: "", days: 30, relEq: "" },
  documents:          { selectedDocId: null },
  plant:              { areaOpenStates: {} },

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

  updatePermits: (patch) =>
    set((s) => ({ permits: { ...s.permits, ...patch } })),

  updateInspections: (patch) =>
    set((s) => ({ inspections: { ...s.inspections, ...patch } })),

  updateManagedWorkOrders: (patch) =>
    set((s) => ({ managedWorkOrders: { ...s.managedWorkOrders, ...patch } })),

  updateProcedures: (patch) =>
    set((s) => ({ procedures: { ...s.procedures, ...patch } })),

  updateDrawings: (patch) =>
    set((s) => ({ drawings: { ...s.drawings, ...patch } })),

  updateAudit: (patch) =>
    set((s) => ({ audit: { ...s.audit, ...patch } })),

  updateDocuments: (patch) =>
    set((s) => ({ documents: { ...s.documents, ...patch } })),

  updatePlant: (patch) =>
    set((s) => ({ plant: { ...s.plant, ...patch } })),
}));
