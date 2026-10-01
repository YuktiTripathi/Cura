import { followUpText, type FollowUp, type Recommendation } from "../../types/chat";

export function Recommendations({ items }: { items: Recommendation[] }) {
  if (!items.length) return null;
  return (
    <div className="recommendations">
      <p>Suggested actions</p>
      {items.map((r, index) => (
        <div className="recommendation-card" key={`${r.category}-${index}`}>
          <strong>{r.category.replace(/_/g, " ")}</strong>
          <p>{r.text}</p>
        </div>
      ))}
    </div>
  );
}

export function EscalationNote({ escalation }: { escalation: string }) {
  return (
    <div className="escalation">
      <strong>Next step</strong>
      <p>
        {escalation === "urgent_care"
          ? "Seek urgent in-person medical care."
          : "Discuss this with a qualified clinician."}
      </p>
    </div>
  );
}

export function FeedbackActions({ onFeedback }: { onFeedback: (rating: "up" | "down") => void }) {
  return (
    <div className="feedback-actions">
      <span className="muted">Was this helpful?</span>
      <button type="button" className="text-button" onClick={() => onFeedback("up")}>👍</button>
      <button type="button" className="text-button" onClick={() => onFeedback("down")}>👎</button>
    </div>
  );
}

export function FollowUpChips({
  items,
  onPick,
}: {
  items: Array<FollowUp | string>;
  onPick: (value: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="chips">
      {items.map((f) => {
        const text = followUpText(f);
        return (
          <button key={text} type="button" onClick={() => onPick(text)}>
            {text}
          </button>
        );
      })}
    </div>
  );
}
