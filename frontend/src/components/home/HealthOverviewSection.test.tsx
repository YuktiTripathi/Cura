import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "../../test/render";
import type { HealthOverview } from "../../types/overview";
import { MarkerPanelProvider } from "../marker/MarkerPanelContext";
import { MarkerPanel } from "../marker/MarkerPanel";
import { HealthOverviewSection } from "./HealthOverviewSection";

const overview: HealthOverview = {
  available: true,
  latest_report_date: "2026-08-18",
  markers: [
    {
      key: "ldl", label: "LDL cholesterol", value: 138, unit: "mg/dL", reference_low: 0, reference_high: 100, status: "high",
      measured_on: "2026-08-18", previous_value: 142, previous_on: "2026-07-09", trend: "toward_range",
      history: [
        { date: "2026-07-09", value: 142, status: "high" },
        { date: "2026-08-18", value: 138, status: "high" },
      ],
    },
    {
      key: "vitamin_d", label: "Vitamin D", value: 12.6, unit: "ng/mL", reference_low: 30, reference_high: 100, status: "low",
      measured_on: "2026-08-18", previous_value: 18, previous_on: "2026-07-09", trend: "away_from_range",
      history: [
        { date: "2026-07-09", value: 18, status: "low" },
        { date: "2026-08-18", value: 12.6, status: "low" },
      ],
    },
    {
      key: "tsh", label: "TSH", value: 2.1, unit: "µIU/mL", reference_low: 0.4, reference_high: 4, status: "normal",
      measured_on: "2026-08-18", trend: "in_range", history: [{ date: "2026-08-18", value: 2.1, status: "normal" }],
    },
  ],
  insights: [{ title: "One pattern is still present", summary: "Vitamin D remains abnormal across reports.", marker_key: "vitamin_d" }],
  scores: [],
  reports: [{ title: "Latest blood report", date: "2026-08-18" }],
};

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getOverview: vi.fn(async () => overview) };
});

describe("HealthOverviewSection", () => {
  afterEach(() => cleanup());

  it("shows out-of-range values, what is improving and what is worth a look", async () => {
    const open = vi.fn();
    const onSend = vi.fn();
    render(
      <MarkerPanelProvider value={{ has: (key) => key === "ldl" || key === "vitamin_d", open }}>
        <HealthOverviewSection onSend={onSend} />
      </MarkerPanelProvider>
    );
    await waitFor(() => expect(screen.getByTestId("health-home")).toBeTruthy());
    const cards = screen.getAllByTestId("value-card").map((card) => card.textContent);
    expect(cards).toHaveLength(2);
    expect(cards[0]).toContain("Improving · was 142");
    expect(cards[1]).toContain("Further from range · was 18");
    expect(screen.getByRole("button", { name: /LDL cholesterol: 142 → 138 mg\/dL/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "LDL cholesterol history" }));
    expect(open).toHaveBeenCalledWith("ldl");

    fireEvent.click(screen.getByRole("button", { name: "Ask Cura" }));
    expect(onSend).toHaveBeenCalledWith("What should I know about my Vitamin D?", [], {
      type: "blood_marker",
      source: "supershyft",
      marker_code: "vitamin_d",
    });

    fireEvent.click(screen.getByRole("button", { name: "See all 3 latest results" }));
    expect(screen.getByText("TSH")).toBeTruthy();
  });
});

describe("MarkerPanel", () => {
  afterEach(() => cleanup());

  it("shows the trend, every result and marker-scoped questions", () => {
    const onAsk = vi.fn();
    const onClose = vi.fn();
    render(<MarkerPanel marker={overview.markers![0]} onClose={onClose} onAsk={onAsk} />);
    expect(screen.getByRole("heading", { name: "LDL cholesterol" })).toBeTruthy();
    expect(document.activeElement?.id).toBe("marker-panel-title");
    expect(screen.getByText("Moving toward the reference range")).toBeTruthy();
    expect(screen.getByTestId("trend-chart")).toBeTruthy();
    const rows = screen.getByRole("table", { name: "LDL cholesterol results" }).querySelectorAll("tbody tr");
    expect(Array.from(rows).map((row) => row.textContent)).toEqual([
      expect.stringContaining("138 mg/dL"),
      expect.stringContaining("142 mg/dL"),
    ]);
    fireEvent.click(screen.getByRole("button", { name: "How has it changed?" }));
    expect(onAsk).toHaveBeenCalledWith("How has my LDL cholesterol changed over time?", {
      type: "blood_marker",
      source: "supershyft",
      marker_code: "ldl",
    });
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });

  it("explains when there is only one result", () => {
    render(<MarkerPanel marker={overview.markers![2]} onClose={vi.fn()} onAsk={vi.fn()} />);
    expect(screen.queryByTestId("trend-chart")).toBeNull();
    expect(screen.getByText(/Only one result so far/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "How has it changed?" })).toBeNull();
  });

  it("reveals a point's value on hover or keyboard focus", () => {
    render(<MarkerPanel marker={overview.markers![1]} onClose={vi.fn()} onAsk={vi.fn()} />);
    const points = screen.getByTestId("trend-chart").querySelectorAll(".trend-hit");
    fireEvent.focus(points[0]);
    expect(screen.getByRole("status").textContent).toContain("18 ng/mL");
    expect(screen.getByRole("status").textContent).toContain("Outside reference range");
  });
});
