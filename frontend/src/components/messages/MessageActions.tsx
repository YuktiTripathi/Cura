import { useEffect, useState } from "react";

export type FeedbackRating = "up" | "down";

/** Copy, regenerate, view sources and feedback for one assistant answer. */
export function MessageActions({
  text,
  onFeedback,
  onRegenerate,
  sourceCount = 0,
  onViewSources,
  disabled = false,
}: {
  text: string;
  onFeedback: (rating: FeedbackRating, comment?: string) => void;
  onRegenerate?: () => void;
  sourceCount?: number;
  onViewSources?: () => void;
  disabled?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [rated, setRated] = useState<FeedbackRating | null>(null);
  const [askingReason, setAskingReason] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!copied) return;
    const id = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(id);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  }

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
        <button type="button" className="text-button" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
        {onRegenerate ? (
          <button type="button" className="text-button" onClick={onRegenerate} disabled={disabled}>
            Regenerate
          </button>
        ) : null}
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
            <span className="muted">Was this helpful?</span>
            <button type="button" className="text-button" aria-label="Helpful" onClick={() => rate("up")}>
              👍
            </button>
            <button type="button" className="text-button" aria-label="Not helpful" onClick={() => rate("down")}>
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
            placeholder="What was wrong or missing? (optional)"
            aria-label="What was wrong or missing?"
            autoFocus
          />
          <button type="submit">Send</button>
          <button type="button" className="text-button" onClick={() => sendDown(false)}>
            Skip
          </button>
        </form>
      ) : null}
    </div>
  );
}
