import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { PresentedFinding } from "../../types/chat";
import { FindingsTable, availableFindings } from "./FindingsTable";

const measured: PresentedFinding = {
  label: "Bilirubin",
  value: "0.27",
  unit: "mg/dl",
  status: "low",
  numeric_value: 0.27,
  reference_low: 0.3,
  reference_high: 1.2,
};

const inRange: PresentedFinding = {
  label: "Albumin",
  value: "3.63",
  unit: "g/dl",
  status: "in_range",
  numeric_value: 3.63,
  reference_low: 3.5,
  reference_high: 5.2,
};

const missing: PresentedFinding[] = [
  { label: "alkaline phosphatase", value: "—", unit: "U/L", status: "missing" },
  { label: "absolute neutrophil count", value: null, unit: "10^3/uL", status: "missing" },
  { label: "esr automated", value: "—", status: "missing" },
];

describe("FindingsTable", () => {
  afterEach(() => cleanup());

  it("shows only measured biomarkers and omits the status column", () => {
    expect(availableFindings([measured, ...missing, inRange]).map((item) => item.label)).toEqual([
      "Bilirubin",
      "Albumin",
    ]);
    render(<FindingsTable findings={[measured, ...missing, inRange]} />);
    expect(screen.getByText("Bilirubin")).toBeTruthy();
    expect(screen.getByText("Albumin")).toBeTruthy();
    expect(screen.queryByText("alkaline phosphatase")).toBeNull();
    expect(screen.queryByText("absolute neutrophil count")).toBeNull();
    expect(screen.queryByText("esr automated")).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Status" })).toBeNull();
    expect(screen.getByText("Within range")).toBeTruthy();
    expect(screen.getByText("Below range")).toBeTruthy();
  });

  it("shows risk score and status for a Bio-AI report", () => {
    render(
      <FindingsTable
        findings={[
          { label: "Hypertension", value: "16", status: "Healthy", source_type: "bio_ai_report", numeric_value: 16 },
          { label: "Dyslipidemia", value: "3", status: "healthy", source_type: "bio_ai_report", numeric_value: 3 },
        ]}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Risk Score" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeTruthy();
    expect(screen.queryByRole("columnheader", { name: "Value" })).toBeNull();
    expect(screen.getAllByText("Healthy")).toHaveLength(2);
  });
});
