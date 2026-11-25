import type { ContextRef } from "../../types/chat";
import type { CategoryDetail, Finding } from "../../types/unifiedHealth";
import type { HealthView } from "../../lib/api";

type Place = "home" | "overview" | "category" | "marker" | "risk";

type Edu = NonNullable<Finding["education"]> & {
  body?: string;
  why_it_matters?: string;
  limitations?: string;
  content_source?: string;
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

function ResultRow({ title, value, note, onOpen }: { title: string; value?: string | null; note?: string | null; onOpen: () => void }) {
  return (
    <li className="result-row">
      <button type="button" className="result-row-button" onClick={onOpen}>
        <span className="result-row-main">
          <strong>{title}</strong>
          {note ? <span className="muted">{note}</span> : null}
        </span>
        {value ? <span className="result-row-value">{value}</span> : null}
        <span className="result-row-chevron" aria-hidden="true">›</span>
      </button>
    </li>
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
}) {
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
        <button type="button" className="text-button" onClick={() => onPlace("home")}>Home</button>
        <h1>My health</h1>
        <p className="muted">
          {view.overview?.provenance?.blood_report_date ? `Blood results from ${friendlyDate(view.overview.provenance.blood_report_date)}. ` : ""}
          {view.overview?.provenance?.bio_ai_report_date ? `Bio-AI assessment from ${friendlyDate(view.overview.provenance.bio_ai_report_date)}.` : ""}
        </p>
        {categories.length === 0 ? <p>No blood results or Bio-AI assessments are available yet.</p> : null}
        <div className="health-grid">
          {categories.map((card) => (
            <button key={card.id} type="button" className="health-card" onClick={() => onPlace("category", card.id)}>
              <span className="health-card-title">
                {card.icon ? <span aria-hidden="true">{card.icon}</span> : null}
                <strong>{card.name}</strong>
                <span className="result-row-chevron" aria-hidden="true">›</span>
              </span>
              <span>{card.description || card.summary}</span>
              <span className="muted">
                {card.measured?.total ? plural(card.measured.total, "blood test", "blood tests") : "No blood tests"}
                {card.risks?.assessed ? ` · ${plural(card.risks.assessed, "Bio-AI assessment", "Bio-AI assessments")}` : ""}
              </span>
            </button>
          ))}
        </div>
      </section>
    );
  }

  if (place === "category" && detail) {
    const measured = (detail.findings || []).filter((item) => item.source_type === "measured");
    const risks = (detail.findings || []).filter((item) => item.source_type === "predicted_risk");
    return (
      <section className="cura-category">
        <button type="button" className="text-button" onClick={() => onPlace("overview")}>My health</button>
        <h1>{detail.name}</h1>
        {detail.about ? <p>{detail.about}</p> : null}
        <h2>Blood results</h2>
        {measured.length === 0 ? <p className="muted">No blood results in this area.</p> : null}
        <ul className="finding-list">
          {measured.map((item) => (
            <ResultRow
              key={item.id}
              title={item.name}
              value={item.value != null ? `${item.value}${item.unit ? " " + item.unit : ""}` : null}
              note={item.status_label}
              onOpen={() => onPlace("marker", categoryId, item.id)}
            />
          ))}
        </ul>
        <h2>Bio-AI assessments</h2>
        {risks.length === 0 ? <p className="muted">No Bio-AI assessments in this area.</p> : null}
        <ul className="finding-list">
          {risks.map((item) => (
            <ResultRow
              key={item.id}
              title={item.name}
              value={cap(item.classification) || null}
              note="Predicted risk"
              onOpen={() => onPlace("risk", categoryId, item.id)}
            />
          ))}
        </ul>
        <QuestionList prompts={questions(view, categoryId)} onAsk={(text) => onAsk(text, refFor(view, categoryId))} />
      </section>
    );
  }

  if (place === "marker" && finding) {
    const edu = finding.education as Edu | null | undefined;
    const related = (view.related_keys?.[finding.id] || []).map((key) => Object.values(view.findings || {}).find((item) => item.id.endsWith(key))).filter(Boolean) as Finding[];
    return (
      <article className="cura-detail">
        <button type="button" className="text-button" onClick={() => onPlace("category", categoryId)}>Back</button>
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
            <p>{finding.previous_value} {finding.unit || ""}{finding.previous_on ? ` on ${friendlyDate(finding.previous_on)}` : ""}. Shown only because an earlier result used the same measurement.</p>
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
    return (
      <article className="cura-detail">
        <button type="button" className="text-button" onClick={() => onPlace("category", categoryId)}>Back</button>
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
