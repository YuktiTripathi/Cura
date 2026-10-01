import { describe, expect, it } from "vitest";
import type { EvidenceItem } from "../types/chat";
import { groupEvidence, highlightedLines } from "./sources";

const blood = (marker: string, value: number): EvidenceItem => ({
  evidence_id: `ev-${marker}`,
  report_id: "blood-002",
  report_type: "blood_report",
  report_date: "2026-08-18",
  marker,
  source: "ihr",
  value,
  unit: "mg/dL",
  reference_range: "0–100 mg/dL",
});

describe("groupEvidence", () => {
  it("groups values by report and never exposes ids", () => {
    const groups = groupEvidence([blood("LDL", 138), blood("HDL", 41)]);
    expect(groups).toHaveLength(1);
    expect(groups[0].kind).toBe("report");
    expect(groups[0].title).toMatch(/^Blood report · /);
    expect(groups[0].title).not.toContain("blood-002");
    expect(groups[0].items.map((i) => i.label)).toEqual(["LDL", "HDL"]);
  });

  it("groups uploaded evidence by document page with its quoted row", () => {
    const groups = groupEvidence([
      {
        evidence_id: "c1",
        report_id: "doc-1",
        report_type: "user_uploaded",
        report_date: "2026-10-01",
        source: "user_uploaded",
        document_id: "doc-1",
        filename: "labs.pdf",
        page_start: 2,
        marker: "HbA1c",
        value: 5.6,
        unit: "%",
        excerpt: "HbA1c 5.6 % (ref 4.0-5.6)",
      },
    ]);
    expect(groups[0]).toMatchObject({ kind: "document", title: "labs.pdf · page 2", documentId: "doc-1", page: 2 });
    expect(groups[0].items[0].excerpt).toBe("HbA1c 5.6 % (ref 4.0-5.6)");
  });

  it("skips evidence with nothing to show", () => {
    expect(
      groupEvidence([{ evidence_id: "e", report_id: "bio-9", report_type: "bio_ai_report", report_date: "2026-01-01" }])
    ).toEqual([]);
  });
});

describe("highlightedLines", () => {
  it("marks the lines an excerpt quotes", () => {
    const page = "Lab Report\nLDL Cholesterol 142 mg/dL (ref < 100)\nHbA1c 5.6 % (ref 4.0-5.6)";
    expect([...highlightedLines(page, ["HbA1c 5.6 % (ref 4.0-5.6)"])]).toEqual([2]);
    expect([...highlightedLines(page, [""])]).toEqual([]);
  });
});
