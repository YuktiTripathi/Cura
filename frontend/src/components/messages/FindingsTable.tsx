import { useState } from "react";
import type { PresentedFinding } from "../../types/chat";
import { numericValue } from "../../lib/range";
import { RangeBar } from "./RangeBar";
import { t } from "../../i18n";

const MISSING_STATUS = new Set(["missing", "not_available", "unavailable", "not_present"]);

/** Rows without a measured value are omitted from result tables and cards. */
export function availableFindings(findings: PresentedFinding[]): PresentedFinding[] {
  return findings.filter((item) => {
    const status = (item.status || "").toLowerCase().replace(/[\s-]+/g, "_");
    const measured =
      item.numeric_value != null && Number.isFinite(item.numeric_value)
        ? true
        : (() => {
            const value = item.value == null ? "" : String(item.value).trim();
            if (!value || /^[-—–−]+$/.test(value)) return false;
            if (/^(n\/a|na|missing|null|none)$/i.test(value)) return false;
            return /\d/.test(value);
          })();
    if (!measured) return false;
    if (MISSING_STATUS.has(status)) return false;
    return true;
  });
}

export function RelatedResults({ findings }: { findings: PresentedFinding[] }) {
  const [open, setOpen] = useState(false);
  if (!findings.length) return null;
  return (
    <div className="related-results">
      <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
        {open ? "Hide related results" : "View related results"}
      </button>
      {open ? <FindingsTable findings={findings} /> : null}
    </div>
  );
}

export function RawResultsDisclosure({ findings }: { findings: PresentedFinding[] }) {
  const [open, setOpen] = useState(false);
  if (!findings.length) return null;
  return (
    <div className="raw-results">
      <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
        {open ? "Hide full results" : "View all results"}
      </button>
      {open ? <FindingsTable findings={findings} /> : null}
    </div>
  );
}

export function FindingsTable({ findings }: { findings: PresentedFinding[] }) {
  findings = availableFindings(findings);
  if (!findings.length) return null;
  const riskScores = findings.every((item) => item.source_type === "bio_ai_report");
  const showRange = !riskScores && findings.some((item) => item.reference_low != null || item.reference_high != null);
  return (
    <div className="findings-table-wrap">
      <table className="findings-table">
        <thead>
          <tr>
            <th>{t("ui.FindingsTable.measurement", "Measurement")}</th>
            <th>{riskScores ? "Risk Score" : "Value"}</th>
            {riskScores ? <th>{t("ui.FindingsTable.status", "Status")}</th> : null}
            {showRange ? <th>{t("ui.FindingsTable.range", "Range")}</th> : null}
          </tr>
        </thead>
        <tbody>
          {findings.map((item, index) => (
            <tr key={`${item.label}-${index}`}>
              <td>{item.label}</td>
              <td>
                {item.value ?? "—"}
                {item.unit ? ` ${item.unit}` : ""}
              </td>
              {riskScores ? <td>{riskStatusLabel(item.status)}</td> : null}
              {showRange ? (
                <td>
                  <RangeBar
                    label={item.label}
                    value={numericValue(item)}
                    unit={item.unit}
                    low={item.reference_low}
                    high={item.reference_high}
                  />
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function riskStatusLabel(status: string | null | undefined): string {
  const text = (status || "").trim();
  if (!text || text.toLowerCase() === "unknown") return "—";
  return text.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
