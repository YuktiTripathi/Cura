import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";
import { friendlySendError } from "../hooks/useCuraChat";

vi.mock("../lib/api", () => ({
  transcribeVoice: vi.fn(),
  getDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

afterEach(cleanup);

describe("draft preservation", () => {
  it("puts a failed message back in the box", () => {
    const { rerender } = render(<Composer disabled={false} onSend={vi.fn()} />);
    rerender(<Composer disabled={false} onSend={vi.fn()} restoreText="How is my vitamin D?" />);
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("How is my vitamin D?");
  });
});

describe("friendly errors", () => {
  it("never shows raw error text", () => {
    const msg = friendlySendError(new Error("TypeError: Failed to fetch at line 42"));
    expect(msg).not.toMatch(/TypeError|fetch|line 42/);
    expect(msg).toMatch(/try again/i);
  });
});
