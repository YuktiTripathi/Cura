import { describe, expect, it } from "vitest";
import type { PresentedFinding } from "../../types/chat";
import { uniqueRelated } from "./PresentedAnswer";
import { readInsights, mergeSuggestions } from "../../lib/companion";

const f = (key: string): PresentedFinding => ({ label: key.toUpperCase(), value: "1", unit: "mg/dL", canonical_key: key }) as PresentedFinding;

describe("answer presentation policy", () => {
  it("does not repeat a value already shown on the main card", () => {
    const out = uniqueRelated([f("hdl"), f("ldl"), f("ldl")], [f("hdl")]);
    expect(out.map((x) => x.canonical_key)).toEqual(["ldl"]);
  });

  it("keeps follow-up chips to three", () => {
    expect(mergeSuggestions(["a?"], ["b", "c", "d", "e"]).length).toBeLessThanOrEqual(3);
  });

  it("shows at most one proactive insight when asked", () => {
    const raw = [{ text: "one" }, { text: "two" }];
    expect(readInsights(raw, 1).length).toBeLessThanOrEqual(1);
  });
});
