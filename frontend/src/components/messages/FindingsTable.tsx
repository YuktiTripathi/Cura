import { useState } from "react";
import type { PresentedFinding } from "../../types/chat";

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
  return (
    <div className="findings-table-wrap">
      <table className="findings-table">
        <thead>
          <tr>
            <th>Measurement</th>
            <th>Value</th>
            <th>Status</th>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
