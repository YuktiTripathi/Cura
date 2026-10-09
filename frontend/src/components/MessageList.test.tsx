import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessageList } from "./MessageList";
import type { StructuredResponse } from "../types/chat";

afterEach(() => {
  cleanup();
});

describe("MessageList provenance", () => {
  it("shows a single personal source line and hides internal retrieval UI", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your Bio-AI report summarizes several risk scores.",
            evidence: [
              {
                evidence_id: "ev-1",
                report_id: "bio-9",
                report_type: "bio_ai_report",
                report_date: "2026-01-01",
                source: "supershyft",
              },
            ],
            meta: { sources_used: ["supershyft"] },
            provenance: { type: "personal_health", sources: [{ name: "Bio-AI Report", source_type: "personal_record" }] },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId("provenance-line").textContent).toBe("Source: Bio-AI Report");
    expect(screen.queryByText("Ask Cura")).toBeNull();
    expect(screen.queryByText(/supershyft/i)).toBeNull();
    expect(screen.queryByText(/bio-9/)).toBeNull();
  });

  it("links retrieved medical sources", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Hypertension is high blood pressure.",
            provenance: {
              type: "medical_reference",
              sources: [
                { name: "WHO", url: "https://www.who.int/news-room/fact-sheets/detail/hypertension", source_type: "guideline" },
                { name: "NICE", url: "https://www.nice.org.uk/guidance/ng136", source_type: "guideline" },
              ],
            },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId("provenance-line").textContent).toBe("Sources: WHO · NICE");
    expect(screen.getByRole("link", { name: "WHO" }).getAttribute("href")).toContain("who.int");
  });

    it("renders findings without internal source ids", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Thyroid health",
            presentation: {
              mode: "DOMAIN_SUMMARY",
              headline: "Thyroid health",
              summary: "Thyroid health using the measurements available in your latest records.",
              findings: [
                {
                  label: "TSH",
                  value: "2.1",
                  unit: "µIU/mL",
                  status: "in_range",
                  source_type: "blood_report",
                  source_date: "2026-08-18",
                  source_id: "blood-002",
                  source_label: "Latest blood report · 18 Aug 2026",
                },
              ],
              interpretation: null,
              uncertainties: [],
              next_steps: [],
            },
            provenance: {
              type: "personal_health",
              sources: [{ name: "Latest blood report · 18 Aug 2026", source_type: "personal_record", source_id: "blood-002" }],
            },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByText("TSH")).toBeTruthy();
    expect(screen.getByText(/2\.1/)).toBeTruthy();
    expect(screen.getByTestId("provenance-line").textContent).toContain("Latest blood report");
    expect(screen.queryByText("blood-002")).toBeNull();
  });

  it("hides the source line when no blood-report fact was retrieved", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "No matching blood result is available for LDL.",
            evidence: [],
            provenance: { type: "none", sources: [] },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByTestId("provenance-line")).toBeNull();
    expect(screen.queryByText(/Blood Report/)).toBeNull();
  });
});

describe("MessageList narrative summary", () => {
  const presentation: StructuredResponse = {
    mode: "HEALTH_OVERVIEW",
    summary: "Most of your major health areas look reassuring, but the main pattern that stands out is red cell and iron findings.",
    overall_summary:
      "Most of your major health areas look reassuring, but the main pattern that stands out is red cell and iron findings.",
    findings: [],
    uncertainties: [],
    next_steps: ["The highest-yield next step is to review this red cell and iron findings pattern with a clinician."],
    summary_style: "NARRATIVE_HEALTH_SUMMARY",
    themes: [
      {
        title: "Red cell and iron findings",
        priority: "high",
        status: "needs_attention",
        supporting_fact_ids: ["hemoglobin", "iron"],
        interpretation: "Haemoglobin is 10.5 g/dL (low); Iron is 35 µg/dL (low). These sit together as one pattern rather than separate unrelated alerts. This can be worth discussing with a clinician; it is not a diagnosis.",
        missing_information: ["Ferritin is not available in this report, which would help interpret this pattern."],
        next_step: "The highest-yield next step is to review this red cell and iron findings pattern with a clinician.",
        related_findings: [
          { label: "Haemoglobin", value: "10.5", unit: "g/dL", status: "low", canonical_key: "hemoglobin" },
          { label: "Iron", value: "35", unit: "µg/dL", status: "low", canonical_key: "iron" },
        ],
      },
      {
        title: "Areas that look reassuring",
        priority: "low",
        status: "reassuring",
        supporting_fact_ids: [],
        interpretation: "Lipids currently look reassuring on the available measurements.",
        missing_information: [],
        related_findings: [],
      },
    ],
    raw_findings: [
      { label: "Haemoglobin", value: "10.5", unit: "g/dL", status: "low", canonical_key: "hemoglobin" },
      { label: "MCV", value: "72", unit: "fL", status: "low", canonical_key: "mcv" },
      { label: "Iron", value: "35", unit: "µg/dL", status: "low", canonical_key: "iron" },
      { label: "LDL", value: "92", unit: "mg/dL", status: "in_range", canonical_key: "ldl" },
      { label: "Urea", value: "28", unit: "mg/dL", status: "in_range", canonical_key: "urea" },
    ],
  };

  it("renders theme cards and keeps the raw table behind View all results", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Most of your major health areas look reassuring, but the main pattern that stands out is red cell and iron findings.",
            presentation,
            provenance: { type: "personal_health", sources: [{ name: "Latest blood report · 24 Aug 2026", source_type: "personal_record" }] },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getAllByTestId("health-theme")).toHaveLength(2);
    expect(screen.getByText("Red cell and iron findings")).toBeTruthy();
    expect(screen.getByText("Areas that look reassuring")).toBeTruthy();
    expect(screen.queryByText("Urea")).toBeNull();
    expect(screen.queryByText("Measurement")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View all results" }));
    expect(screen.getByText("Urea")).toBeTruthy();
    expect(screen.getByText("Measurement")).toBeTruthy();
  });

  it("progressively discloses related values on a theme", () => {
    render(
      <MessageList
        messages={[{ role: "assistant", content: "summary", presentation }]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByText("Measurement")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Related values" }));
    expect(screen.getByText("Measurement")).toBeTruthy();
    expect(screen.getByText("Haemoglobin")).toBeTruthy();
  });

  it("renders a SuperShyft testing option separately from medical text", () => {
    const option = {
      type: "package_recommendation" as const,
      relevance: "HIGH_RELEVANCE" as const,
      headline: "A test that may help clarify this",
      package: { id: "31", name: "Iron Studies with Ferritin", kind: "test_group" as const },
      reason: "Your haemoglobin, MCV, MCH and serum iron are low, while ferritin is not available.",
      helps_answer: "Whether your iron stores are depleted.",
      relevant_tests: ["Ferritin", "Iron", "TIBC", "Transferrin"],
      already_recent: ["Iron"],
      primary_action: {
        type: "OPEN_PACKAGE" as const,
        label: "View Iron Studies with Ferritin",
        package_id: "31",
        catalog_kind: "test_group" as const,
      },
      secondary_action: {
        type: "COMPARE_WITH_EXISTING_RESULTS" as const,
        label: "Check what I already have",
      },
      comparison: {
        included: ["Ferritin", "Iron", "TIBC", "Transferrin"],
        already_have: [{ key: "iron", label: "Iron", measured_on: "24 Aug 2026" }],
        adds_information: ["Ferritin"],
        timing_note: "Some included tests already appear in your reports; others would add new information.",
      },
      catalog_id: "31",
      kind: "test_group" as const,
      display_name: "Iron Studies with Ferritin",
      included_matched_tests: ["ferritin", "iron", "tibc"],
      included_matched_labels: ["Ferritin", "Iron", "TIBC"],
    };
    const seen: unknown[] = [];
    const onOpen = (event: Event) => seen.push((event as CustomEvent).detail);
    window.addEventListener("cura:open_package", onOpen);
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Ferritin would help interpret the iron pattern.",
            testingOption: option,
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByTestId("testing-option")).toBeNull();
    expect(screen.queryByText("A test that may help clarify this")).toBeNull();
    expect(screen.queryByText("View Iron Studies with Ferritin")).toBeNull();
    window.removeEventListener("cura:open_package", onOpen);
  });

  it("shows a so-far summary and related results disclosure", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your B12 is 154 pg/mL.",
            presentation: {
              mode: "INTERPRETATION",
              headline: "Vitamin B12",
              summary: "Your B12 is 154 pg/mL.",
              findings: [],
              interpretation: "This sits below the reported range.",
              uncertainties: [],
              next_steps: [],
              topic_summary: { text: "So far: we have been looking at B12." },
              related_findings: [{ label: "MCV", value: "72", unit: "fL", status: "low" }],
            },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId("topic-summary").textContent).toContain("So far");
    fireEvent.click(screen.getByRole("button", { name: "View related results" }));
    expect(screen.getByText("MCV")).toBeTruthy();
  });
});

describe("MessageList pending answer", () => {
  it("does not render an empty bubble for the assistant placeholder", () => {
    render(
      <MessageList
        messages={[
          { role: "user", content: "What is my LDL?" },
          { role: "assistant", content: "" },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(document.querySelectorAll("article.user").length).toBe(1);
    expect(document.querySelectorAll("article.assistant").length).toBe(0);
  });
});

describe("MessageList answer preview", () => {
  it("shows previewed values while the explanation is still being written", () => {
    render(
      <MessageList
        messages={[
          { role: "user", content: "What is my LDL?" },
          {
            role: "assistant",
            content: "",
            preview: [
              { label: "LDL cholesterol", value: "138.0", unit: "mg/dL", numeric_value: 138, reference_low: 0, reference_high: 100 },
            ],
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId("answer-preview")).toBeTruthy();
    expect(screen.getByText("LDL cholesterol")).toBeTruthy();
    expect(screen.getByText("Above range")).toBeTruthy();
    // No feedback or follow-ups on an unfinished answer.
    expect(screen.queryByText("Was this helpful?")).toBeNull();
  });
});


describe("MessageList premium semantic streaming", () => {
  it("renders validated experience blocks as semantic sections instead of a flat text blob", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your vitamin D is 24 ng/mL.\n\nThis is below your lab range.",
            experienceBlocks: [
              { sequence: 1, kind: "direct_answer", text: "Your vitamin D is 24 ng/mL." },
              {
                sequence: 2,
                kind: "key_facts",
                findings: [
                  {
                    label: "Vitamin D",
                    value: "24",
                    unit: "ng/mL",
                    canonical_key: "vitamin_d",
                    reference_low: 30,
                    reference_high: 100,
                  },
                ],
              },
              { sequence: 3, kind: "interpretation", text: "This is below your lab's reported range." },
              { sequence: 4, kind: "personal_relevance", text: "This may be relevant to the bone-health goal we were discussing." },
            ],
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );

    expect(screen.getByTestId("streaming-experience")).toBeTruthy();
    expect(screen.getByText("From your records")).toBeTruthy();
    expect(screen.getByText("What it means")).toBeTruthy();
    expect(screen.getByText("Why this matters for you")).toBeTruthy();
    expect(screen.getByText("CURA is completing the picture")).toBeTruthy();
    expect(screen.getByLabelText(/CURA · Building your answer/)).toBeTruthy();
  });

  it("shows follow-up suggestions as a continuation area", () => {
    render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "Your vitamin D is below the reported range.",
            followUps: ["What can affect vitamin D?"],
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByText("Continue with CURA")).toBeTruthy();
    expect(screen.getByRole("button", { name: /What can affect vitamin D/ })).toBeTruthy();
  });
});
