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

export function FollowUpChips({
  items,
  onPick,
}: {
  items: Array<FollowUp | string>;
  onPick: (value: string) => void;
}) {
  if (!items.length) return null;
  return (
    <div className="follow-up-group">
      <span className="follow-up-label">Continue with CURA</span>
      <div className="chips follow-up-chips">
        {items.map((f) => {
          const text = followUpText(f);
          return (
            <button key={text} type="button" onClick={() => onPick(text)}>
              <span>{text}</span>
              <span className="follow-up-arrow" aria-hidden="true">→</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
