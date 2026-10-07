import { useEffect, useRef } from "react";
import type { ContextRef } from "../../types/chat";
import type { MarkerOverview } from "../../types/overview";
import { fmt, formatBounds } from "../../lib/range";
import { RangeBar } from "../messages/RangeBar";
import { TrendChart, shortDate } from "./TrendChart";
import { t } from "../../i18n";

function historyStatus(status: string | null | undefined): string {
  const value = (status || "").toLowerCase().replace(/[\s-]+/g, "_");
  if (!value || value === "unknown") return "—";
  if (value === "low" || value === "below_range") return "Below range";
  if (value === "high" || value === "above_range") return "Above range";
  if (value === "normal" || value === "in_range") return "Within range";
  return status || "—";
}

const TREND_TEXT: Record<string, string> = {
  toward_range: "Moving toward the reference range",
  away_from_range: "Moving away from the reference range",
  steady: "About the same as last time",
  in_range: "Within the reference range",
};

/**
 * Non-modal detail panel for one marker: where it is now, how it has moved, every result, and
 * quick questions that carry the marker as context. A side column on wide screens, a sheet on phones.
 */
export function MarkerPanel({
  marker,
  onClose,
  onAsk,
}: {
  marker: MarkerOverview;
  onClose: () => void;
  onAsk: (text: string, contextRef: ContextRef) => void;
}) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus();
  }, [marker.key]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      // Escape inside a dialog (sources, doctor summary) closes that dialog, not this panel.
      if (event.target instanceof Element && event.target.closest("[role='dialog']")) return;
      onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const ref: ContextRef = { type: "blood_marker", source: "supershyft", marker_code: marker.key };
  const history = [...(marker.history || [])].sort((a, b) => b.date.localeCompare(a.date));
  const bounds = formatBounds(marker.reference_low, marker.reference_high, marker.unit);

  return (
    <aside className="marker-panel" aria-labelledby="marker-panel-title" data-testid="marker-panel">
      <header className="marker-panel-header">
        <h2 id="marker-panel-title" tabIndex={-1} ref={headingRef}>
          {marker.label}
        </h2>
        <button type="button" className="dialog-close" aria-label={`Close ${marker.label}`} onClick={onClose}>
          ×
        </button>
      </header>
      <p className="value-card-value">
        {fmt(marker.value)}
        {marker.unit ? <span className="value-card-unit"> {marker.unit}</span> : null}
      </p>
      <p className="muted marker-panel-date">
        {marker.measured_on ? `Latest result · ${shortDate(marker.measured_on)}` : "Latest result"}
      </p>
      <RangeBar label={marker.label} value={marker.value} unit={marker.unit} low={marker.reference_low} high={marker.reference_high} />
      {marker.trend ? <p className="marker-panel-trend">{TREND_TEXT[marker.trend]}</p> : null}
      {history.length >= 2 ? (
        <TrendChart
          label={marker.label}
          unit={marker.unit}
          points={history}
          low={marker.reference_low}
          high={marker.reference_high}
        />
      ) : (
        <p className="muted">{t("ui.MarkerPanel.only_one_result_so_far_a_trend_appears_a", "Only one result so far. A trend appears after your next report.")}</p>
      )}
      <table className="findings-table" aria-label={`${marker.label} results`}>
        <thead>
          <tr>
            <th>{t("ui.MarkerPanel.date", "Date")}</th>
            <th>{t("ui.MarkerPanel.value", "Value")}</th>
            <th>{t("ui.MarkerPanel.range", "Range")}</th>
            <th>{t("ui.MarkerPanel.status", "Status")}</th>
          </tr>
        </thead>
        <tbody>
          {history.map((point) => (
            <tr key={point.date}>
              <td>{shortDate(point.date)}</td>
              <td>
                {fmt(point.value)}
                {marker.unit ? ` ${marker.unit}` : ""}
              </td>
              <td>{bounds || "—"}</td>
              <td>{historyStatus(point.status)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {bounds ? <p className="muted marker-panel-ref">Reference range on your latest report: {bounds}</p> : null}
      <div className="chips marker-panel-ask">
        <button type="button" onClick={() => onAsk(`What does my ${marker.label} result mean?`, ref)}>
          What does this mean?
        </button>
        {history.length >= 2 ? (
          <button type="button" onClick={() => onAsk(`How has my ${marker.label} changed over time?`, ref)}>
            How has it changed?
          </button>
        ) : null}
        <button type="button" onClick={() => onAsk(`What can I do about my ${marker.label}?`, ref)}>
          What can I do?
        </button>
      </div>
    </aside>
  );
}
