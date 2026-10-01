import type { PresentedFinding } from "../../types/chat";
import { ValueCard } from "./ValueCard";

/** The user's own values, shown as soon as they are retrieved and before the explanation is ready. */
export function PreviewAnswer({ findings }: { findings: PresentedFinding[] }) {
  return (
    <div className="answer-block" data-testid="answer-preview">
      <p className="preview-note">Here's what your records show. Writing your explanation…</p>
      <div className="value-cards">
        {findings.map((item, index) => (
          <ValueCard key={`${item.label}-${index}`} finding={item} />
        ))}
      </div>
    </div>
  );
}
