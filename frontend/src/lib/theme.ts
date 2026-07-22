/**
 * AI Operations Brain — Design Theme
 * Industrial Dark palette: charcoal (#0f0f0f) / amber (#f59e0b) / green (#10b981)
 * Single source of truth for all colour decisions.
 */
export const THEME = {
  colors: {
    bg: {
      base: "#0f0f0f",
      surface: "#1a1a1a",
      card: "#1f1f1f",
      elevated: "#242424",
    },
    border: {
      DEFAULT: "#2a2a2a",
      light: "#333333",
    },
    amber: { light: "#fbbf24", DEFAULT: "#f59e0b", dark: "#d97706" },
    emerald: { light: "#34d399", DEFAULT: "#10b981", dark: "#059669" },
    red: { light: "#f87171", DEFAULT: "#ef4444", dark: "#dc2626" },
    orange: { light: "#fb923c", DEFAULT: "#f97316", dark: "#ea580c" },
    blue: { light: "#60a5fa", DEFAULT: "#3b82f6", dark: "#2563eb" },
    purple: { light: "#c084fc", DEFAULT: "#a855f7", dark: "#9333ea" },
    text: {
      primary: "#f9f9f9",
      secondary: "#a0a0a0",
      muted: "#6b7280",
    },
  },

  /** Map risk level string → colour token */
  riskColor: {
    Critical: "#ef4444",
    High: "#f97316",
    Medium: "#f59e0b",
    Low: "#10b981",
  } as Record<string, string>,

  /** Map equipment type → accent colour for graph nodes */
  equipmentColor: {
    "Centrifugal Pump": "#f59e0b",
    "Compressor": "#a855f7",
    "Heat Exchanger": "#3b82f6",
    "Pressure Vessel": "#14b8a6",
    "Valve": "#f97316",
  } as Record<string, string>,

  /** Map agent id → colour for the agent panel */
  agentColor: {
    equipment_brain: "#a855f7",
    maintenance_advisor: "#3b82f6",
    compliance_agent: "#10b981",
    lessons_learned: "#f59e0b",
    document_intelligence: "#f97316",
    synthesizer: "#ec4899",
  } as Record<string, string>,

  agentLabel: {
    equipment_brain: "Equipment Brain",
    maintenance_advisor: "Maintenance Advisor",
    compliance_agent: "Compliance Agent",
    lessons_learned: "Lessons Learned",
    document_intelligence: "Document Intelligence",
    synthesizer: "AI Synthesizer",
  } as Record<string, string>,

  /** Map graph node type → colour for ForceGraph */
  graphNodeColor: {
    equipment: "#f59e0b",
    incident: "#ef4444",
    maintenance: "#3b82f6",
    maintenance_overdue: "#f97316",
    document: "#a855f7",
    regulation: "#14b8a6",
    technician: "#10b981",
    spare_part: "#6b7280",
    component: "#ec4899",
    location: "#64748b",
  } as Record<string, string>,
} as const;
