import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessageList } from "../MessageList";
import { MessageActions } from "./MessageActions";

describe("MessageActions", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("copies the answer text", async () => {
    const writeText = vi.fn(async () => undefined);
    vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
    render(<MessageActions text="Your LDL is 138 mg/dL." onFeedback={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(writeText).toHaveBeenCalledWith("Your LDL is 138 mg/dL.");
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

  it("offers regenerate only on the latest answer", () => {
    const onRegenerate = vi.fn();
    render(
      <MessageList
        messages={[
          { role: "user", content: "What is my LDL?" },
          { role: "assistant", content: "Your LDL is 138 mg/dL." },
          { role: "user", content: "And HDL?" },
          { role: "assistant", content: "Your HDL is 41 mg/dL." },
        ]}
        onFollowUp={vi.fn()}
        onAskContext={vi.fn()}
        onFeedback={vi.fn()}
        onRegenerate={onRegenerate}
      />
    );
    const buttons = screen.getAllByRole("button", { name: "Regenerate" });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(onRegenerate).toHaveBeenCalledWith(3);
  });
});
