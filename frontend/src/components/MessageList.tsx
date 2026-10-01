import { useState } from "react";
import { openSuperShyftPackage } from "../lib/packageActions";
import { assistantTextSegments, followUpText, displayAssistantText, type ContextRef, type HealthTheme, type PackageAction, type PresentedFinding, type StructuredResponse, type TestingOption, type UserProvenance } from "../types/chat";
import type { ChatMessage } from "../hooks/useCuraChat";

export function MessageList({
  messages,
  onFollowUp,
  onAskContext: _onAskContext,
  onFeedback,
  onEditQuestion,
  editingDisabled = false,
}: {
  messages: ChatMessage[];
  onFollowUp: (value: string) => void;
  onAskContext: (value: string, contextRef: ContextRef) => void;
  onFeedback: (rating: "up" | "down") => void;
  onEditQuestion?: (index: number, text: string) => void;
  editingDisabled?: boolean;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  function startEdit(index: number, content: string) {
    setEditingIndex(index);
    setDraft(content);
  }

  function saveEdit() {
    if (editingIndex == null) return;
    const text = draft.trim();
    if (!text) return;
    onEditQuestion?.(editingIndex, text);
    setEditingIndex(null);
    setDraft("");
  }

  return (
    <div className="messages">
      {messages.map((m, i) => (
        <article key={i} className={m.role}>
          {m.role === "user" && editingIndex === i ? (
            <div className="edit-question">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                aria-label="Edit question"
              />
              <div className="edit-question-actions">
                <button type="button" onClick={saveEdit} disabled={!draft.trim()}>
                  Save
                </button>
                <button type="button" className="text-button" onClick={() => setEditingIndex(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : m.role === "assistant" && m.presentation ? (
            <PresentedAnswer
              presentation={m.presentation}
              fallback={m.content}
              testingOption={m.testingOption || m.presentation.testing_option}
            />
          ) : (
            <p>{m.role === "assistant" ? <AssistantBody content={m.content} /> : m.content}</p>
          )}
          {m.role === "user" && editingIndex !== i && onEditQuestion && (
            <div className="user-actions">
              <button
                type="button"
                className="text-button"
                disabled={editingDisabled}
                onClick={() => startEdit(i, m.content)}
              >
                Edit
              </button>
            </div>
          )}
          {m.testingOption && !m.presentation ? (
            <TestingOptionCard option={m.testingOption} />
          ) : null}
          {m.recommendations && m.recommendations.length > 0 && (
            <div className="recommendations">
              <p>Suggested actions</p>
              {m.recommendations.map((r, index) => (
                <div className="recommendation-card" key={`${r.category}-${index}`}>
                  <strong>{r.category.replace(/_/g, " ")}</strong>
                  <p>{r.text}</p>
                </div>
              ))}
            </div>
          )}
          {m.meta?.escalation && (
            <div className="escalation">
              <strong>Next step</strong>
              <p>
                {m.meta.escalation === "urgent_care"
                  ? "Seek urgent in-person medical care."
                  : "Discuss this with a qualified clinician."}
              </p>
            </div>
          )}
          {m.role === "assistant" && (
            <ProvenanceLine
              provenance={m.provenance}
              findings={
                m.presentation?.findings && m.presentation.findings.length > 0
                  ? m.presentation.findings
                  : m.presentation?.raw_findings
              }
            />
          )}
          {m.role === "assistant" && m.content && (
            <div className="feedback-actions">
              <span className="muted">Was this helpful?</span>
              <button type="button" className="text-button" onClick={() => onFeedback("up")}>👍</button>
              <button type="button" className="text-button" onClick={() => onFeedback("down")}>👎</button>
            </div>
          )}
          {m.followUps && m.followUps.length > 0 && (
            <div className="chips">
              {m.followUps.map((f) => {
                const text = followUpText(f);
                return (
                  <button key={text} type="button" onClick={() => onFollowUp(text)}>
                    {text}
                  </button>
                );
              })}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function debugMode(): boolean {
  return import.meta.env.VITE_CURA_DEBUG === "true";
}

function isDisclaimer(text: string): boolean {
  return /not a (medical )?diagnosis/i.test(text);
}

function PresentedAnswer({
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

function TestingOptionCard({ option }: { option: TestingOption }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const name = option.package?.name || option.display_name;
  const reason = option.reason || option.medical_rationale || "";
  const headline = option.headline || "A test that may help clarify this";
  const primary = option.primary_action || {
    type: "OPEN_PACKAGE" as const,
    label: `View ${name}`,
    package_id: option.package?.id || option.catalog_id,
    catalog_kind: option.package?.kind || option.kind,
  };
  const comparison = option.comparison;
  const relevance = option.relevance || "OPTIONAL";
  const alreadyHave =
    comparison?.already_have?.length
      ? comparison.already_have
      : (option.already_recent || []).map((label) => ({ key: label, label, measured_on: null }));

  function runAction(action: PackageAction) {
    if (action.type === "COMPARE_WITH_EXISTING_RESULTS") {
      setDetailsOpen(true);
      return;
    }
    const packageId = action.package_id || option.package?.id || option.catalog_id;
    if (action.type === "OPEN_PACKAGE" && packageId) {
      openSuperShyftPackage(action.catalog_kind || option.kind, packageId);
    }
  }

  return (
    <section
      className={`testing-option testing-option-${relevance.toLowerCase()}`}
      data-testid="testing-option"
      data-relevance={relevance}
    >
      <p className="testing-option-headline">{headline}</p>
      <p className="testing-option-name">
        <strong>{name}</strong>
      </p>
      {reason ? <p className="testing-option-reason">{reason}</p> : null}
      <div className="testing-option-actions">
        <button
          type="button"
          className="testing-option-primary"
          data-testid="package-primary-cta"
          onClick={() => runAction(primary)}
        >
          {primary.label}
        </button>
        {option.secondary_action ? (
          <button
            type="button"
            className="text-button"
            data-testid="package-secondary-cta"
            onClick={() => runAction(option.secondary_action!)}
          >
            {option.secondary_action.label}
          </button>
        ) : null}
        <button
          type="button"
          className="text-button"
          data-testid="package-details-toggle"
          onClick={() => setDetailsOpen((value) => !value)}
        >
          {detailsOpen ? "Hide details" : "Details"}
        </button>
      </div>
      {detailsOpen ? (
        <div className="testing-option-details" data-testid="package-details">
          {option.helps_answer ? (
            <p>
              <strong>Helps answer: </strong>
              {option.helps_answer}
            </p>
          ) : null}
          {(option.relevant_tests || []).length > 0 ? (
            <div>
              <h4>Relevant tests</h4>
              <ul>
                {(option.relevant_tests || []).map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {alreadyHave.length > 0 ? (
            <div>
              <h4>Already in your reports</h4>
              <ul>
                {alreadyHave.map((item) => (
                  <li key={item.key}>
                    {item.label}
                    {item.measured_on ? ` · ${item.measured_on}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {(comparison?.adds_information || []).length > 0 ? (
            <div>
              <h4>Would add new information</h4>
              <ul>
                {comparison!.adds_information.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {comparison?.timing_note ? <p className="muted">{comparison.timing_note}</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function ThemeList({ themes }: { themes: HealthTheme[] }) {
  return (
    <div className="theme-cards">
      {themes.map((theme) => (
        <ThemeCard key={theme.title} theme={theme} />
      ))}
    </div>
  );
}

function ThemeCard({ theme }: { theme: HealthTheme }) {
  const [open, setOpen] = useState(false);
  const related = theme.related_findings || [];
  return (
    <article className={`theme-card theme-${theme.status}`} data-testid="health-theme">
      <header>
        <h4>{theme.title}</h4>
        <span className="theme-status">{theme.status.replace(/_/g, " ")}</span>
      </header>
      {theme.interpretation ? <p>{theme.interpretation}</p> : null}
      {theme.missing_information && theme.missing_information.length > 0 ? (
        <ul className="theme-missing">
          {theme.missing_information.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
      {related.length > 0 ? (
        <div>
          <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
            {open ? "Hide related values" : "Related values"}
          </button>
          {open ? <FindingsTable findings={related} /> : null}
        </div>
      ) : null}
    </article>
  );
}

function RelatedResults({ findings }: { findings: PresentedFinding[] }) {
  const [open, setOpen] = useState(false);
  if (!findings.length) return null;
  return (
    <div className="related-results">
      <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
        {open ? "Hide related results" : "View related results"}
      </button>
      {open ? <FindingsTable findings={findings} /> : null}
    </div>
  );
}

function RawResultsDisclosure({ findings }: { findings: PresentedFinding[] }) {
  const [open, setOpen] = useState(false);
  if (!findings.length) return null;
  return (
    <div className="raw-results">
      <button type="button" className="text-button" onClick={() => setOpen((value) => !value)}>
        {open ? "Hide full results" : "View all results"}
      </button>
      {open ? <FindingsTable findings={findings} /> : null}
    </div>
  );
}

function FindingsTable({ findings }: { findings: PresentedFinding[] }) {
  return (
    <div className="findings-table-wrap">
      <table className="findings-table">
        <thead>
          <tr>
            <th>Measurement</th>
            <th>Value</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((item, index) => (
            <tr key={`${item.label}-${index}`}>
              <td>{item.label}</td>
              <td>
                {item.value ?? "—"}
                {item.unit ? ` ${item.unit}` : ""}
              </td>
              <td>{(item.status || "").replace(/_/g, " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AssistantBody({ content }: { content: string }) {
  const text = displayAssistantText(content, debugMode());
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, index) => (
        <span key={index}>
          {index > 0 ? <br /> : null}
          {assistantTextSegments(line).map((part, partIndex) =>
            part.bold ? <strong key={partIndex}>{part.text}</strong> : <span key={partIndex}>{part.text}</span>
          )}
        </span>
      ))}
    </>
  );
}

function ProvenanceLine({
  provenance,
  findings,
}: {
  provenance?: UserProvenance;
  findings?: Array<{ source_id?: string | null; source_label?: string | null }>;
}) {
  const sources = provenance?.sources || [];
  if (!sources.length) return null;
  const label = sources.length === 1 ? "Source" : "Sources";
  const debug = debugMode();
  return (
    <details className="source-details">
      <summary className="source-line" data-testid="provenance-line">
        {label}:{" "}
        {sources.map((source, index) => (
          <span key={`${source.name}-${index}`}>
            {index > 0 ? " · " : null}
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.name}
              </a>
            ) : (
              source.name
            )}
          </span>
        ))}
      </summary>
      <div className="source-debug" data-testid="provenance-debug">
        {debug
          ? sources.map((source, index) => (
              <p key={`${source.source_id || source.name}-${index}`}>
                {source.name}
                {source.source_id ? ` · ${source.source_id}` : ""}
              </p>
            ))
          : findings?.some((item) => item.source_label) ? (
              findings
                .filter((item) => item.source_label)
                .filter((item, index, all) => all.findIndex((row) => row.source_label === item.source_label) === index)
                .map((item) => <p key={item.source_label || ""}>{item.source_label}</p>)
            ) : (
              <p>Internal record identifiers are hidden. Dates above identify the report that was used.</p>
            )}
      </div>
    </details>
  );
}
