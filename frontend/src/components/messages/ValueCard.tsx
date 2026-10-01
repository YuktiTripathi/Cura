import type { PresentedFinding } from "../../types/chat";
import { numericValue } from "../../lib/range";
import { RangeBar } from "./RangeBar";

/** One measured value: name, value with unit, where it sits in its reference range, and when. */
export function ValueCard({ finding, compact = false }: { finding: PresentedFinding; compact?: boolean }) {
  const value = numericValue(finding);
  const hasRange = finding.reference_low != null || finding.reference_high != null;
  return (
    <article className={`value-card${compact ? " compact" : ""}`} data-testid="value-card">
      <header>
        <strong>{finding.label}</strong>
        {finding.source_date ? <span className="value-card-date">{shortDate(finding.source_date)}</span> : null}
      </header>
      <p className="value-card-value">
        {finding.value ?? "—"}
        {finding.unit ? <span className="value-card-unit"> {finding.unit}</span> : null}
      </p>
      {hasRange && value != null ? (
        <RangeBar
          label={finding.label}
          value={value}
          unit={finding.unit}
          low={finding.reference_low}
          high={finding.reference_high}
        />
      ) : finding.status ? (
        <span className="value-card-status">{finding.status.replace(/_/g, " ")}</span>
      ) : null}
    </article>
  );
}

function shortDate(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
