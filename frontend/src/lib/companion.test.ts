import { describe, expect, it } from "vitest";
import { handoffAsText, mergeSuggestions, readHandoff, readInsights } from "./companion";

describe("readInsights", () => {
  it("keeps unsuppressed insights with a summary, capped", () => {
    const raw = [
      { trigger: "PERSISTENTLY_ABNORMAL", title: "One pattern is still present", summary: "Vitamin D remains abnormal.", entity: "vitamin_d" },
      { title: "Hidden", summary: "Iron changed.", entity: "iron", suppressed: true },
      { title: "No summary" },
      "junk",
      { title: "Third", summary: "B12 remains abnormal.", entity: "vitamin_b12" },
      { title: "Fourth", summary: "Beyond the cap." },
    ];
    expect(readInsights(raw)).toEqual([
      { title: "One pattern is still present", summary: "Vitamin D remains abnormal.", entity: "vitamin_d" },
      { title: "Third", summary: "B12 remains abnormal.", entity: "vitamin_b12" },
    ]);
    expect(readInsights(null)).toEqual([]);
  });
});

describe("readHandoff", () => {
  it("needs key findings and drops non-strings", () => {
    expect(readHandoff({ key_findings: [] })).toBeNull();
    expect(readHandoff({ key_findings: ["LDL 138 mg/dL (high)", 4], questions_for_clinician: ["What next?"] })).toEqual({
      key_findings: ["LDL 138 mg/dL (high)"],
      longitudinal_changes: [],
      relevant_context: [],
      missing_information: [],
      questions_for_clinician: ["What next?"],
    });
  });

  it("renders a plain-text summary with only the filled sections", () => {
    const text = handoffAsText(readHandoff({ key_findings: ["LDL 138 mg/dL (high)"], questions_for_clinician: ["What next?"] })!);
    expect(text).toContain("Key findings:\n- LDL 138 mg/dL (high)");
    expect(text).toContain("Questions to ask:\n- What next?");
    expect(text).not.toContain("Changes over time");
    expect(text).toContain("not a diagnosis");
  });
});

describe("mergeSuggestions", () => {
  it("keeps follow-ups first and drops repeats", () => {
    expect(
      mergeSuggestions([{ text: "Why is this pattern still present?" }], ["why is this pattern still present?", "What should I discuss with my doctor?", "A", "B"])
    ).toEqual([{ text: "Why is this pattern still present?" }, "What should I discuss with my doctor?", "A"]);
  });
});
