import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "../../../lib/api";
import { __setLocaleForTests } from "../../../i18n";
import type { HealthStory } from "../../../types/unifiedHealth";
import { HealthOverviewView } from "../HealthOverviewView";
import { HealthStoryView } from "./HealthStoryView";

afterEach(() => { cleanup(); vi.restoreAllMocks(); __setLocaleForTests("en"); });

const hdl = { id: "r1", source_type: "measured", name: "HDL Cholesterol", status: "below_range", status_label: "Below range", value: 37, unit: "mg/dL", reference_low: 40, reference_high: 60, measured_on: "2026-08-21", important: true, data_quality: "verified" };
const story = {
  category_id: "heart_circulation", category_name: "Heart & Circulation", icon: "heart", status: "needs_closer_attention", status_label: "Needs closer attention", headline: "Let's understand your heart health",
  understand_body: { available: true, title: "Let's get to know your heart", sections: [{ heading: "What your heart does", text: "Your heart is a muscle that pumps blood." }, { heading: "Where cholesterol fits in", text: "Cholesterol travels in particles." }], report_scope: "A blood report does not show blood pressure.", source: "medical_knowledge_base", review_status: "unreviewed", evidence_ids: [] },
  your_assessment: { available: true, lead: "", note: "", risks: [{ finding_id: "risk:cardiac_health", name: "Heart Health", score: 72, classification: "High Risk", assessed_on: "2026-08-25", model_name: null, model_version: null, what_it_means: "This is a predicted risk from your Bio-AI assessment.", what_it_does_not_mean: ["It is not a diagnosis."], limitations: ["It is an estimate."], contributing_factors: null, contributing_note: "Your assessment does not list contributing factors, so CURA does not guess them from your blood results.", evidence_ids: [] }] },
  personal_factors: { lead: "", measured: [{ finding: hdl, marker_id: "hdl_cholesterol_direct", why_relevant: "It is one part of your cholesterol picture.", source: "Laboratory report", evidence_ids: [] }], within_range_count: 2,
    lifestyle: [{ key: "activity", label: "Physical activity", state: "reported", value: "Low", level: "low", recorded_at: "2026-08-20", source: "Your questionnaire", evidence_ids: [] }, { key: "smoking", label: "Smoking", state: "not_reported", evidence_ids: [] }],
    relationships: [{ relationship_id: "life_activity_low_hdl_low:heart_circulation", text: "Your HDL cholesterol is below your laboratory's reference range, and you have reported low physical activity. This does not mean that low activity caused your HDL result.", relationship_type: "potentially_related", finding_ids: ["r1"], lifestyle_keys: ["activity"], rule_id: "life_activity_low_hdl_low", causal_claim: false, evidence_status: "rule_based_unreviewed", evidence_ids: [] }],
    missing: ["Smoking is not on record, so nothing here assumes it either way."] },
  biomarker_education: [{ marker_id: "hdl_cholesterol_direct", name: "HDL cholesterol", finding_id: "r1", measures: "The cholesterol carried by HDL particles.", body_function: "HDL helps carry extra cholesterol back to the liver.", why_it_matters: "One part of your cholesterol picture.", causes_when_low: ["Little physical activity"], causes_when_high: [], effects_when_low: "A lower HDL can be associated with a higher chance of heart problems.", effects_when_high: "Higher is not always better.", influences: ["Smoking"], practical_steps: ["Regular movement"], related_markers: [], age_sex_note: "", unit_note: "", your_result: { value: 37, unit: "mg/dL", reference_low: 40, reference_high: 60, status: "below_range", status_label: "Below range", measured_on: "2026-08-21", source: "Laboratory report" }, needs_attention: true, detail_level: "full", evidence_ids: [], review_status: "unreviewed" }],
  improvement_plan: { lead: "", actions: [{ action_id: "heart_move_gradually", title: "Add gentle movement to your day", what: "Build up daily movement slowly.", why: "You have reported low physical activity.", supported_by: [], safety_note: "If you have chest pain, check with your doctor first.", evidence_status: "rule_based_unreviewed" }], note: "They are not promised to change a Bio-AI score." },
  next_steps: { monitoring: ["Results to keep an eye on: HDL Cholesterol."], follow_ups: [], suggested_questions: ["Why is my HDL Cholesterol low?"], related_categories: [{ id: "blood_sugar_metabolism", name: "Blood Sugar & Metabolism", status_label: "Looking good", icon: "drops" }] },
  limitations: ["Not yet reviewed by clinicians."],
  metadata: { knowledge_version: "bk-1", rules_version: "rel-1", actions_version: "act-1", prompt_version: "story-1", evidence_version: "x", generated_at: "2026-11-23T00:00:00Z", generation: "rules", generation_model: null, data_state: "complete" },
  disclaimer: "This is general education.",
} as unknown as HealthStory;

describe("guided health story", () => {
  it("renders every chapter with measured, predicted and reported evidence kept apart", () => {
    render(<HealthStoryView story={story} onAsk={vi.fn()} />);
    for (const t of ["Let's get to know your heart", "What your Bio-AI assessment says", "What could be influencing your health?", "Get to know your biomarkers", "Ways to support your health", "Your next steps"]) expect(screen.getByRole("heading", { name: t })).toBeTruthy();
    expect(screen.getByText("Measured in your blood report")).toBeTruthy();
    expect(screen.getByText("Reported by you")).toBeTruthy();
    expect(screen.getByText(/Score 72 out of 100/)).toBeTruthy();
    expect(screen.getByText("Not reported")).toBeTruthy();
    expect(screen.getByText(/Not independently verified/)).toBeTruthy();
    expect(screen.getByText(/does not mean that low activity caused/)).toBeTruthy();
  });

  it("opens a biomarker card to show the result against its range, then education, without a new request", () => {
    const spy = vi.spyOn(api, "getHealthStory");
    render(<HealthStoryView story={story} onAsk={vi.fn()} />);
    expect(screen.queryByText("HDL helps carry extra cholesterol back to the liver.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /HDL cholesterol/ }));
    expect(screen.getByText("HDL helps carry extra cholesterol back to the liver.")).toBeTruthy();
    expect(screen.getByText(/laboratory's own reference range/)).toBeTruthy();
    expect(screen.getByText("General education, not yet reviewed by clinicians.")).toBeTruthy();
    expect(spy).not.toHaveBeenCalled();
  });

  it("opens the risk explanation and says the model is not stated", () => {
    render(<HealthStoryView story={story} onAsk={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "What this does and does not mean" }));
    expect(screen.getByText("It is not a diagnosis.")).toBeTruthy();
    expect(screen.getByText(/Model name and version: not stated/)).toBeTruthy();
    expect(screen.getByText(/does not guess them from your blood results|CURA does not guess/)).toBeTruthy();
  });

  it("reveals the source and report date of a finding", () => {
    render(<HealthStoryView story={story} onAsk={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Show source" }));
    expect(screen.getByText(/Laboratory report, 21 Aug 2026/)).toBeTruthy();
  });

  it("starts a conversation with the area context from a suggested question and from the input", () => {
    const onAsk = vi.fn();
    render(<HealthStoryView story={story} onAsk={onAsk} />);
    fireEvent.click(screen.getByRole("button", { name: /Why is my HDL Cholesterol low/ }));
    expect(onAsk).toHaveBeenCalledWith("Why is my HDL Cholesterol low?", expect.objectContaining({ entry_point: "health_area" }));
    fireEvent.change(screen.getByLabelText("Ask CURA about this area"), { target: { value: "Is this serious?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(onAsk).toHaveBeenLastCalledWith("Is this serious?", expect.objectContaining({ entry_point: "health_area" }));
  });

  it("navigates to a related category", () => {
    const open = vi.fn();
    render(<HealthStoryView story={story} onAsk={vi.fn()} onOpenCategory={open} />);
    fireEvent.click(screen.getByRole("button", { name: /Blood Sugar & Metabolism/ }));
    expect(open).toHaveBeenCalledWith("blood_sugar_metabolism");
  });

  it("handles partial data: no assessment, no blood results, no actions", () => {
    const partial = { ...story, your_assessment: { available: false, lead: "", note: "No Bio-AI risk was assessed for this area.", risks: [] }, personal_factors: { ...story.personal_factors, measured: [], relationships: [] }, biomarker_education: [], improvement_plan: { lead: "", actions: [], note: "n" }, metadata: { ...story.metadata, data_state: "partial" } } as unknown as HealthStory;
    render(<HealthStoryView story={partial} onAsk={vi.fn()} />);
    expect(screen.getByText(/Some information for this area is missing/)).toBeTruthy();
    expect(screen.getAllByText("No Bio-AI risk was assessed for this area.").length).toBeGreaterThan(0);
    expect(screen.getByText("No blood results for this area are available.")).toBeTruthy();
    expect(screen.getByText(/no specific steps to suggest/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Get to know your biomarkers" })).toBeNull();
  });

  it("falls back to English text in Hindi mode instead of failing", () => {
    __setLocaleForTests("hi");
    render(<HealthStoryView story={story} onAsk={vi.fn()} />);
    expect(screen.getByText(/Score 72/)).toBeTruthy();
  });

  it("shows a loading state and falls back to the short summary when the story is unavailable", async () => {
    vi.spyOn(api, "getHealthStory").mockRejectedValue(new Error("no"));
    vi.spyOn(api, "getHealthCategory").mockResolvedValue({ id: "heart_circulation", name: "Heart & Circulation", icon: "heart", status: "looking_good", status_label: "Looking good", summary: "Summary text.", findings: [], actions: [], follow_ups: [], interpretation: [] } as never);
    render(<QueryClientProvider client={new QueryClient()}><HealthOverviewView onAsk={vi.fn()} openId="heart_circulation" onOpenChange={vi.fn()} onOpenReport={vi.fn()} /></QueryClientProvider>);
    expect(screen.getByText(/Opening this part of your health/)).toBeTruthy();
    expect(await screen.findByText("Summary text.")).toBeTruthy();
  });
});
