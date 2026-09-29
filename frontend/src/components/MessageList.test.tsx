import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessageList } from "./MessageList";

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
});
