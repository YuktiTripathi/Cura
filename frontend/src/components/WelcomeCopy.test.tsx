import { describe, expect, it } from "vitest";
import { homeQuestions } from "../welcome/homeQuestions";
import type { Finding } from "../types/unifiedHealth";

describe("home questions", () => {
  it("uses general questions when reports are not confirmed", () => {
    expect(homeQuestions(false, false, [])).toContain("How does sleep affect my health?");
    expect(homeQuestions(false, false, [])).toHaveLength(4);
  });

  it("adds one question from a real finding and stays within four", () => {
    const finding = { id: "vitamin_d", name: "Vitamin D" } as Finding;
    const questions = homeQuestions(true, true, [finding]);
    expect(questions).toContain("What does my vitamin D result mean?");
    expect(questions).toHaveLength(4);
  });
});
