import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MessageList } from "./MessageList";

describe("plain response mode", () => {
  it("renders only the conversational answer and the model's own follow-ups", () => {
    const answer = "Your glucose control is the main thing to focus on first.";
    const { container } = render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: answer,
            meta: { response_mode: "plain" } as never,
            presentation: {
              mode: "DOMAIN_SUMMARY",
              headline: "Metabolic health",
              summary: "Card summary that must not render",
              findings: [{ label: "HbA1c", value: "9.1", unit: "%", status: "high" }],
              interpretation: null,
              uncertainties: ["What's still unclear"],
              next_steps: [],
              suggestion_chips: ["Generic card chip"],
            },
            followUps: ["How does this relate to my triglycerides?"],
            recommendations: [{ text: "Walk daily", category: "activity" }] as never,
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByText(answer)).toBeTruthy();
    expect(container.textContent).not.toContain("Card summary that must not render");
    expect(container.textContent).not.toContain("What's still unclear");
    expect(container.textContent).toContain("How does this relate to my triglycerides?");
    expect(container.textContent).not.toContain("Generic card chip");
    expect(container.textContent).not.toContain("Using your health context");
    expect(container.textContent).not.toContain("Walk daily");
  });

  it("rich mode still renders the presentation", () => {
    const { container } = render(
      <MessageList
        messages={[
          {
            role: "assistant",
            content: "x",
            presentation: {
              mode: "DOMAIN_SUMMARY",
              headline: "Metabolic health",
              summary: "Card summary visible in rich mode",
              findings: [],
              interpretation: null,
              uncertainties: [],
              next_steps: [],
            },
          },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(container.textContent).toContain("Card summary visible in rich mode");
  });
});
