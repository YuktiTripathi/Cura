import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CuraProcessingState } from "./CuraProcessingState";

describe("CuraProcessingState", () => {
  afterEach(() => cleanup());

  it("shows the current status sentence", () => {
    render(
      <CuraProcessingState
        event={{ stage: "FETCHING_BLOOD_DATA", message_key: "blood.fetch", family: "blood" }}
      />
    );
    expect(screen.getByText("Reading your latest results…")).toBeTruthy();
    expect(screen.getByRole("status").getAttribute("data-stage")).toBe("blood");
  });

  it("hides when complete", () => {
    const { container } = render(
      <CuraProcessingState event={{ stage: "COMPLETE", message_key: "complete" }} />
    );
    expect(container.textContent).toBe("");
  });
});
