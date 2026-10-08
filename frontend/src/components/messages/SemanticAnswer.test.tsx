import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ResolvedValue, SemanticResponse } from "../../types/semantic";
import { SemanticAnswer } from "./SemanticAnswer";

const hba1c: ResolvedValue = {
  key: "blood.hba1c.latest", label: "HbA1c", kind: "blood", value: 9.1, unit: "%", status: "high",
  reference_low: 4, reference_high: 5.6, date: "2026-09-28",
};
const t2d: ResolvedValue = { key: "bioai.type_2_diabetes", label: "Type 2 diabetes", kind: "bio_ai", value: 78, status: "high" };

function show(response: Partial<SemanticResponse>) {
  return render(<SemanticAnswer response={{ summary: "Summary.", blocks: [], follow_ups: [], sources: [], ...response }} />);
}

afterEach(cleanup);

describe("SemanticAnswer", () => {
  it("summary alone stands on its own", () => {
    show({ summary: "Your **HbA1c** is above range." });
    expect(screen.getByText("HbA1c").tagName).toBe("STRONG");
    expect(document.querySelectorAll(".sem-block")).toHaveLength(0);
  });

  it("renders every block type from one generic switch", () => {
    show({
      blocks: [
        { type: "text", title: "Note", text: "A separate idea." },
        { type: "metric", values: [hba1c] },
        { type: "metric_group", title: "Glucose control", values: [hba1c] },
        { type: "risk", title: "Risk overview", values: [t2d] },
        { type: "comparison", title: "Since last time", values: [{ ...hba1c, key: "blood.hba1c.trend", previous: 8.4, direction: "increased" }] },
        { type: "insight", title: "Why", text: "These point the same way.", values: [hba1c] },
        { type: "reassurance", title: "Reassuring", text: "Liver and kidney look fine." },
        { type: "priority_list", title: "Top 3", items: [{ title: "Blood sugar" }, { title: "Lipids" }] },
        { type: "action_list", title: "Next", items: [{ title: "Walk after meals" }] },
        { type: "nutrition", title: "Food", increase: ["Vegetables"], reduce: ["Refined grains"], text: "Why it matters." },
        { type: "warning", text: "Talk to your doctor soon." },
      ],
    });
    expect(document.querySelectorAll(".sem-block")).toHaveLength(11);
    expect(screen.getByText("Risk overview")).toBeTruthy();
    expect(screen.getByText("8.4%")).toBeTruthy();
    expect(screen.getByText("Refined grains")).toBeTruthy();
    expect(document.querySelector("ol.sem-list")).not.toBeNull(); // priorities are ranked
  });

  it("ignores unknown block types instead of failing", () => {
    // @ts-expect-error - an unknown type from a newer backend
    show({ blocks: [{ type: "carousel", title: "x" }] });
    expect(screen.getByText("Summary.")).toBeTruthy();
    expect(screen.queryByText("x")).toBeNull();
  });

  it("does not render HTML from text", () => {
    show({ summary: "<img src=x onerror=alert(1)> hi" });
    expect(document.querySelector("img")).toBeNull();
  });

  it("a collapsed group starts folded", () => {
    show({ blocks: [{ type: "metric_group", title: "All 20 results", collapsed: true, values: [hba1c] }] });
    expect(screen.queryByText("9.1%")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /show all 20 results/i }));
    expect(screen.getByText("9.1%")).toBeTruthy();
  });

  it("sources sit behind one compact affordance", () => {
    show({ sources: [{ type: "blood_report", date: "2026-09-28" }, { type: "medical_reference", label: "CDC" }] });
    expect(screen.getByText("Sources (2)")).toBeTruthy();
  });
});
