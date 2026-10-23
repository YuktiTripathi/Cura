import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CompanionPrototype } from "./CompanionPrototype";

vi.mock("../lib/api", () => ({
  sendFeedback: vi.fn(),
}));

afterEach(cleanup);

describe("companion prototype", () => {
  it("renders synthetic measurements and labeled estimates without sending a question", () => {
    render(<CompanionPrototype />);
    expect(screen.getByText(/not a patient record/i)).toBeTruthy();
    expect(screen.getByText("HbA1c")).toBeTruthy();
    expect(screen.getByText("5.4")).toBeTruthy();
    expect(screen.getAllByText("Estimate").length).toBeGreaterThan(0);
    expect(screen.getByText(/does not, by itself, confirm/i)).toBeTruthy();
  });
});