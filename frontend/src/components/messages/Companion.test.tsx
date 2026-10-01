import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StructuredResponse } from "../../types/chat";
import { MessageList } from "../MessageList";

const presentation: StructuredResponse = {
  mode: "TREND",
  summary: "LDL changed from 142 to 138 mg/dL.",
  findings: [],
  uncertainties: [],
  next_steps: ["Recheck lipids in 3 months.", "Discuss this with a clinician."],
  proactive_insights: [
    { trigger: "IMPROVED_BUT_STILL_ABNORMAL", title: "Something changed", summary: "LDL cholesterol improved but remains high.", entity: "ldl", suppressed: false },
    { trigger: "X", title: "Hidden", summary: "Should not show.", suppressed: true },
  ],
  clinician_handoff: {
    key_findings: ["LDL cholesterol 138.0 mg/dL (high)"],
    longitudinal_changes: ["LDL cholesterol: improved but still abnormal"],
    relevant_context: [],
    missing_information: [],
    questions_for_clinician: ["Which findings warrant follow-up first?"],
  },
  suggestion_chips: ["What should I discuss with my doctor?", "Why is this pattern still present?"],
};

function renderAnswer() {
  return render(
    <MessageList
      messages={[
        { role: "user", content: "How has my LDL changed?" },
        { role: "assistant", content: "LDL changed from 142 to 138 mg/dL.", presentation, followUps: [{ text: "Why is this pattern still present?", category: "x" }] },
      ]}
      onFollowUp={vi.fn()}
      onAskContext={vi.fn()}
      onFeedback={vi.fn()}
    />
  );
}

describe("in-chat companion pieces", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("shows only unsuppressed insights that came with the answer", () => {
    renderAnswer();
    const note = screen.getByTestId("insight-note");
    expect(note.textContent).toContain("LDL cholesterol improved but remains high.");
    expect(note.textContent).not.toContain("Should not show");
  });

  it("merges suggestion chips into follow-ups without repeats", () => {
    renderAnswer();
    const chips = screen.getAllByRole("button").filter((b) => b.closest(".chips")).map((b) => b.textContent);
    expect(chips).toEqual(["Why is this pattern still present?", "What should I discuss with my doctor?"]);
  });

  it("lets the reader tick next steps and remembers them", () => {
    renderAnswer();
    const box = screen.getByRole("checkbox", { name: "Recheck lipids in 3 months." }) as HTMLInputElement;
    fireEvent.click(box);
    expect(box.checked).toBe(true);
    cleanup();
    renderAnswer();
    expect((screen.getByRole("checkbox", { name: "Recheck lipids in 3 months." }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("checkbox", { name: "Discuss this with a clinician." }) as HTMLInputElement).checked).toBe(false);
  });

  it("opens a printable doctor summary and copies it as text", async () => {
    const writeText = vi.fn(async (_text: string) => undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    renderAnswer();
    fireEvent.click(screen.getByRole("button", { name: "Doctor summary" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("LDL cholesterol 138.0 mg/dL (high)")).toBeTruthy();
    expect(within(dialog).getByText("Which findings warrant follow-up first?")).toBeTruthy();
    expect(within(dialog).queryByText("Relevant context")).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Print" }));
    expect(print).toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Copy as text" }));
    await vi.waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0]).toContain("Key findings:\n- LDL cholesterol 138.0 mg/dL (high)");
  });

  it("offers no doctor summary without key findings", () => {
    render(
      <MessageList
        messages={[{ role: "assistant", content: "Hello", presentation: { ...presentation, clinician_handoff: null } }]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByRole("button", { name: "Doctor summary" })).toBeNull();
  });
});
