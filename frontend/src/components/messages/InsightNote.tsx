import type { AnswerInsight } from "../../lib/companion";
import { useMarkerPanel } from "../marker/MarkerPanelContext";

/** Longitudinal notes the backend attached to this answer (never unsolicited: only what came with it). */
export function InsightNote({ insights }: { insights: AnswerInsight[] }) {
  const panel = useMarkerPanel();
  if (!insights.length) return null;
  return (
    <div className="insight-note" data-testid="insight-note">
      <ul>
        {insights.map((insight, index) => (
          <li key={`${insight.summary}-${index}`}>
            <span>{insight.summary}</span>
            {insight.entity && panel.has(insight.entity) ? (
              <button type="button" className="text-button" onClick={() => panel.open(insight.entity!)}>
                History
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
