import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FindingRow, HealthOverviewView } from "./HealthOverviewView";
import type { CategoryDetail, UnifiedOverview } from "../../types/unifiedHealth";
import * as api from "../../lib/api";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const counts = { total: 2, within_range: 1, outside_range: 1, no_range: 0, unavailable: 0 };
const card = (over: Record<string, unknown> = {}) => ({
  id: "liver_health", name: "Liver Health", description: "How your body processes food, breaks down medicines and removes waste.", icon: "liver", status: "worth_attention", status_label: "Worth paying attention to", completeness: "complete",
  scenario: "blood_out_risk_ok", summary: "Two liver results are above range, even though your fatty liver risk is healthy.",
  important_findings: [], measured: counts, risks: { assessed: 1, raised: 0 }, count_line: "8 blood tests · 1 risk assessed", detail_line: "2 blood results outside range",
  primary_action: { label: "Explore my liver health", question: "What do my liver results mean for me?" }, ...over,
});
const overview = {
  available: true, state: "ready", opening: "Here is your whole picture.", totals: { blood_within: 42, blood_outside: 11, blood_no_range: 5, blood_unavailable: 5, risks_assessed: 8, risks_raised: 2, metabolic_age: 43 },
  priorities: [{ category_id: "liver_health", title: "Look after your liver", detail: "Two results are high.", icon: "liver", tone: "attention" }],
  categories: [card(), card({ id: "thyroid_health", name: "Thyroid Health", description: "How your thyroid helps control your energy and metabolism.", status: "looking_good", status_label: "Looking good", summary: "All good.", primary_action: { label: "Explore my thyroid health", question: "q" } })],
  provenance: { blood_report_date: "2026-08-21", bio_ai_report_date: "2026-08-25", reports_linked: false, dates_differ: true }, overall_question: "Help me understand my overall health", disclaimer: "Blood tests measure your current health.",
} as unknown as UnifiedOverview;
const detail = {
  ...card(), about: "Your liver cleans your blood.", interpretation: ["A healthy risk does not cancel abnormal results."], insight: "Different tests tell different things.",
  findings: [
    { id: "a", source_type: "measured", name: "Direct Bilirubin", status: "above_range", status_label: "Above range", value: 0.5, unit: "mg/dL", reference_low: 0, reference_high: 0.3, important: true, explain: "A waste substance your liver helps remove.", education: { name: "Bilirubin Direct", what_it_is: "A waste substance your liver has processed.", if_high: "A high result may mean bile is not moving well.", if_low: "A low result is usually not a concern.", next_step: "Discuss it with a doctor." } },
    { id: "risk:nafld", source_type: "predicted_risk", name: "Fatty Liver", status: "risk_healthy", status_label: "Healthy predicted risk", score: 12, classification: "mild", important: false },
    { id: "b", source_type: "measured", name: "Albumin", status: "within_range", status_label: "Within range", value: 4, unit: "g/dL", important: false },
  ],
  actions: [{ title: "Review your results", detail: "Talk to your doctor.", icon: "clipboard" }], follow_ups: ["Why is my bilirubin high?"],
} as unknown as CategoryDetail;

function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);
}

describe("My Health Overview", () => {
  it("shows the combined summary, priorities and one card per category with one action each", async () => {
    vi.spyOn(api, "getHealthOverview").mockResolvedValue(overview);
    wrap(<HealthOverviewView onAsk={vi.fn()} openId={null} onOpenChange={vi.fn()} onOpenReport={vi.fn()} />);
    expect(await screen.findByText("Here is your whole picture.")).toBeTruthy();
    expect(screen.getByText("42")).toBeTruthy();
    expect(screen.getByText("Look after your liver")).toBeTruthy();
    const cards = document.querySelectorAll("button.health-card");
    expect(cards).toHaveLength(2);
    expect(screen.getAllByText("How your body processes food, breaks down medicines and removes waste.")).toHaveLength(1);
    expect(screen.getAllByText("8 blood tests · 1 risk assessed").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Explore my/)).toBeNull();
    cards.forEach((c) => expect(c.textContent).not.toMatch(/outside range|above range|unavailable/));
    expect(screen.queryByText("What does this mean?")).toBeNull();
  });

  it("opens a category and keeps individual reports reachable", async () => {
    vi.spyOn(api, "getHealthOverview").mockResolvedValue(overview);
    const onOpenChange = vi.fn();
    const onOpenReport = vi.fn();
    wrap(<HealthOverviewView onAsk={vi.fn()} openId={null} onOpenChange={onOpenChange} onOpenReport={onOpenReport} />);
    fireEvent.click(await screen.findByRole("button", { name: /Liver Health\. Worth paying attention to/ }));
    expect(onOpenChange).toHaveBeenCalledWith("liver_health");
    fireEvent.click(screen.getByText("View blood report"));
    expect(onOpenReport).toHaveBeenCalledWith("blood");
  });

  it("shows measured and predicted findings in one list, expands the rest, and asks with the area context", async () => {
    vi.spyOn(api, "getHealthCategory").mockResolvedValue(detail);
    const onAsk = vi.fn();
    wrap(<HealthOverviewView onAsk={onAsk} openId="liver_health" onOpenChange={vi.fn()} onOpenReport={vi.fn()} />);
    expect(await screen.findByText("Direct Bilirubin")).toBeTruthy();
    expect(screen.getAllByText("Measured").length).toBeGreaterThan(0);
    expect(screen.queryByText("Albumin")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View complete assessment" }));
    expect(screen.getByText("Albumin")).toBeTruthy();
    expect(screen.getByText("Fatty Liver")).toBeTruthy();
    expect(screen.getByText(/^Predicted/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Why is my bilirubin high\?/ }));
    expect(onAsk).toHaveBeenCalledWith("Why is my bilirubin high?", expect.objectContaining({ entry_point: "health_area" }));
  });

  it("prints verified values and ranges exactly as given", () => {
    render(<ul><FindingRow f={detail.findings![0]} /></ul>);
    expect(screen.getByText(/0\.5 mg\/dL \(0 to 0\.3\)/)).toBeTruthy();
  });

  it("shows the source and date of each result and never implies one moment in time", () => {
    const measured = { ...detail.findings![0], measured_on: "2026-08-21" };
    const predicted = { ...detail.findings![1], measured_on: "2026-08-25" };
    render(<ul><FindingRow f={measured} /><FindingRow f={predicted} /></ul>);
    expect(screen.getByText("Measured, blood report 21 Aug 2026")).toBeTruthy();
    expect(screen.getByText("Predicted, Bio-AI report 25 Aug 2026")).toBeTruthy();
  });

  it("keeps the Bio-AI category prominent and the raw score inspectable without a probability", () => {
    render(<ul><FindingRow f={detail.findings![1]} /></ul>);
    expect(screen.getByText("Healthy predicted risk")).toBeTruthy();
    expect(screen.queryByText("12")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View the score" }));
    expect(screen.getByText("12 out of 100")).toBeTruthy();
    expect(screen.getByText(/0 to 25 Healthy, 26 to 50 Increased Risk, 51 to 75 High Risk, 76 to 100 Very High Risk/)).toBeTruthy();
    expect(screen.getByText(/your report's labels apply/)).toBeTruthy();
    expect(screen.getByText(/not a diagnosis/)).toBeTruthy();
    expect(screen.getByText(/not a percentage chance/)).toBeTruthy();
    expect(screen.queryByText(/12%/)).toBeNull();
  });

  it("says plainly when nothing is available", async () => {
    vi.spyOn(api, "getHealthOverview").mockResolvedValue({ ...overview, available: false, categories: [] } as unknown as UnifiedOverview);
    wrap(<HealthOverviewView onAsk={vi.fn()} openId={null} onOpenChange={vi.fn()} onOpenReport={vi.fn()} />);
    expect(await screen.findByText(/No blood results or Bio-AI report/)).toBeTruthy();
  });
});

describe("About this test", () => {
  const f = detail.findings![0];
  it("opens reviewed text and shows only the direction the report's range points to", () => {
    render(<ul><FindingRow f={f} /></ul>);
    expect(screen.queryByText("A high result may mean bile is not moving well.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "About this test" }));
    expect(screen.getByText("A waste substance your liver has processed.")).toBeTruthy();
    expect(screen.getByText("A high result may mean bile is not moving well.")).toBeTruthy();
    expect(screen.queryByText("A low result is usually not a concern.")).toBeNull();
    expect(screen.getByText("Discuss it with a doctor.")).toBeTruthy();
  });

  it("has no button for a finding without reviewed text", () => {
    render(<ul><FindingRow f={{ ...f, education: null }} /></ul>);
    expect(screen.queryByRole("button", { name: "About this test" })).toBeNull();
  });
});
