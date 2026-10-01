/**
 * Accessibility smoke tests: axe-core on the richest UI states. jsdom cannot judge colour contrast,
 * so that rule is off here; contrast was checked in a real browser (both themes) with axe + Lighthouse.
 */
import axe from "axe-core";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "./test/render";
import { MessageList } from "./components/MessageList";
import { MarkerPanel } from "./components/marker/MarkerPanel";
import { ReviewValues } from "./components/documents/ReviewValues";
import type { StructuredResponse } from "./types/chat";

vi.mock("./lib/api", async () => {
  const actual = await vi.importActual<typeof import("./lib/api")>("./lib/api");
  return {
    ...actual,
    getDocumentFacts: vi.fn(async () => ({
      document_id: "d1",
      filename: "labs.pdf",
      ready: true,
      facts: [{ key: "ldl", label: "LDL cholesterol", value: 142, unit: "mg/dL", reference_high: 100, page: 1, line: 2, excerpt: "LDL 142 mg/dL (ref < 100)" }],
    })),
  };
});

async function violations(container: Element = document.body) {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

const presentation: StructuredResponse = {
  mode: "RESULT_LIST",
  summary: "Lipid health from your latest records.",
  findings: [
    { label: "LDL cholesterol", value: "138.0", unit: "mg/dL", status: "high", canonical_key: "ldl", numeric_value: 138, reference_low: 0, reference_high: 100 },
    { label: "HDL cholesterol", value: "41.0", unit: "mg/dL", status: "in_range", canonical_key: "hdl", numeric_value: 41, reference_low: 40, reference_high: 60 },
  ],
  uncertainties: [],
  next_steps: ["Recheck lipids in 3 months."],
  proactive_insights: [{ title: "Something changed", summary: "LDL improved but remains high.", entity: "ldl" }],
  clinician_handoff: { key_findings: ["LDL 138 mg/dL (high)"] },
  suggestion_chips: ["What can I do about LDL?"],
};

describe("accessibility (axe)", () => {
  afterEach(() => cleanup());

  it("a rich answer has no violations", async () => {
    render(
      <MessageList
        messages={[
          { role: "user", content: "Show my lipid results" },
          {
            role: "assistant",
            content: "Lipid health from your latest records.",
            presentation,
            evidence: [{ evidence_id: "e", report_id: "r", report_type: "blood_report", report_date: "2026-08-18", marker: "LDL", value: 138, unit: "mg/dL" }],
            provenance: { type: "personal_health", sources: [{ name: "Latest blood report · 18 Aug 2026", source_type: "personal_record" }] },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
        onRegenerate={vi.fn()}
        onEditQuestion={vi.fn()}
      />
    );
    expect(await violations()).toEqual([]);
  });

  it("the marker panel has no violations", async () => {
    render(
      <MarkerPanel
        marker={{
          key: "ldl", label: "LDL cholesterol", value: 138, unit: "mg/dL", reference_low: 0, reference_high: 100, status: "high",
          measured_on: "2026-08-18", previous_value: 142, previous_on: "2026-07-09", trend: "toward_range",
          history: [{ date: "2026-07-09", value: 142, status: "high" }, { date: "2026-08-18", value: 138, status: "high" }],
        }}
        onClose={vi.fn()}
        onAsk={vi.fn()}
      />
    );
    expect(await violations()).toEqual([]);
  });

  it("the review dialog has no violations", async () => {
    render(<ReviewValues documentId="d1" onOpenChange={vi.fn()} onCompare={vi.fn()} onAsk={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId("review-row")).toBeTruthy());
    expect(await violations()).toEqual([]);
  });
});
