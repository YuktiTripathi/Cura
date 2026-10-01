import { useState } from "react";
import type { ContextRef, PresentedFinding } from "../../types/chat";
import type { MarkerOverview } from "../../types/overview";
import { useOverview } from "../../hooks/useOverview";
import { fmt } from "../../lib/range";
import { FindingsTable } from "../messages/FindingsTable";
import { ValueCard } from "../messages/ValueCard";
import { useMarkerPanel } from "../marker/MarkerPanelContext";
import { shortDate } from "../marker/TrendChart";

const OUT = new Set(["low", "high", "critical"]);
const MAX_ATTENTION = 4;

export function toFinding(marker: MarkerOverview): PresentedFinding {
  return {
    label: marker.label,
    value: fmt(marker.value),
    unit: marker.unit,
    status: marker.status,
    source_date: marker.measured_on,
    canonical_key: marker.key,
    numeric_value: marker.value,
    reference_low: marker.reference_low,
    reference_high: marker.reference_high,
  };
}

function changeNote(marker: MarkerOverview): string | null {
  if (marker.previous_value == null || !marker.previous_on) return null;
  const since = shortDate(marker.previous_on);
  if (marker.trend === "toward_range") return `Improving · was ${fmt(marker.previous_value)} on ${since}`;
  if (marker.trend === "away_from_range") return `Further from range · was ${fmt(marker.previous_value)} on ${since}`;
  return `Was ${fmt(marker.previous_value)} on ${since}`;
}

/** Home dashboard: what needs attention, what is improving, and what is worth a look. */
export function HealthOverviewSection({
  onSend,
}: {
  onSend: (text: string, documentIds?: string[], contextRef?: ContextRef) => void;
}) {
  const { data } = useOverview();
  const panel = useMarkerPanel();
  const [showAll, setShowAll] = useState(false);
  if (!data || !data.markers?.length) return null;

  const markers = data.markers;
  const attention = markers.filter((m) => OUT.has(m.status || "")).slice(0, MAX_ATTENTION);
  const improving = markers.filter((m) => m.trend === "toward_range");
  const insights = (data.insights || []).slice(0, 3);
  const labelFor = (key?: string | null) => markers.find((m) => m.key === key)?.label;

  return (
    <section className="health-home" aria-labelledby="health-home-title" data-testid="health-home">
      <header className="health-home-header">
        <h2 id="health-home-title">Your health at a glance</h2>
        {data.latest_report_date ? <span className="muted">Latest report · {shortDate(data.latest_report_date)}</span> : null}
      </header>

      {attention.length > 0 ? (
        <div className="health-home-block">
          <h3>Needs attention</h3>
          <div className="value-cards">
            {attention.map((marker) => (
              <ValueCard key={marker.key} finding={toFinding(marker)} note={changeNote(marker)} />
            ))}
          </div>
        </div>
      ) : (
        <p className="health-home-calm">All of your latest results are within their reference ranges.</p>
      )}

      {improving.length > 0 ? (
        <div className="health-home-block">
          <h3>Improving</h3>
          <div className="chips">
            {improving.map((marker) => (
              <button key={marker.key} type="button" onClick={() => panel.open(marker.key)}>
                <span aria-hidden="true">↗ </span>
                {marker.label}: {fmt(marker.previous_value ?? marker.value)} → {fmt(marker.value)}
                {marker.unit ? ` ${marker.unit}` : ""}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {insights.length > 0 ? (
        <div className="health-home-block">
          <h3>Worth a look</h3>
          <ul className="insight-list">
            {insights.map((insight, index) => (
              <li key={`${insight.title}-${index}`}>
                <span>
                  <strong>{insight.title}</strong> {insight.summary}
                </span>
                <span className="insight-actions">
                  {insight.marker_key && panel.has(insight.marker_key) ? (
                    <button type="button" className="text-button" onClick={() => panel.open(insight.marker_key!)}>
                      History
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="text-button"
                    onClick={() =>
                      onSend(
                        labelFor(insight.marker_key)
                          ? `What should I know about my ${labelFor(insight.marker_key)}?`
                          : `Tell me more: ${insight.summary}`,
                        [],
                        insight.marker_key
                          ? { type: "blood_marker", source: "supershyft", marker_code: insight.marker_key }
                          : undefined
                      )
                    }
                  >
                    Ask Cura
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="health-home-block">
        <button type="button" className="text-button" aria-expanded={showAll} onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Hide all results" : `See all ${markers.length} latest results`}
        </button>
        {showAll ? <FindingsTable findings={markers.map(toFinding)} /> : null}
      </div>
    </section>
  );
}
