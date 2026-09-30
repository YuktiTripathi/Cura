import { describe, expect, it } from "vitest";
import { processingCopy, uiStageFor, type ProcessingEvent } from "../lib/processingMessages";

describe("processing messages", () => {
  it("maps blood fetch to a friendly sentence", () => {
    const event: ProcessingEvent = {
      stage: "FETCHING_BLOOD_DATA",
      message_key: "blood.fetch",
      family: "blood",
    };
    expect(processingCopy(event)).toBe("Reading your latest results…");
    expect(uiStageFor(event.stage)).toBe("blood");
  });

  it("does not restart follow-ups with understanding your question", () => {
    const event: ProcessingEvent = {
      stage: "PLANNING",
      message_key: "followup.context",
      family: "followup",
      follow_up: true,
    };
    expect(processingCopy(event)).toBe("Keeping the previous context in mind…");
    expect(processingCopy(event)).not.toMatch(/Understanding your question/);
  });

  it("keeps document copy free of implementation details", () => {
    const event: ProcessingEvent = {
      stage: "READING_DOCUMENT",
      message_key: "document.read",
      family: "document",
    };
    expect(processingCopy(event).toLowerCase()).not.toContain("pageindex");
  });
});
