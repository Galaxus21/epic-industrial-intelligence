/**
 * Tests — AgentPanel Component
 * Verifies correct rendering for agent status transitions.
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AgentPanel } from "@/components/Query/AgentPanel";
import type { AgentEvent } from "@/lib/types";

describe("AgentPanel", () => {
  it("renders all 6 agent labels", () => {
    render(<AgentPanel events={[]} isRunning={false} />);
    expect(screen.getByText("Equipment Brain")).toBeDefined();
    expect(screen.getByText("Maintenance Advisor")).toBeDefined();
    expect(screen.getByText("Compliance Agent")).toBeDefined();
    expect(screen.getByText("Lessons Learned")).toBeDefined();
    expect(screen.getByText("Document Intelligence")).toBeDefined();
    expect(screen.getByText("AI Synthesizer")).toBeDefined();
  });

  it("shows message when agent is active", () => {
    const events: AgentEvent[] = [
      { agent: "equipment_brain", status: "active", message: "Loading equipment memory…" },
    ];
    render(<AgentPanel events={events} isRunning={true} />);
    expect(screen.getByText("Loading equipment memory…")).toBeDefined();
  });

  it("shows done message when agent completes", () => {
    const events: AgentEvent[] = [
      { agent: "maintenance_advisor", status: "done", message: "Found 1 overdue task(s)" },
    ];
    render(<AgentPanel events={events} isRunning={false} />);
    expect(screen.getByText("Found 1 overdue task(s)")).toBeDefined();
  });
});
