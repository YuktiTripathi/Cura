import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WelcomeExperience } from "./WelcomeExperience";
import { selectGreeting } from "../welcome/selectGreeting";

describe("WelcomeExperience", () => {
  it("shows one greeting, the three cards, and at most four questions", () => {
    const greeting = selectGreeting({
      firstName: "Neha",
      hasConversations: false,
      reportsKnown: true,
      hasReports: true,
      hasUnexploredReport: false,
      previousVisitAt: null,
      now: "2026-11-26T00:00:00.000Z",
      recentTopic: null,
    });
    render(
      <WelcomeExperience
        greeting={greeting}
        questions={["Which of my health results should I focus on first?", "What do my results tell me about my health?", "How can I improve my health through everyday habits?", "What does my vitamin D result mean?", "extra"]}
        onSend={() => undefined}
        onOpenOverview={() => undefined}
        inputRef={createRef()}
      />
    );
    expect(screen.getByRole("heading", { name: "Hi Neha 👋" })).toBeTruthy();
    expect(screen.getByText("Let's get to know your health, together.")).toBeTruthy();
    expect(screen.getByText("Understand my health")).toBeTruthy();
    expect(screen.getByText("Eat better for my body")).toBeTruthy();
    expect(screen.getByText("Let's talk about health")).toBeTruthy();
    expect(screen.getByText("Curious about your health?")).toBeTruthy();
    expect(screen.queryByText("extra")).toBeNull();
    expect(screen.queryByText(/blood report, your Bio-AI/)).toBeNull();
  });

  it("uses the no-report card description only when absence is confirmed", () => {
    render(
      <WelcomeExperience
        greeting={null}
        questions={[]}
        reportsConfirmedAbsent
        onSend={() => undefined}
        inputRef={createRef()}
      />
    );
    expect(screen.getByText("Learn how your body works and what your health tests can tell you.")).toBeTruthy();
  });
});
