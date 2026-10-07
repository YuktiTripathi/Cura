import { processingCopy, type ProcessingEvent } from "../lib/processingMessages";
import { CuraProcessingState } from "./CuraProcessingState";
import { t } from "../i18n";

const MAX_DONE_VISIBLE = 3;

/**
 * One entry per distinct sentence, in the order last shown. Several backend stages share copy
 * ("Preparing your explanation…"), so a repeat moves to the end instead of being listed twice.
 * REQUEST_RECEIVED is skipped: it arrives after the client's own "Understanding…" placeholder.
 */
export function progressSteps(events: ProcessingEvent[]): Array<{ event: ProcessingEvent; text: string }> {
  const steps: Array<{ event: ProcessingEvent; text: string }> = [];
  for (const event of events) {
    if (event.stage === "COMPLETE" || event.stage === "REQUEST_RECEIVED") continue;
    const text = processingCopy(event);
    if (!text) continue;
    const existing = steps.findIndex((step) => step.text === text);
    if (existing >= 0) steps.splice(existing, 1);
    steps.push({ event, text });
  }
  return steps;
}

export function ProgressStepper({ events }: { events: ProcessingEvent[] }) {
  const steps = progressSteps(events);
  if (!steps.length) return null;
  const current = steps[steps.length - 1];
  const done = steps.slice(0, -1).slice(-MAX_DONE_VISIBLE);
  return (
    <div className="progress-stepper" data-testid="progress-stepper">
      {done.length > 0 && (
        <ol className="progress-done" aria-label={t("ui.ProgressStepper.completed_steps", "Completed steps")}>
          {done.map((step) => (
            <li key={step.text}>
              <span className="progress-check" aria-hidden="true">✓</span>
              {step.text.replace(/…$/, "")}
            </li>
          ))}
        </ol>
      )}
      <CuraProcessingState event={current.event} />
    </div>
  );
}
