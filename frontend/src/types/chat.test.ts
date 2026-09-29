import { describe, expect, it } from "vitest";
import { assistantTextSegments, displayAssistantText, extractStructuredAnswer } from "./chat";

const payload = {
  answer: "HDL is often called good cholesterol; LDL is often called bad cholesterol.",
  claims: [],
  recommendation_candidates: [],
  follow_up_questions: ["What is a healthy HDL level?"],
  safety_flags: [],
  escalation: null,
};

describe("displayAssistantText", () => {
  it("renders answer instead of raw JSON", () => {
    const raw = JSON.stringify(payload);
    expect(displayAssistantText(raw)).toBe(payload.answer);
    expect(displayAssistantText(raw)).not.toContain("follow_up_questions");
  });

  it("passes through plain text", () => {
    expect(displayAssistantText("HDL carries cholesterol.")).toBe("HDL carries cholesterol.");
  });

  it("keeps raw JSON only in debug mode", () => {
    const raw = JSON.stringify(payload);
    expect(displayAssistantText(raw, true)).toBe(raw);
  });

  it("marks Bio-AI category names as bold segments", () => {
    expect(assistantTextSegments("• **Hypertension:** 16 (Healthy)")).toEqual([
      { text: "• ", bold: false },
      { text: "Hypertension:", bold: true },
      { text: " 16 (Healthy)", bold: false },
    ]);
  });

  it("extracts nested answer strings", () => {
    expect(extractStructuredAnswer(JSON.stringify({ answer: JSON.stringify(payload) }))).toBe(payload.answer);
  });
});
