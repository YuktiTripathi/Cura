import type { ExperienceBlock, PresentedFinding } from "../../types/chat";
import { ValueCard } from "./ValueCard";

type BlockGroup = {
  direct?: string;
  facts: PresentedFinding[];
  interpretation?: string;
  relevance?: string;
  uncertainties: string[];
  nextSteps: string[];
};

function collect(blocks: ExperienceBlock[]): BlockGroup {
  const sorted = [...blocks].sort((a, b) => a.sequence - b.sequence);
  const facts: PresentedFinding[] = [];
  const uncertainties: string[] = [];
  const nextSteps: string[] = [];
  let direct: string | undefined;
  let interpretation: string | undefined;
  let relevance: string | undefined;

  for (const block of sorted) {
    const text = block.text?.trim();
    if (block.kind === "direct_answer" && text) direct = text;
    if (block.kind === "interpretation" && text) interpretation = text;
    if (block.kind === "personal_relevance" && text) relevance = text;
    if (block.kind === "uncertainty" && text && !uncertainties.includes(text)) uncertainties.push(text);
    if (block.kind === "next_step" && text && !nextSteps.includes(text)) nextSteps.push(text);
    if (block.kind === "key_facts" && block.findings?.length) {
      for (const finding of block.findings) {
        const duplicate = facts.some(
          (item) =>
            item.canonical_key === finding.canonical_key &&
            item.value === finding.value &&
            item.source_date === finding.source_date
        );
        if (!duplicate) facts.push(finding);
      }
    }
  }
  return { direct, facts, interpretation, relevance, uncertainties, nextSteps };
}

/**
 * Renders P0-2 validated semantic blocks as a progressive health answer instead of
 * flattening them back into a growing paragraph. Blocks have already crossed the
 * backend's release boundary before this component sees them.
 */
export function StreamingExperience({ blocks }: { blocks: ExperienceBlock[] }) {
  const view = collect(blocks);
  if (!blocks.length) return null;

  return (
    <div className="streaming-experience" data-testid="streaming-experience" aria-live="polite">
      {view.direct ? (
        <p className="streaming-lead experience-reveal" data-kind="direct_answer">
          {view.direct}
        </p>
      ) : null}

      {view.facts.length ? (
        <section className="experience-segment experience-reveal" data-kind="key_facts">
          <div className="experience-segment-label">From your records</div>
          <div className="value-cards streaming-values">
            {view.facts.map((finding, index) => (
              <ValueCard key={`${finding.canonical_key || finding.label}-${index}`} finding={finding} compact={view.facts.length === 1} />
            ))}
          </div>
        </section>
      ) : null}

      {view.interpretation ? (
        <section className="experience-segment experience-reveal" data-kind="interpretation">
          <div className="experience-segment-label">What it means</div>
          <p>{view.interpretation}</p>
        </section>
      ) : null}

      {view.relevance ? (
        <aside className="personal-relevance experience-reveal" data-kind="personal_relevance" aria-label="Why this matters for you">
          <span>Why this matters for you</span>
          <p>{view.relevance}</p>
        </aside>
      ) : null}

      {view.uncertainties.length ? (
        <section className="experience-segment experience-segment-muted experience-reveal" data-kind="uncertainty">
          <div className="experience-segment-label">Still unclear</div>
          <ul>
            {view.uncertainties.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {view.nextSteps.length ? (
        <section className="experience-segment experience-next experience-reveal" data-kind="next_step">
          <div className="experience-segment-label">A useful next step</div>
          <ul>
            {view.nextSteps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="experience-working" role="status">
        <span aria-hidden="true" />
        <span>CURA is completing the picture</span>
      </div>
    </div>
  );
}
