import { useState } from "react";
import { t } from "../../i18n";

export type FeedbackRating = "up" | "down";

/** Feedback, and sources when the answer has them. */
export function MessageActions({
  onFeedback,
  sourceCount = 0,
  onViewSources,
}: {
  text?: string;
  onFeedback: (rating: FeedbackRating, comment?: string) => void;
  onRegenerate?: () => void;
  sourceCount?: number;
  onViewSources?: () => void;
  onDoctorSummary?: () => void;
  disabled?: boolean;
}) {
  const [rated, setRated] = useState<FeedbackRating | null>(null);
  const [askingReason, setAskingReason] = useState(false);
  const [reason, setReason] = useState("");

  function rate(rating: FeedbackRating) {
    if (rating === "down") {
      setAskingReason(true);
      return;
    }
    setRated("up");
    onFeedback("up");
  }

  function sendDown(withReason: boolean) {
    setRated("down");
    setAskingReason(false);
    onFeedback("down", withReason && reason.trim() ? reason.trim() : undefined);
  }

  return (
    <div className="message-actions">
      <div className="message-actions-row">
        {sourceCount > 0 && onViewSources ? (
          <button type="button" className="text-button" onClick={onViewSources}>
            View sources ({sourceCount})
          </button>
        ) : null}
        <span className="message-actions-spacer" />
        {rated ? (
          <span className="muted" role="status">
            Thanks for the feedback
          </span>
        ) : (
          <span className="feedback-actions">
            <span className="muted">{t("ui.MessageActions.was_this_helpful", "Was this helpful?")}</span>
            <button type="button" className="text-button" aria-label={t("ui.MessageActions.helpful", "Helpful")} onClick={() => rate("up")}>
              👍
            </button>
            <button type="button" className="text-button" aria-label={t("ui.MessageActions.not_helpful", "Not helpful")} onClick={() => rate("down")}>
              👎
            </button>
          </span>
        )}
      </div>
      {askingReason ? (
        <form
          className="feedback-reason"
          onSubmit={(event) => {
            event.preventDefault();
            sendDown(true);
          }}
        >
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("ui.MessageActions.what_was_wrong_or_missing_optional", "What was wrong or missing? (optional)")}
            aria-label={t("ui.MessageActions.what_was_wrong_or_missing", "What was wrong or missing?")}
            autoFocus
          />
          <button type="submit">{t("ui.MessageActions.send", "Send")}</button>
          <button type="button" className="text-button" onClick={() => sendDown(false)}>
            Skip
          </button>
        </form>
      ) : null}
    </div>
  );
}
