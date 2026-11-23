import axe from "axe-core";
import { createRef, useState } from "react";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithQuery as render } from "../../test/render";
import { WelcomeExperience } from "../WelcomeExperience";
import { BodySystemOverviewView } from "./BodySystemOverviewView";
import { RiskOverviewView } from "./RiskOverviewView";
import type { BiomarkerResult, BodySystemOverview, RiskOverview, SystemSummary } from "../../types/bodySystems";

const getBodySystems = vi.fn();
const getRiskOverview = vi.fn();
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, getBodySystems: (...a: unknown[]) => getBodySystems(...a), getRiskOverview: (...a: unknown[]) => getRiskOverview(...a) };
});

const counts = (over: Partial<SystemSummary["status_breakdown"]> = {}) => ({ normal: 0, low: 0, high: 0, critical: 0, no_range: 0, no_value: 0, ...over });

function result(over: Partial<BiomarkerResult>): BiomarkerResult {
  return {
    result_id: "r:x", original_name: "X", display_name: "X", system_id: "heart_circulation", secondary_system_ids: [], status: "normal",
    status_source: "report_flag", mapping_method: "source_label", needs_mapping_review: false, is_derived: false, duplicates_collapsed: 0,
    conflicting_values: [], history: [], ...over,
  } as BiomarkerResult;
}

const ldl = result({
  result_id: "r1:ldl", original_name: "LDL Cholestrol Calculated", display_name: "LDL Cholesterol Calculated", cura_key: "ldl", value: 138, unit: "mg/dL",
  reference_high: 100, status: "high", source_group: "Lipid Profile", previous_value: 150, previous_on: "2026-01-05", trend: "toward_range",
  history: [{ date: "2026-01-05", value: 150, status: "high" }, { date: "2026-08-18", value: 138, status: "high" }],
});
const hdl = result({ result_id: "r1:hdl", original_name: "HDL Cholestrol Direct", display_name: "HDL Cholesterol Direct", cura_key: "hdl", value: 48, unit: "mg/dL", reference_low: 40, status: "normal" });
const alt = result({ result_id: "r1:alt", original_name: "SGPT (ALT)", display_name: "SGPT (ALT)", system_id: "liver_health", value: 28, unit: "U/L", reference_high: 45, status: "normal" });
const mg = result({ result_id: "r1:mg", original_name: "Magnesium", display_name: "Magnesium", system_id: "vitamins_nutrition", secondary_system_ids: ["sleep_recovery"], value: 1.4, unit: "mg/dL", reference_low: 1.7, status: "low" });

function system(over: Partial<SystemSummary>): SystemSummary {
  return {
    id: "heart_circulation", name: "Heart & Circulation", scope: "primary", available_count: 2, abnormal_count: 1,
    status_breakdown: counts({ normal: 1, high: 1 }), state: "attention", key_findings: [{ result_id: "r1:ldl", label: "LDL Cholesterol Calculated", value: 138, unit: "mg/dL", status: "high", how_far: "moderately" }],
    result_ids: ["r1:ldl", "r1:hdl"], related_result_ids: [], related_abnormal_count: 0, group_coverage: [], needs_mapping_review: false, subsections: [], ...over,
  } as SystemSummary;
}

function overview(over: Partial<BodySystemOverview> = {}): BodySystemOverview {
  return {
    available: true, state: "ready", registry_version: "1.0", report: { report_id: "r1", report_date: "2026-08-18" }, available_reports: [{ report_id: "r1", report_date: "2026-08-18" }],
    totals: { unique_results: 4, abnormal: 2, status_breakdown: counts({ normal: 2, high: 1, low: 1 }), unmapped: 0, allergy: 0, duplicates_collapsed: 0, conflicting_duplicates: 0 },
    systems: [
      system({}),
      system({ id: "liver_health", name: "Liver Health", available_count: 1, abnormal_count: 0, status_breakdown: counts({ normal: 1 }), state: "all_in_range", key_findings: [], result_ids: ["r1:alt"] }),
      system({ id: "sleep_recovery", name: "Sleep & Recovery", scope: "related_only", available_count: 1, abnormal_count: 1, status_breakdown: counts({ low: 1 }), key_findings: [], result_ids: [], related_result_ids: ["r1:mg"], caveat: "These results are related to recovery. They do not measure how well you sleep." }),
    ],
    results: [ldl, hdl, alt, mg], ...over,
  } as BodySystemOverview;
}

// The page owns the opened card so the header Back button can step out of it. This stands in for it.
function Blood({ onAsk }: { onAsk: (text: string, ref: never) => void }) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <>
      <button type="button" onClick={() => setOpenId(null)}>Back</button>
      <BodySystemOverviewView onAsk={onAsk as never} openId={openId} onOpenChange={setOpenId} />
    </>
  );
}
function Risk({ onAsk }: { onAsk: (text: string, ref: never) => void }) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <>
      <button type="button" onClick={() => setOpenId(null)}>Back</button>
      <RiskOverviewView onAsk={onAsk as never} openId={openId} onOpenChange={setOpenId} />
    </>
  );
}

async function violations(container: Element) {
  const found = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  return found.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

beforeEach(() => {
  getBodySystems.mockReset();
  getRiskOverview.mockReset();
});
afterEach(() => cleanup());

describe("BodySystemOverviewView", () => {
  it("shows one card per system the report holds and nothing else", async () => {
    getBodySystems.mockResolvedValue(overview());
    render(<Blood onAsk={vi.fn()} />);
    const list = await screen.findByRole("list", { name: /body systems with results/i });
    expect(within(list).getAllByRole("button")).toHaveLength(3);
    expect(screen.queryByText("Thyroid Health")).toBeNull();
    expect(screen.getByText("2 results · 1 outside range")).toBeTruthy();
    expect(screen.getByText("1 result · all within range")).toBeTruthy();
    expect(screen.getByText(/Only tests on this report are shown/)).toBeTruthy();
  });

  it("opens a system, lists the result needing attention first, and asks with the marker as context", async () => {
    getBodySystems.mockResolvedValue(overview());
    const onAsk = vi.fn();
    render(<Blood onAsk={onAsk} />);
    fireEvent.click(await screen.findByRole("button", { name: /Heart & Circulation/ }));
    const rows = screen.getAllByRole("listitem");
    expect(rows[0].textContent).toContain("LDL Cholesterol Calculated");
    fireEvent.click(within(rows[0]).getByRole("button", { expanded: false }));
    expect(screen.getByRole("img", { name: /LDL Cholesterol Calculated 138 mg\/dL: above range/i })).toBeTruthy();
    expect(screen.getByText("Name on the report")).toBeTruthy();
    expect(screen.getByText("LDL Cholestrol Calculated")).toBeTruthy();
    expect(screen.getByTestId("trend-chart")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "How has it changed?" }));
    expect(onAsk).toHaveBeenCalledWith(
      "How has my LDL Cholesterol Calculated changed over time?",
      expect.objectContaining({ type: "blood_marker", marker_code: "ldl" })
    );
  });

  it("asks about a whole system with the report and its results named", async () => {
    getBodySystems.mockResolvedValue(overview());
    const onAsk = vi.fn();
    render(<Blood onAsk={onAsk} />);
    fireEvent.click(await screen.findByRole("button", { name: /Heart & Circulation/ }));
    fireEvent.click(screen.getByRole("button", { name: "Explain these results" }));
    const [text, ref] = onAsk.mock.calls[0];
    expect(text).toBe("Explain my Heart & Circulation results in simple words, especially LDL Cholesterol Calculated.");
    expect(text).not.toMatch(/\d/);
    expect(ref).toEqual(expect.objectContaining({ type: "blood_report", report_id: "r1" }));
    expect(ref.entry_point).toBeUndefined();
  });

  it("tells the member in plain words what each system covers", async () => {
    getBodySystems.mockResolvedValue(overview({ systems: [system({ about: "How your body handles the cholesterol and fats that affect your heart." })] }));
    render(<Blood onAsk={vi.fn()} />);
    expect(await screen.findByText(/cholesterol and fats that affect your heart/)).toBeTruthy();
  });

  it("shows the caveat and related results for a related-only system without counting them twice", async () => {
    getBodySystems.mockResolvedValue(overview());
    render(<Blood onAsk={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Sleep & Recovery/ }));
    expect(screen.getByText(/do not measure how well you sleep/)).toBeTruthy();
    expect(screen.getByText("Magnesium")).toBeTruthy();
  });

  it("goes back to the cards", async () => {
    getBodySystems.mockResolvedValue(overview());
    render(<Blood onAsk={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Liver Health/ }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByRole("list", { name: /body systems with results/i })).toBeTruthy();
  });

  it("offers a report picker only when there is more than one report and reloads on change", async () => {
    getBodySystems.mockResolvedValue(overview({ available_reports: [{ report_id: "r2", report_date: "2026-08-18" }, { report_id: "r1", report_date: "2026-01-05" }] }));
    render(<Blood onAsk={vi.fn()} />);
    const select = await screen.findByRole("combobox", { name: "Report" });
    fireEvent.change(select, { target: { value: "r1" } });
    await waitFor(() => expect(getBodySystems).toHaveBeenLastCalledWith("r1"));
  });

  it("does not show a picker for a single report", async () => {
    getBodySystems.mockResolvedValue(overview());
    render(<Blood onAsk={vi.fn()} />);
    await screen.findByRole("list", { name: /body systems/i });
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("says plainly when a report has no results and shows no cards", async () => {
    getBodySystems.mockResolvedValue(overview({ state: "no_results", systems: [], results: [] }));
    render(<Blood onAsk={vi.fn()} />);
    expect(await screen.findByText(/no results on this report/i)).toBeTruthy();
    expect(screen.queryByRole("list", { name: /body systems/i })).toBeNull();
  });

  it("falls back to the chat explanation when the overview cannot load", async () => {
    getBodySystems.mockRejectedValue(new Error("down"));
    const onAsk = vi.fn();
    render(<Blood onAsk={onAsk} />);
    fireEvent.click(await screen.findByRole("button", { name: /Explain my blood report in chat/ }));
    expect(onAsk).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ entry_point: "blood_report_overview" }));
  });

  it("has no accessibility violations on the cards or the opened detail", async () => {
    getBodySystems.mockResolvedValue(overview());
    const { container } = render(<Blood onAsk={vi.fn()} />);
    await screen.findByRole("list", { name: /body systems/i });
    expect(await violations(container)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: /Heart & Circulation/ }));
    fireEvent.click(screen.getAllByRole("button", { expanded: false })[0]);
    expect(await violations(container)).toEqual([]);
  });
});

function risks(over: Partial<RiskOverview> = {}): RiskOverview {
  return {
    available: true, state: "ready", registry_version: "1.0", disclaimer: "These are predicted risks from your Bio-AI assessment. They are not measured blood results and they are not diagnoses.",
    report: { report_id: "b1", report_date: "2026-08-18", source_line: "bio_ai", metabolic_age: 34 }, available_reports: [{ report_id: "b1", report_date: "2026-08-18", source_line: "bio_ai" }],
    same_day_alternatives: false, totals: { risk_count: 2, raised_count: 1, duplicates_collapsed: 0 },
    groups: [{ id: "heart_circulation", name: "Heart & Circulation", risk_count: 1, raised_count: 1, status_breakdown: { moderate: 1 }, key_findings: [{ code: "cardiac_health", name: "Cardiac health", score: 30, status: "moderate" }], risk_codes: ["cardiac_health"], needs_mapping_review: false },
      { id: "thyroid_health", name: "Thyroid Health", risk_count: 1, raised_count: 0, status_breakdown: { low: 1 }, key_findings: [], risk_codes: ["thyroid"], needs_mapping_review: false }],
    risks: [
      { code: "cardiac_health", name: "Cardiac health", group_id: "heart_circulation", kind: "predicted_risk", score: 30, status: "moderate", level: "raised", percentile: 55, contributing_factors: ["LDL"], history: [], duplicates_collapsed: 0 },
      { code: "thyroid", name: "Thyroid", group_id: "thyroid_health", kind: "predicted_risk", score: 12, status: "low", level: "not_raised", history: [], contributing_factors: [], duplicates_collapsed: 0 },
    ], ...over,
  } as RiskOverview;
}

describe("RiskOverviewView", () => {
  it("shows only returned risk areas, labelled as predictions, never as diagnoses", async () => {
    getRiskOverview.mockResolvedValue(risks());
    render(<Risk onAsk={vi.fn()} />);
    const list = await screen.findByRole("list", { name: /risk areas/i });
    expect(within(list).getAllByRole("button")).toHaveLength(2);
    expect(screen.getByText(/not measured blood results and they are not diagnoses/)).toBeTruthy();
    expect(screen.queryByText("Liver Health")).toBeNull();
  });

  it("leads with the summary, metabolic age and the risks that need attention", async () => {
    const data = risks();
    data.risks![0].about = "heart and blood vessel problems";
    getRiskOverview.mockResolvedValue(data);
    const onAsk = vi.fn();
    render(<Risk onAsk={onAsk} />);
    expect(await screen.findByText("Understand your future health")).toBeTruthy();
    const summary = screen.getByTestId("risk-summary");
    expect(within(summary).getByText("No raised risk")).toBeTruthy();
    expect(within(summary).getByText("Needs attention")).toBeTruthy();
    expect(screen.getByText("34 years")).toBeTruthy();
    const card = screen.getByTestId("attention-card");
    expect(within(card).getByText("moderate predicted risk")).toBeTruthy();
    expect(within(card).getByText(/higher risk of heart and blood vessel problems/)).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Understand this risk" }));
    expect(onAsk).toHaveBeenCalledWith("What does my Cardiac health risk result mean?", expect.objectContaining({ risk_code: "cardiac_health" }));
    expect(screen.queryByRole("img", { name: /illustration/i })).toBeNull();
  });

  it("shows the everyday name first with the medical name as the secondary line", async () => {
    const data = risks();
    data.risks![0] = { ...data.risks![0], display_name: "Heart Health", medical_name: "Cardiac health", about: "heart problems" };
    getRiskOverview.mockResolvedValue(data);
    const onAsk = vi.fn();
    render(<Risk onAsk={onAsk} />);
    const card = await screen.findByTestId("attention-card");
    expect(within(card).getByText("Heart Health")).toBeTruthy();
    expect(within(card).getByText("Cardiac health")).toBeTruthy();
    fireEvent.click(within(card).getByRole("button", { name: "Understand this risk" }));
    expect(onAsk).toHaveBeenCalledWith("What does my Heart Health risk result mean?", expect.objectContaining({ entry_point: "risk_explainer", risk_code: "cardiac_health" }));
  });

  it("asks different questions at the report level and at the health area level", async () => {
    const data = risks();
    data.groups![0] = { ...data.groups![0], topic: "heart health" };
    getRiskOverview.mockResolvedValue(data);
    const onAsk = vi.fn();
    render(<Risk onAsk={onAsk} />);
    fireEvent.click(await screen.findByRole("button", { name: "Which of my health risks need attention?" }));
    expect(onAsk).toHaveBeenCalledWith("Which of my health risks need attention?", expect.objectContaining({ type: "bio_ai_report", entry_point: "health_area" }));
    expect(screen.getByRole("button", { name: "How can I improve my overall health?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Heart & Circulation/ }));
    expect(screen.getByRole("button", { name: "Why is my heart health risk increased?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "What do my blood tests say about my heart health?" }));
    expect(onAsk).toHaveBeenLastCalledWith("What do my blood tests say about my heart health?", expect.objectContaining({ entry_point: "health_area" }));
    expect(screen.getByRole("button", { name: "What do my blood tests say about my heart health?" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Which of my health risks need attention?" })).toBeNull();
  });

  it("opens an area and asks about one risk with its code as context", async () => {
    getRiskOverview.mockResolvedValue(risks());
    const onAsk = vi.fn();
    render(<Risk onAsk={onAsk} />);
    fireEvent.click(await screen.findByRole("button", { name: /Heart & Circulation/ }));
    fireEvent.click(screen.getByRole("button", { name: /Cardiac health/ }));
    expect(screen.getByText("Percentile")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "What does this mean?" }));
    expect(onAsk).toHaveBeenCalledWith("What does my Cardiac health risk result mean?", expect.objectContaining({ type: "bio_ai_risk", risk_code: "cardiac_health", report_id: "b1" }));
  });

  it("tells the member when two reports share the date", async () => {
    getRiskOverview.mockResolvedValue(risks({ same_day_alternatives: true, available_reports: [{ report_id: "b2", report_date: "2026-08-18", source_line: "advanced_bio_ai" }, { report_id: "b1", report_date: "2026-08-18", source_line: "bio_ai" }] }));
    render(<Risk onAsk={vi.fn()} />);
    expect(await screen.findByText(/more than one Bio-AI report on this date/)).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Report" })).toBeTruthy();
  });

  it("has no accessibility violations", async () => {
    getRiskOverview.mockResolvedValue(risks());
    const { container } = render(<Risk onAsk={vi.fn()} />);
    await screen.findByRole("list", { name: /risk areas/i });
    expect(await violations(container)).toEqual([]);
  });
});

describe("Welcome buttons", () => {
  const me = { greeting: "Hi", capabilities: { has_blood_report: true, has_bio_ai_report: true, has_nutrition: false }, starters: { personal: [], general: [] } } as never;

  it("open the overview instead of starting a chat", () => {
    const onSend = vi.fn();
    const onOpenOverview = vi.fn();
    render(<WelcomeExperience me={me} meLoading={false} onSend={onSend} onOpenOverview={onOpenOverview} inputRef={createRef()} />);
    expect(screen.queryByText("My Blood Report")).toBeNull();
    expect(screen.queryByText("My Bio-AI Report")).toBeNull();
    fireEvent.click(screen.getByText("My Health Overview"));
    expect(onOpenOverview.mock.calls).toEqual([["unified"]]);
    expect(onSend).not.toHaveBeenCalled();
  });

  it("still start the chat when no overview handler is given", () => {
    const onSend = vi.fn();
    render(<WelcomeExperience me={me} meLoading={false} onSend={onSend} inputRef={createRef()} />);
    fireEvent.click(screen.getByText("My Health Overview"));
    expect(onSend).toHaveBeenCalledWith(expect.any(String), [], expect.objectContaining({ entry_point: "health_area" }));
  });
});


describe("Header back button", () => {
  it("appears only when there is somewhere to go back to", async () => {
    const { CuraHeader } = await import("../CuraHeader");
    const onBack = vi.fn();
    const { rerender } = render(<CuraHeader onOpenSidebar={() => undefined} />);
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
    rerender(<CuraHeader onOpenSidebar={() => undefined} onBack={onBack} />);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
