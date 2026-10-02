import type { StructuredResponse, TestingOption } from "../../types/chat";
import { AssistantBody } from "./AssistantBody";
import { FindingsTable, RawResultsDisclosure, RelatedResults } from "./FindingsTable";
import { TestingOptionCard } from "./TestingOptionCard";
import { ThemeList } from "./ThemeCards";
import { ValueCard } from "./ValueCard";
import { NextSteps } from "./NextSteps";

function isDisclaimer(text: string): boolean {
  return /not a (medical )?diagnosis/i.test(text);
}

export function PresentedAnswer({
  presentation,
  fallback,
  testingOption,
}: {
  presentation: StructuredResponse;
  fallback: string;
  testingOption?: TestingOption | null;
}) {
  const narrative = presentation.summary_style === "NARRATIVE_HEALTH_SUMMARY" || Boolean(presentation.themes && presentation.themes.length > 0);
  const showHeadline = !narrative && presentation.mode !== "SINGLE_VALUE" && Boolean(presentation.headline);
  const findings = presentation.findings || [];
  const gaps = (presentation.uncertainties || []).filter((item) => !isDisclaimer(item));
  const notes = (presentation.uncertainties || []).filter(isDisclaimer);
  const useCards = findings.length > 0 && findings.length <= 3 && presentation.mode !== "SINGLE_VALUE";
  // A single value is stated in the summary sentence; the card adds where it sits in its range.
  const singleWithRange =
    !narrative &&
    presentation.mode === "SINGLE_VALUE" &&
    findings.length === 1 &&
    (findings[0].reference_low != null || findings[0].reference_high != null);
  return (
    <div className="answer-block">
      {presentation.topic_summary?.text ? (
        <p className="topic-summary" data-testid="topic-summary">
          {presentation.topic_summary.text}
        </p>
      ) : null}
      {showHeadline ? <h3 className="answer-headline">{presentation.headline}</h3> : null}
      {presentation.overall_summary || presentation.summary ? (
        <p className="answer-summary">{presentation.overall_summary || presentation.summary}</p>
      ) : null}
      {presentation.personal_relevance ? (
        <aside className="personal-relevance" aria-label="Why this matters for you">
          <span>Why this matters for you</span>
          <p>{presentation.personal_relevance}</p>
        </aside>
      ) : null}
      {singleWithRange ? <ValueCard finding={findings[0]} compact /> : null}
      {narrative ? <ThemeList themes={presentation.themes || []} /> : null}
      {narrative ? <RawResultsDisclosure findings={presentation.raw_findings || []} /> : null}
      {!narrative && findings.length > 0 && presentation.mode !== "SINGLE_VALUE" ? (
        useCards ? (
          <div className="value-cards">
            {findings.map((item, index) => (
              <ValueCard key={`${item.label}-${index}`} finding={item} />
            ))}
          </div>
        ) : (
          <FindingsTable findings={findings} />
        )
      ) : null}
      {!narrative && presentation.interpretation ? (
        <section className="answer-section">
          <h4>How to read this</h4>
          <p>{presentation.interpretation}</p>
        </section>
      ) : null}
      {!narrative && gaps.length > 0 ? (
        <section className="answer-section">
          <h4>What’s still unclear</h4>
          <ul>
            {gaps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {notes.map((item) => (
        <p className="answer-note" key={item}>
          {item}
        </p>
      ))}
      <NextSteps items={presentation.next_steps || []} />
      {!presentation.summary && !presentation.overall_summary && !findings.length && !presentation.interpretation && !narrative ? (
        <p>
          <AssistantBody content={fallback} />
        </p>
      ) : null}
      {(presentation.related_findings || []).length > 0 ? (
        <RelatedResults findings={presentation.related_findings || []} />
      ) : null}
      {(testingOption || presentation.testing_option) ? (
        <TestingOptionCard option={(testingOption || presentation.testing_option)!} />
      ) : null}
    </div>
  );
}
