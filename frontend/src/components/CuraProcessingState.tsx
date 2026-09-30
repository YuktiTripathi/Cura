import { processingCopy, uiStageFor, type CuraProcessingUiStage, type ProcessingEvent } from "../lib/processingMessages";

type Props = {
  event: ProcessingEvent | null;
};

export function CuraProcessingState({ event }: Props) {
  if (!event || event.stage === "COMPLETE") return null;
  const stage: CuraProcessingUiStage = uiStageFor(event.stage);
  const text = processingCopy(event);
  if (!text) return null;
  return (
    <div className="cura-processing" data-stage={stage} role="status" aria-live="polite">
      <span className="cura-processing-dot" aria-hidden="true" />
      <p>{text}</p>
    </div>
  );
}
