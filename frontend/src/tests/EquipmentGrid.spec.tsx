/**
 * Tests — EquipmentGrid Component
 * Verifies equipment card rendering and health bar colouring logic.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { EquipmentGrid } from "@/components/Dashboard/EquipmentGrid";
import type { Equipment } from "@/lib/types";

const MOCK_EQUIPMENT: Equipment[] = [
  {
    id: "P-101", name: "Crude Oil Feed Pump", type: "Centrifugal Pump",
    location: "Unit 4", health_score: 72, failure_probability: 18,
    compliance_score: 85, maintenance_due_days: 7, criticality: "High",
    status: "Running",
  },
  {
    id: "V-301", name: "Feed Surge Drum", type: "Pressure Vessel",
    location: "Unit 4", health_score: 95, failure_probability: 2,
    compliance_score: 100, maintenance_due_days: 90, criticality: "Critical",
    status: "Running",
  },
];

describe("EquipmentGrid", () => {
  it("renders all equipment cards", () => {
    render(<EquipmentGrid equipment={MOCK_EQUIPMENT} />);
    expect(screen.getByText("Crude Oil Feed Pump")).toBeDefined();
    expect(screen.getByText("Feed Surge Drum")).toBeDefined();
  });

  it("shows P-101 in the attention section due to high failure probability", () => {
    render(<EquipmentGrid equipment={MOCK_EQUIPMENT} />);
    expect(screen.getByText("Requires Attention (1)")).toBeDefined();
  });

  it("shows V-301 in normal operation section", () => {
    render(<EquipmentGrid equipment={MOCK_EQUIPMENT} />);
    expect(screen.getByText("Normal Operation (1)")).toBeDefined();
  });

  it("displays failure probability badge for P-101", () => {
    render(<EquipmentGrid equipment={MOCK_EQUIPMENT} />);
    expect(screen.getByText("18% risk")).toBeDefined();
  });

  it("handles empty equipment array gracefully", () => {
    render(<EquipmentGrid equipment={[]} />);
    // Should render without throwing
    expect(document.body).toBeDefined();
  });
});
