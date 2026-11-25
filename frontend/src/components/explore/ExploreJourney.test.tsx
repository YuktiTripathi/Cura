import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExploreJourney } from "./ExploreJourney";
import type { HealthView } from "../../lib/api";

const view = {
  state: "ready",
  snapshot_version: "2.3",
  overview: {
    categories: [{ id: "liver_health", name: "Liver", description: "How your liver works.", measured: { total: 1 }, risks: { assessed: 1 }, status: "worth_attention", status_label: "Worth a look" }],
    provenance: { blood_report_date: "2026-08-21" },
  },
  categories: {
    liver_health: {
      id: "liver_health",
      name: "Liver",
      about: "Your liver processes food.",
      findings: [
        { id: "alt", source_type: "measured", name: "ALT", value: 48, unit: "U/L", status: "above_range", status_label: "Above range", reference_low: 0, reference_high: 40, education: { name: "ALT", what_it_is: "An enzyme in liver cells.", body: "Liver cells contain ALT.", content_source: "medical_knowledge_v2.3" } },
        { id: "risk:nafld", source_type: "predicted_risk", name: "Fatty liver", status: "risk_healthy", status_label: "Healthy predicted risk", classification: "Healthy" },
      ],
    },
  },
  findings: {},
  related_keys: {},
  suggested_questions: { liver_health: ["What do my liver results show?"] },
} as unknown as HealthView;
view.findings = Object.fromEntries((view.categories.liver_health.findings ?? []).map((item) => [item.id, item]));

describe("ExploreJourney", () => {
  it("opens a category and a biomarker from the cached view", () => {
    const onPlace = vi.fn();
    const { rerender } = render(
      <ExploreJourney view={view} loading={false} error={false} name="Alex" place="home" categoryId={null} findingId={null} onPlace={onPlace} onAsk={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { name: "Hello, Alex" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Explore my health" }));
    expect(onPlace).toHaveBeenCalledWith("overview");
    rerender(<ExploreJourney view={view} loading={false} error={false} name="Alex" place="overview" categoryId={null} findingId={null} onPlace={onPlace} onAsk={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Liver/ }));
    expect(onPlace).toHaveBeenCalledWith("category", "liver_health");
    rerender(<ExploreJourney view={view} loading={false} error={false} name="Alex" place="category" categoryId="liver_health" findingId={null} onPlace={onPlace} onAsk={vi.fn()} />);
    expect(screen.getByText("Above range")).toBeTruthy();
    expect(screen.getAllByText("Healthy").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /ALT/ }));
    rerender(<ExploreJourney view={view} loading={false} error={false} name="Alex" place="marker" categoryId="liver_health" findingId="alt" onPlace={onPlace} onAsk={vi.fn()} />);
    expect(screen.getByText("Liver cells contain ALT.")).toBeTruthy();
    expect(screen.getByText(/Reference range 0–40/)).toBeTruthy();
  });
});
