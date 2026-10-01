import { useState } from "react";
import type { PresentedFinding } from "../../types/chat";
import { numericValue } from "../../lib/range";
import { RangeBar } from "./RangeBar";

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
  const showRange = findings.some((item) => item.reference_low != null || item.reference_high != null);
  return (
    <div className="findings-table-wrap">
      <table className="findings-table">
        <thead>
          <tr>
            <th>Measurement</th>
            <th>Value</th>
            <th>Status</th>
            {showRange ? <th>Range</th> : null}
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
              <td>{(item.status || "").replace(/_/g, " ")}</td>
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
