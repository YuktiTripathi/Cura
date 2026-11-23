import { describe, expect, it } from "vitest";
import { introLine } from "./WelcomeExperience";

describe("welcome intro", () => {
  it("mentions only what exists", () => {
    expect(introLine({ has_blood_report: true })).toContain("your blood report");
    expect(introLine({ has_blood_report: true })).not.toMatch(/Bio-AI|nutrition/);
  });
  it("falls back to general help with no reports", () => {
    expect(introLine({})).not.toMatch(/report/);
  });
  it("joins several items naturally", () => {
    expect(introLine({ has_blood_report: true, has_bio_ai_report: true, has_nutrition: true })).toContain("your blood report, your Bio-AI report and your nutrition");
  });
});
