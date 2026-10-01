import type { StructuredResponse, TestingOption } from "../../types/chat";
import { AssistantBody } from "./AssistantBody";
import { FindingsTable, RawResultsDisclosure, RelatedResults } from "./FindingsTable";
import { TestingOptionCard } from "./TestingOptionCard";
import { ThemeList } from "./ThemeCards";

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
      {narrative ? <ThemeList themes={presentation.themes || []} /> : null}
      {narrative ? <RawResultsDisclosure findings={presentation.raw_findings || []} /> : null}
      {!narrative && findings.length > 0 && presentation.mode !== "SINGLE_VALUE" ? (
        useCards ? (
          <div className="findings-cards">
            {findings.map((item, index) => (
              <article className="finding-card" key={`${item.label}-${index}`}>
                <strong>{item.label}</strong>
                <p>
                  {item.value ?? "—"}
                  {item.unit ? ` ${item.unit}` : ""}
                </p>
                {item.status ? <span>{item.status.replace(/_/g, " ")}</span> : null}
              </article>
            ))}
          </div>
        ) : (
          <FindingsTable findings={findings} />
        )
      ) : null}
      {!narrative && presentation.interpretation ? (
        <section className="answer-section">
          <h4>What this may mean</h4>
          <p>{presentation.interpretation}</p>
        </section>
      ) : null}
      {!narrative && gaps.length > 0 ? (
        <section className="answer-section">
          <h4>Still uncertain</h4>
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
      {presentation.next_steps && presentation.next_steps.length > 0 ? (
        <section className="answer-section">
          <h4>Worth considering</h4>
          <ul>
            {presentation.next_steps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
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
