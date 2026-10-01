import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ProcessingEvent } from "../lib/processingMessages";
import { ProgressStepper, progressSteps } from "./ProgressStepper";

const events: ProcessingEvent[] = [
  { stage: "PLANNING", message_key: "planning", family: "personal" },
  { stage: "FETCHING_BLOOD_DATA", message_key: "blood.fetch", family: "blood" },
  { stage: "REASONING", message_key: "reason", family: "blood" },
  { stage: "COMPOSING_RESPONSE", message_key: "response.compose", family: "blood" },
];

describe("ProgressStepper", () => {
  afterEach(() => cleanup());

  it("skips the request-received echo and moves repeated sentences to the end", () => {
    const live: ProcessingEvent[] = [
      { stage: "PLANNING", message_key: "planning", family: "personal" },
      { stage: "REQUEST_RECEIVED", message_key: "request.received", family: "personal" },
      { stage: "PLANNING", message_key: "planning", family: "personal" },
      { stage: "FETCHING_HISTORY", message_key: "history.fetch", family: "trend" },
      { stage: "REASONING", message_key: "reason", family: "trend" },
      { stage: "CHECKING_SAFETY", message_key: "safety.check", family: "trend" },
      { stage: "COMPOSING_RESPONSE", message_key: "response.compose", family: "trend" },
    ];
    expect(progressSteps(live).map((step) => step.text)).toEqual([
      "Understanding your question…",
      "Looking through your previous results…",
      "Checking your explanation…",
      "Preparing your explanation…",
    ]);
  });

  it("collapses consecutive steps that read the same", () => {
    expect(progressSteps(events).map((step) => step.text)).toEqual([
      "Understanding your question…",
      "Reading your latest results…",
      "Preparing your explanation…",
    ]);
  });

  it("ticks off completed steps and announces only the current one", () => {
    render(<ProgressStepper events={events} />);
    const done = screen.getByRole("list", { name: "Completed steps" });
    expect(done.textContent).toContain("Understanding your question");
    expect(done.textContent).toContain("Reading your latest results");
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Preparing your explanation…");
    expect(status.getAttribute("data-stage")).toBe("composing");
  });

  it("shows just the current status before any step completes", () => {
    render(<ProgressStepper events={events.slice(0, 1)} />);
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("Understanding your question…");
  });

  it("renders nothing once complete", () => {
    const { container } = render(<ProgressStepper events={[{ stage: "COMPLETE", message_key: "complete" }]} />);
    expect(container.textContent).toBe("");
  });
});
