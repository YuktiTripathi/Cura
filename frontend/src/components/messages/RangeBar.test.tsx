import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RangeBar } from "./RangeBar";
import { ValueCard } from "./ValueCard";

describe("RangeBar", () => {
  afterEach(() => cleanup());

  it("spells out the status and the reference bounds", () => {
    render(<RangeBar label="LDL" value={142} unit="mg/dL" low={0} high={100} />);
    expect(screen.getByText("Above range")).toBeTruthy();
    expect(screen.getByText("Ref 0–100 mg/dL")).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toBe(
      "LDL 142 mg/dL: above range (reference 0–100 mg/dL)."
    );
  });

  it("supports one-sided ranges", () => {
    render(<RangeBar label="hs-CRP" value={0.4} unit="mg/L" high={1} />);
    expect(screen.getByText("Within range")).toBeTruthy();
    expect(screen.getByText("Ref below 1 mg/L")).toBeTruthy();
  });

  it("renders nothing without a usable range", () => {
    const { container } = render(<RangeBar label="LDL" value={142} unit="mg/dL" />);
    expect(container.textContent).toBe("");
  });
});

describe("ValueCard", () => {
  afterEach(() => cleanup());

  it("shows a range bar when the finding carries bounds", () => {
    render(
      <ValueCard
        finding={{ label: "Vitamin D", value: "18.0", unit: "ng/mL", status: "low", numeric_value: 18, reference_low: 30, reference_high: 100 }}
      />
    );
    expect(screen.getByText("Vitamin D")).toBeTruthy();
    expect(screen.getByText("Below range")).toBeTruthy();
  });

  it("falls back to the status text without bounds", () => {
    render(<ValueCard finding={{ label: "TSH", value: "2.1", unit: "µIU/mL", status: "in_range" }} />);
    expect(screen.getByText("in range")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
