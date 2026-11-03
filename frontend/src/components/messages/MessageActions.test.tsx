import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessageList } from "../MessageList";
import { MessageActions } from "./MessageActions";

describe("MessageActions", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("does not offer copy, regenerate, or a doctor summary", () => {
    render(<MessageActions text="Your LDL is 138 mg/dL." onFeedback={vi.fn()} onRegenerate={vi.fn()} onDoctorSummary={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Doctor summary" })).toBeNull();
  });

  it("sends 👍 straight away and asks an optional reason for 👎", () => {
    const onFeedback = vi.fn();
    const { unmount } = render(<MessageActions text="a" onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: "Helpful" }));
    expect(onFeedback).toHaveBeenCalledWith("up");
    expect(screen.getByText("Thanks for the feedback")).toBeTruthy();
    unmount();

    render(<MessageActions text="a" onFeedback={onFeedback} />);
    fireEvent.click(screen.getByRole("button", { name: "Not helpful" }));
    expect(onFeedback).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("What was wrong or missing?"), { target: { value: "Missing my HDL" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onFeedback).toHaveBeenLastCalledWith("down", "Missing my HDL");
  });

  it("does not show regenerate under answers", () => {
    render(
      <MessageList
        messages={[
          { role: "user", content: "What is my LDL?" },
          { role: "assistant", content: "Your LDL is 138 mg/dL." },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  });
});
