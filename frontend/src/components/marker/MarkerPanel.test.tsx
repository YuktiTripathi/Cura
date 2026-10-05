import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "../../test/render";
import type { MarkerOverview } from "../../types/overview";
import { MarkerPanel } from "./MarkerPanel";

const ldl: MarkerOverview = {
  key: "ldl",
  label: "LDL cholesterol",
  value: 138,
  unit: "mg/dL",
  reference_low: 0,
  reference_high: 100,
  status: "high",
  measured_on: "2026-08-18",
  previous_value: 142,
  previous_on: "2026-07-09",
  trend: "toward_range",
  history: [
    { date: "2026-07-09", value: 142, status: "high" },
    { date: "2026-08-18", value: 138, status: "high" },
  ],
};

const vitaminD: MarkerOverview = {
  key: "vitamin_d",
  label: "Vitamin D",
  value: 12.6,
  unit: "ng/mL",
  reference_low: 30,
  reference_high: 100,
  status: "low",
  measured_on: "2026-08-18",
  previous_value: 18,
  previous_on: "2026-07-09",
  trend: "away_from_range",
  history: [
    { date: "2026-07-09", value: 18, status: "low" },
    { date: "2026-08-18", value: 12.6, status: "low" },
  ],
};

const tsh: MarkerOverview = {
  key: "tsh",
  label: "TSH",
  value: 2.1,
  unit: "µIU/mL",
  reference_low: 0.4,
  reference_high: 4,
  status: "normal",
  measured_on: "2026-08-18",
  trend: "in_range",
  history: [{ date: "2026-08-18", value: 2.1, status: "normal" }],
};

describe("MarkerPanel", () => {
  afterEach(() => cleanup());

  it("shows the trend, every result and marker-scoped questions", () => {
    const onAsk = vi.fn();
    const onClose = vi.fn();
    render(<MarkerPanel marker={ldl} onClose={onClose} onAsk={onAsk} />);
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

  it("ignores Escape pressed inside a dialog", () => {
    const onClose = vi.fn();
    render(<MarkerPanel marker={ldl} onClose={onClose} onAsk={vi.fn()} />);
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    const inner = document.createElement("button");
    dialog.appendChild(inner);
    document.body.appendChild(dialog);
    fireEvent.keyDown(inner, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    dialog.remove();
  });

  it("explains when there is only one result", () => {
    render(<MarkerPanel marker={tsh} onClose={vi.fn()} onAsk={vi.fn()} />);
    expect(screen.queryByTestId("trend-chart")).toBeNull();
    expect(screen.getByText(/Only one result so far/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "How has it changed?" })).toBeNull();
  });

  it("reveals a point's value on hover or keyboard focus", () => {
    render(<MarkerPanel marker={vitaminD} onClose={vi.fn()} onAsk={vi.fn()} />);
    const points = screen.getByTestId("trend-chart").querySelectorAll(".trend-hit");
    fireEvent.focus(points[0]);
    expect(screen.getByRole("status").textContent).toContain("18 ng/mL");
    expect(screen.getByRole("status").textContent).toContain("Outside reference range");
  });
});
