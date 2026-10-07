import { t } from "../../i18n";
import { followUpText, type EmergencyContact, type FollowUp, type Recommendation } from "../../types/chat";

export function Recommendations({ items }: { items: Recommendation[] }) {
  if (!items.length) return null;
  return (
    <div className="recommendations">
      <p>{t("ui.MessageExtras.suggested_actions", "Suggested actions")}</p>
      {items.map((r, index) => (
        <div className="recommendation-card" key={`${r.category}-${index}`}>
          <strong>{r.category.replace(/_/g, " ")}</strong>
          <p>{r.text}</p>
        </div>
      ))}
    </div>
  );
}

export function EscalationNote({
  escalation,
  contacts = [],
}: {
  escalation: string;
  contacts?: EmergencyContact[];
}) {
  const urgent = escalation === "urgent_care" || escalation === "crisis_support";
  return (
    <div className="escalation">
      <strong>{t("escalation.title", "Next step")}</strong>
      <p>
        {escalation === "crisis_support"
          ? t("escalation.crisis", "Please talk to someone now. Help is free and available 24x7.")
          : escalation === "urgent_care"
          ? t("escalation.urgent", "Seek urgent in-person medical care.")
          : escalation === "see_doctor_24h"
          ? t("escalation.soon", "See a doctor within the next day.")
          : t("escalation.clinician", "Discuss this with a qualified clinician.")}
      </p>
      {urgent && contacts.length > 0 && (
        <div className="escalation-calls">
          {contacts.map((c) => (
            <a key={c.kind} className="escalation-call" href={`tel:${c.number}`}>
              {t("escalation.call", "Call {label} {number}", { label: c.label, number: c.number })}
            </a>
          ))}
        </div>
      )}
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
      <span className="follow-up-label">{t("ui.MessageExtras.continue_with_cura", "Continue with CURA")}</span>
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
