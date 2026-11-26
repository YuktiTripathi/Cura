import { useState } from "react";
import { LineIcon } from "../LineIcon";
import { BODY_AT_WORK, CATEGORY_PLACEHOLDER, friendlyBiomarkerName } from "./bodyAtWork";
import type { ChatMessage } from "../../hooks/useCuraChat";
import { MarkdownAnswer } from "../messages/MarkdownAnswer";
import { MessageList } from "../MessageList";
import { Composer } from "../Composer";
import type { ContextRef } from "../../types/chat";
import type { CategoryDetail, Finding } from "../../types/unifiedHealth";
import type { HealthView } from "../../lib/api";

type Place = "home" | "overview" | "category" | "marker" | "risk";

type Edu = NonNullable<Finding["education"]> & {
  body?: string;
  why_it_matters?: string;
  limitations?: string;
  content_source?: string;
  review_status?: string;
  factors?: string[];
  actions?: string[];
  questions?: string[];
  related_markers?: string[];
};


function cap(text?: string | null): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** 2026-08-18 becomes "18 Aug 2026"; anything that is not an ISO date is shown as given. */
function friendlyDate(value?: string | null): string | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function ResultRow({ title, value, note, open, onOpen }: { title: string; value?: string | null; note?: string | null; open?: boolean; onOpen: () => void }) {
  return (
    <div className="result-row">
      <button type="button" className="result-row-button" aria-expanded={open} onClick={onOpen}>
        <span className="result-row-main">
          <strong>{title}</strong>
          {note ? <span className="muted">{note}</span> : null}
        </span>
        {value ? <span className="result-row-value">{value}</span> : null}
        <span className="result-row-chevron" aria-hidden="true">{open ? "▾" : "›"}</span>
      </button>
    </div>
  );
}

function uniqueParagraphs(parts: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of parts) {
    const text = (part || "").trim();
    if (!text) continue;
    const key = text.toLowerCase().replace(/\s+/g, " ");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(text);
  }
  return out;
}

function splitLines(text?: string | null): string[] {
  return uniqueParagraphs((text || "").split(/(?<=\.)\s+/));
}

function InlineFinding({ finding, siblings = [] }: { finding: Finding; siblings?: Finding[] }) {
  const edu = finding.education as Edu | null | undefined;
  const predicted = finding.source_type === "predicted_risk";
  const name = friendlyBiomarkerName(finding.name);
  const about = uniqueParagraphs([edu?.what_it_is, edu?.body]);
  const why = splitLines(edu?.why_it_matters).filter((line) => !about.includes(line));
  const limits = splitLines(edu?.limitations).filter((line) => !about.includes(line) && !why.includes(line)).slice(0, 2);
  const related = (edu?.related_markers || []).map((code) => code.toLowerCase());
  const linked = siblings.filter((item) => {
    const codeOnRow = ((item as Finding & { marker_code?: string | null }).marker_code || "").toLowerCase();
    return item.id !== finding.id && item.source_type === "measured" && related.some((code) => codeOnRow === code || item.name.toLowerCase().includes(code.split("_").join(" ")));
  });
  const sameArea = linked.length ? linked : predicted ? siblings.filter((item) => item.id !== finding.id && item.source_type === "measured").slice(0, 2) : [];
  return (
    <div className="inline-finding">
      {about.length ? (
        <section>
          <h3>{predicted ? `What exactly is ${name.toLowerCase()}?` : `What is ${name}?`}</h3>
          {about.map((line) => <MarkdownAnswer key={line} content={line} />)}
        </section>
      ) : null}
      {why.length ? (
        <section>
          <h3>{predicted ? "Why should you care about it?" : "Why this test matters"}</h3>
          <ul>{why.map((line) => <li key={line}>{line}</li>)}</ul>
        </section>
      ) : null}
      <section>
        <h3>What your results tell us</h3>
        {predicted && finding.score != null ? (
          <p>Your Bio-AI score of <strong>{finding.score}</strong>{finding.classification ? <> is classified by the report as <strong>{cap(finding.classification)}</strong></> : null}. This is a predicted risk, not a diagnosis, and the score is not a percentage chance.</p>
        ) : null}
        {finding.value != null ? (
          <p><strong>{name}</strong> is <strong>{finding.value}{finding.unit ? ` ${finding.unit}` : ""}</strong>{finding.status_label ? `, ${finding.status_label.toLowerCase()}` : ""}.</p>
        ) : null}
        {finding.value != null ? <p>{resultMeaning(finding, edu)}</p> : null}
        <RangeNote finding={finding} />
        {predicted && sameArea.length ? sameArea.map((item) => (
          <p key={item.id}><strong>{friendlyBiomarkerName(item.name)}</strong>{item.value != null ? <> is <strong>{item.value}{item.unit ? ` ${item.unit}` : ""}</strong></> : null}{item.status_label ? `, ${item.status_label.toLowerCase()}` : ""}. This is a measured result in the same health area, not a confirmed contributor to the score.</p>
        )) : null}
        {finding.previous_value != null ? <p className="muted">Earlier result: {finding.previous_value}{finding.previous_on ? ` on ${friendlyDate(finding.previous_on)}` : ""}.</p> : null}
      </section>
      {edu?.factors?.length ? (
        <section>
          <h3>What can influence {predicted ? name.toLowerCase() : "this result"}?</h3>
          <ul className="factor-list">{edu.factors.map((item) => <li key={item}>{item}</li>)}</ul>
          <p className="muted">These are general influencing factors from the knowledge library, not confirmed reasons for this individual score.</p>
        </section>
      ) : null}
      {edu?.actions?.length ? (
        <section>
          <h3>Small things you can do for your body</h3>
          <ul>{edu.actions.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      ) : null}
      {limits.map((line) => <p key={line} className="muted">{line}</p>)}
      {edu?.review_status === "pending_clinical_review" ? <p className="muted">This explanation is educational text awaiting clinical review. It is not marked as clinically approved.</p> : null}
    </div>
  );
}

function questions(view: HealthView, categoryId: string | null, limit = 4): string[] {
  if (!categoryId) return [];
  return (view.suggested_questions?.[categoryId] || []).filter(Boolean).slice(0, limit);
}

/** Labels of the sections the detail screen shows, so CURA does not explain them again from scratch. */
function shownSections(finding?: Finding | null): string[] {
  if (!finding) return [];
  const edu = finding.education as Edu | null | undefined;
  const out: string[] = [];
  if (edu?.what_it_is) out.push("what_it_is");
  if (edu?.body && edu.body !== edu.what_it_is) out.push("inside_body");
  if (finding.source_type === "predicted_risk") out.push("assessment", "score");
  else out.push("your_result", "reference_range");
  if (edu?.why_it_matters) out.push("why_it_matters");
  if (edu?.limitations) out.push("limitations");
  if (finding.previous_value != null) out.push("previous_result");
  return out;
}

function refFor(view: HealthView, categoryId: string | null, finding?: Finding | null): ContextRef {
  const base: ContextRef = {
    type: finding?.source_type === "predicted_risk" ? "bio_ai_risk" : finding ? "blood_marker" : "bio_ai_report",
    source: "supershyft",
    entry_point: "health_area",
    category_id: categoryId,
    finding_id: finding?.id ?? null,
    snapshot_version: view.snapshot_version,
    report_id: finding?.report_id ?? null,
    marker_code: finding?.source_type === "measured" ? finding.id.split(":").pop() : null,
    risk_code: finding?.source_type === "predicted_risk" ? finding.id.replace(/^risk:/, "") : null,
    displayed_sections: shownSections(finding),
  };
  return base;
}

export function ExploreJourney({
  view,
  loading,
  error,
  name,
  place,
  categoryId,
  findingId,
  onPlace,
  onAsk,
  categoryChat,
  onCategoryAsk,
}: {
  view: HealthView | null | undefined;
  loading: boolean;
  error: boolean;
  name: string | null;
  place: Place;
  categoryId: string | null;
  findingId: string | null;
  onPlace: (place: Place, categoryId?: string | null, findingId?: string | null) => void;
  onAsk: (text: string, contextRef: ContextRef) => void;
  categoryChat?: { messages: ChatMessage[]; loading: boolean; error: string | null };
  onCategoryAsk?: (text: string) => void;
}) {
  const [openFinding, setOpenFinding] = useState<string | null>(null);
  if (place === "home") {
    return (
      <section className="cura-home">
        <p className="eyebrow">CURA</p>
        <h1>{name ? `Hello, ${name}` : "Hello"}</h1>
        <p className="lede">CURA helps you understand your body, your blood results and your Bio-AI assessment in plain language.</p>
        <button type="button" className="primary-action" onClick={() => onPlace("overview")}>Explore my health</button>
        <div className="starter-row">
          {["Help me understand a blood test", "What is a Bio-AI assessment?", "How does sleep affect energy?"].map((text) => (
            <button key={text} type="button" className="starter" onClick={() => onAsk(text, { type: "bio_ai_report", source: "supershyft", entry_point: "health_area" })}>{text}</button>
          ))}
        </div>
        {loading ? <p className="muted" aria-live="polite">Preparing your health view…</p> : null}
        {error ? <p role="alert">Your health information is not available right now. You can still ask a general question.</p> : null}
        {view?.state === "unavailable" ? <p>No health reports are available yet.</p> : null}
      </section>
    );
  }

  if (loading) return <section className="cura-home" aria-busy="true"><p className="muted">Preparing your health view…</p></section>;
  if (!view || error) {
    return (
      <section className="cura-home" role="alert">
        <h1>Health information is unavailable</h1>
        <p>You can still ask a general question below.</p>
        <button type="button" className="text-button" onClick={() => onPlace("home")}>Back home</button>
      </section>
    );
  }

  const categories = (view.overview?.categories || []).filter((card) => (card.measured?.total || 0) + (card.risks?.assessed || 0) > 0);
  const detail: CategoryDetail | undefined = categoryId ? view.categories?.[categoryId] : undefined;
  const finding = findingId ? view.findings?.[findingId] : undefined;

  if (place === "overview") {
    return (
      <section className="cura-overview">
        <h1>My health</h1>
        <p>There's a story behind every health result. Let's explore yours.</p>
        <p className="muted">
          {view.overview?.provenance?.blood_report_date ? `Blood results from ${friendlyDate(view.overview.provenance.blood_report_date)}. ` : ""}
          {view.overview?.provenance?.bio_ai_report_date ? `Bio-AI assessment from ${friendlyDate(view.overview.provenance.bio_ai_report_date)}.` : ""}
        </p>
        {view.metabolic_age_insight ? (
          <button
            type="button"
            className="metabolic-age-card"
            onClick={() => onAsk("What does my metabolic age say about my health?", { type: "bio_ai_report", source: "supershyft", entry_point: "health_area" })}
          >
            <strong>Your age, beyond birthdays.</strong>
            <span>There's the age on your birthday cake, and then there's what your health data says about your metabolism.</span>
            <span className="metabolic-age-values">
              <span><b>{view.metabolic_age_insight.actual_age_years}</b> Actual age</span>
              <span><b>{view.metabolic_age_insight.metabolic_age_years}</b> Metabolic age</span>
            </span>
            <span className="metabolic-age-bar" aria-hidden="true">
              <span style={{ width: `${Math.max(8, Math.min(100, (view.metabolic_age_insight.actual_age_years / Math.max(view.metabolic_age_insight.actual_age_years, view.metabolic_age_insight.metabolic_age_years)) * 100))}%` }} />
              <span style={{ width: `${Math.max(8, Math.min(100, (view.metabolic_age_insight.metabolic_age_years / Math.max(view.metabolic_age_insight.actual_age_years, view.metabolic_age_insight.metabolic_age_years)) * 100))}%` }} />
            </span>
            <span>{view.metabolic_age_insight.comparison}</span>
            <span className="metabolic-age-cta">What's behind my metabolic age?</span>
            {friendlyDate(view.metabolic_age_insight.assessed_on) ? <span className="muted">Bio-AI assessment from {friendlyDate(view.metabolic_age_insight.assessed_on)}.</span> : null}
          </button>
        ) : null}
        {categories.length === 0 ? <p>No blood results or Bio-AI assessments are available yet.</p> : null}
        <div className="health-grid">
          {categories.map((card) => {
            const highlight = (card as { risk_highlight?: string | null }).risk_highlight;
            const riskLabel = highlight === "very_high" ? "Very high predicted risk" : highlight === "increased" ? "Increased predicted risk" : "";
            return (
            <button key={card.id} type="button" className="health-card" data-risk={highlight || undefined} onClick={() => onPlace("category", card.id)}>
              <span className="health-card-title">
                {card.icon ? <span className="explore-card-icon"><LineIcon name={card.icon} size={20} /></span> : null}
                <strong>{card.name}</strong>
                <span className="result-row-chevron" aria-hidden="true">›</span>
              </span>
              <span>{card.description || card.summary}</span>
              <span className="muted">
                {[
                  card.measured?.total ? plural(card.measured.total, "blood test", "blood tests") : "",
                  card.risks?.assessed ? plural(card.risks.assessed, "Bio-AI assessment", "Bio-AI assessments") : "",
                ].filter(Boolean).join(" · ")}
              </span>
              {riskLabel ? <span className="health-card-risk">{riskLabel}</span> : null}
            </button>
            );
          })}
        </div>
        {categories.some((card) => (card as { risk_highlight?: string | null }).risk_highlight) ? (
          <p className="muted health-risk-note">Highlighted areas have an increased or very high predicted risk in your Bio-AI assessment.</p>
        ) : null}
      </section>
    );
  }

  if (place === "category" && detail) {
    const measured = (detail.findings || []).filter((item) => item.source_type === "measured");
    const risks = (detail.findings || []).filter((item) => item.source_type === "predicted_risk");
    const pointers = BODY_AT_WORK[detail.id] || [];
    const askHere = (text: string) => (onCategoryAsk ? onCategoryAsk(text) : onAsk(text, refFor(view, categoryId)));
    const summary = detail.insight || detail.summary;
    return (
      <section className="cura-category">
        <h1>{detail.name}</h1>
        {pointers.length ? (
          <>
            <h2>Your body at work</h2>
            <ul className="body-at-work">
              {pointers.map((line) => <li key={line}>{line}</li>)}
            </ul>
          </>
        ) : null}
        {summary ? (
          <>
            <h2>What your results say</h2>
            <p>{summary}</p>
          </>
        ) : null}
        {measured.length ? <h2>From your blood report</h2> : null}
        <ul className="finding-list">
          {measured.map((item) => (
            <li key={item.id}>
              <ResultRow
                title={friendlyBiomarkerName(item.name)}
                value={item.value != null ? `${item.value}${item.unit ? " " + item.unit : ""}` : null}
                note={item.status_label}
                open={openFinding === item.id}
                onOpen={() => setOpenFinding(openFinding === item.id ? null : item.id)}
              />
              {openFinding === item.id ? <InlineFinding finding={item} siblings={detail.findings || []} /> : null}
            </li>
          ))}
        </ul>
        {risks.length ? <h2>From your Bio-AI assessment</h2> : null}
        <ul className="finding-list">
          {risks.map((item) => (
            <li key={item.id} data-risk={/very high/i.test(item.classification || "") ? "very_high" : /increased/i.test(item.classification || "") ? "increased" : undefined}>
              <ResultRow
                title={item.name}
                value={[item.score != null ? String(item.score) : "", cap(item.classification)].filter(Boolean).join(" · ") || null}
                note="Predicted risk"
                open={openFinding === item.id}
                onOpen={() => setOpenFinding(openFinding === item.id ? null : item.id)}
              />
              {openFinding === item.id ? <InlineFinding finding={item} siblings={detail.findings || []} /> : null}
            </li>
          ))}
        </ul>
        <QuestionList prompts={questions(view, categoryId)} onAsk={askHere} />
        {categoryChat && onCategoryAsk ? (
          <div className="category-chat">
            <MessageList
              messages={categoryChat.messages}
              onFollowUp={askHere}
              onAskContext={(text) => askHere(text)}
              onFeedback={() => undefined}
            />
            {categoryChat.error ? <p role="alert">{categoryChat.error} <button type="button" className="text-button" onClick={() => { const asked = [...categoryChat.messages].reverse().find((item) => item.role === "user"); if (asked) onCategoryAsk(asked.content); }}>Try again</button></p> : null}
            <Composer
              disabled={categoryChat.loading}
              onSend={(text) => onCategoryAsk(text)}
              placeholder={CATEGORY_PLACEHOLDER[detail.id] || "Ask anything about this part of your health..."}
              voiceEnabled
            />
          </div>
        ) : null}
      </section>
    );
  }

  if (place === "marker" && finding) {
    const edu = finding.education as Edu | null | undefined;
    const related = (view.related_keys?.[finding.id] || []).map((key) => Object.values(view.findings || {}).find((item) => item.id.endsWith(key))).filter(Boolean) as Finding[];
    return (
      <article className="cura-detail">
        <p className="eyebrow">Measured blood result</p>
        <h1>{edu?.name || finding.name}</h1>
        {finding.medical_name ? <p className="muted">{finding.medical_name}</p> : null}
        {edu?.what_it_is ? <p>{edu.what_it_is}</p> : null}
        <section className="result-card">
          {finding.value != null ? (
            <>
              <p><strong>{finding.value}</strong> {finding.unit || ""}</p>
              <p>{finding.status_label}</p>
            </>
          ) : (
            <p><strong>No value was reported for this test</strong></p>
          )}
          <p className="muted">{friendlyDate(finding.measured_on) || "Collection date unavailable"}</p>
          <RangeNote finding={finding} />
        </section>
        {edu?.body && edu.body !== edu.what_it_is ? (
          <>
            <h2>What happens inside my body?</h2>
            <p>{edu.body}</p>
          </>
        ) : null}
        {finding.value != null ? (
          <>
            <h2>What does my result mean?</h2>
            <p>{resultMeaning(finding, edu)}</p>
          </>
        ) : null}
        {edu?.why_it_matters && edu.why_it_matters !== edu.body ? (
          <>
            <h2>Why is this test important?</h2>
            <p>{edu.why_it_matters}</p>
          </>
        ) : null}
        {edu?.limitations ? (
          <>
            <h2>What this result cannot tell you</h2>
            <p>{edu.limitations}</p>
          </>
        ) : null}
        {finding.previous_value != null ? (
          <>
            <h2>Previous result</h2>
            <p>{finding.previous_value} {finding.unit || ""}{finding.previous_on ? ` on ${friendlyDate(finding.previous_on)}` : ""}. It is shown because it is the same measurement.</p>
          </>
        ) : null}
        {related.length > 0 ? (
          <>
            <h2>Related results</h2>
            <ul>{related.map((item) => <li key={item.id}><button type="button" onClick={() => onPlace("marker", categoryId, item.id)}>{item.name}</button></li>)}</ul>
          </>
        ) : null}
        <QuestionList prompts={questions(view, categoryId)} onAsk={(text) => onAsk(text, refFor(view, categoryId, finding))} />
      </article>
    );
  }

  if (place === "risk" && finding) {
    const edu = finding.education as Edu | null | undefined;
    const measuredHere = (detail?.findings || []).filter((item) => item.source_type === "measured" && item.value != null).slice(0, 6);
    return (
      <article className="cura-detail">
        <p className="eyebrow">Predicted Bio-AI assessment</p>
        <h1>{finding.name}</h1>
        {edu?.what_it_is ? <p>{edu.what_it_is}</p> : null}
        <section className="result-card">
          <p><strong>{cap(finding.classification || finding.status_label)}</strong>{finding.score != null ? ` · score ${finding.score} out of 100` : ""}</p>
          <p className="muted">A predicted risk from your Bio-AI report, not a diagnosis. {friendlyDate(finding.measured_on) || "Assessment date unavailable"}</p>
        </section>
        {edu?.body && edu.body !== edu.what_it_is ? (
          <>
            <h2>What happens inside my body?</h2>
            <p>{edu.body}</p>
          </>
        ) : null}
        {edu?.why_it_matters ? (
          <>
            <h2>Why does this matter?</h2>
            <p>{edu.why_it_matters}</p>
          </>
        ) : null}
        {edu?.limitations ? (
          <>
            <h2>What this prediction cannot tell you</h2>
            <p>{edu.limitations}</p>
          </>
        ) : null}
        {measuredHere.length > 0 ? (
          <>
            <h2>Measured results in this area</h2>
            <p className="muted">These come from your blood report. They are measured, not predicted. The Bio-AI score above is a prediction and does not replace them.</p>
            <ul className="finding-list">
              {measuredHere.map((item) => (
                <ResultRow
                  key={item.id}
                  title={item.name}
                  value={item.value != null ? `${item.value}${item.unit ? " " + item.unit : ""}` : null}
                  note={item.status_label}
                  onOpen={() => onPlace("marker", categoryId, item.id)}
                />
              ))}
            </ul>
          </>
        ) : null}
        <button type="button" className="primary-action" onClick={() => onAsk(`What does my ${finding.name} assessment mean for me?`, refFor(view, categoryId, finding))}>Ask CURA about this</button>
      </article>
    );
  }

  return (
    <section className="cura-home">
      <p>That part of your health is not in the current view.</p>
      <button type="button" className="text-button" onClick={() => onPlace("overview")}>My health</button>
    </section>
  );
}

function resultMeaning(finding: Finding, edu: Edu | null | undefined): string {
  if (finding.status === "above_range") return edu?.if_high || "An explanation for a high result is not available yet.";
  if (finding.status === "below_range") return edu?.if_low || "An explanation for a low result is not available yet.";
  if (finding.status === "within_range") return edu?.next_step || "An explanation for a result inside the range is not available yet.";
  return "This result does not have a numerical interpretation.";
}

function RangeNote({ finding }: { finding: Finding }) {
  const low = finding.reference_low;
  const high = finding.reference_high;
  const value = finding.value;
  const unit = finding.unit || "";
  if (value == null) return null;
  if (low != null && high != null && high > low) {
    // The bar runs a little beyond the range on both sides, so a result outside the range is drawn outside the band.
    const span = high - low;
    const min = Math.min(low - span * 0.5, value - span * 0.1);
    const max = Math.max(high + span * 0.5, value + span * 0.1);
    const at = (n: number) => `${(((n - min) / (max - min)) * 100).toFixed(1)}%`;
    const relation = value < low ? "below" : value > high ? "above" : "within";
    const words = { below: "below the range on your report", above: "above the range on your report", within: "within the range on your report" }[relation];
    return (
      <div className="range-viz" data-relation={relation} aria-label={`Result ${value} ${unit}, ${words}, range ${low} to ${high}`}>
        <div className="range-track">
          <span className="range-band" style={{ left: at(low), width: `${(((high - low) / (max - min)) * 100).toFixed(1)}%` }} />
          <span className="range-mark" style={{ left: at(value) }} />
        </div>
        <p className="muted">Your result is {words}: {low} to {high} {unit}</p>
      </div>
    );
  }
  if (low != null && high == null) {
    return <p className="muted">{value < low ? "Your result is below" : "Your result is at or above"} the lowest value on your report, {low} {unit}. The report gave no upper limit.</p>;
  }
  if (high != null && low == null) {
    return <p className="muted">{value > high ? "Your result is above" : "Your result is at or below"} the highest value on your report, {high} {unit}. The report gave no lower limit.</p>;
  }
  return <p className="muted">This report did not include a reference range.</p>;
}

function QuestionList({ prompts, onAsk }: { prompts: string[]; onAsk: (text: string) => void }) {
  if (prompts.length === 0) return null;
  return (
    <div className="starter-row" role="group" aria-label="Suggested questions">
      {prompts.map((text) => (
        <button key={text} type="button" className="starter" onClick={() => onAsk(text)}>{text}</button>
      ))}
    </div>
  );
}
