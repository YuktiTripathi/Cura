import { useState } from "react";
import type { ContextRef } from "../../types/chat";
import type { CategoryCard, CategoryDetail, EducationNote, Finding } from "../../types/unifiedHealth";
import { useHealthCategory, useHealthOverview } from "../../hooks/useHealthOverview";
import { HealthIcon } from "./HealthIcon";
import { t } from "../../i18n";

const AREA_REF: ContextRef = { type: "bio_ai_report", source: "supershyft", entry_point: "health_area" };
type Ask = (text: string, contextRef: ContextRef) => void;

function formatValue(f: Finding) {
  if (f.value == null) return "";
  return `${f.value}${f.unit ? ` ${f.unit}` : ""}`;
}

function formatDay(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** The raw Bio-AI score, kept inspectable. The scale is shown only once it is documented, so none is invented here. */
function ScoreDetails({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  if (f.score == null) return null;
  return (
    <div className="about-test">
      <button type="button" className="expand-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? t("ui.unified.hide_score", "Hide the score") : t("ui.unified.view_score", "View the score")}
      </button>
      {open ? (
        <ul>
          <li><strong>{t("ui.unified.score", "Score")}</strong><p>{f.score}</p></li>
          {f.classification ? <li><strong>{t("ui.unified.report_category", "Category in the report")}</strong><p>{f.classification}</p></li> : null}
          <li><strong>{t("ui.unified.scale", "Scale")}</strong><p>{t("ui.unified.scale_missing", "The scale for this score is not documented in this app yet.")}</p></li>
          <li><strong>{t("ui.unified.limits", "What to keep in mind")}</strong><p>{t("ui.unified.limits_text", "This is a model estimate, not a diagnosis. Do not read the score as a percentage chance of having the condition.")}</p></li>
        </ul>
      ) : null}
    </div>
  );
}

function rangeText(f: Finding) {
  const { reference_low: lo, reference_high: hi } = f;
  if (lo != null && hi != null) return `${lo} to ${hi}`;
  if (hi != null) return `up to ${hi}`;
  if (lo != null) return `${lo} or more`;
  return "";
}

/** Reviewed, general explanation of a test. Which direction applies comes from the report's own range. */
function AboutTest({ note, status }: { note: EducationNote; status: Finding["status"] }) {
  const [open, setOpen] = useState(false);
  const high = status === "above_range" || status === "critical";
  const low = status === "below_range";
  const rows: Array<[string, string]> = [["What it is", note.what_it_is]];
  if (high && note.if_high) rows.push(["If higher than the range", note.if_high]);
  else if (low && note.if_low) rows.push(["If lower than the range", note.if_low]);
  else {
    if (note.if_high) rows.push(["If higher than the range", note.if_high]);
    if (note.if_low) rows.push(["If lower than the range", note.if_low]);
  }
  if (note.next_step) rows.push(["What to do next", note.next_step]);
  return (
    <div className="about-test">
      <button type="button" className="expand-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? t("ui.unified.hide_about", "Hide details") : t("ui.unified.about_test", "About this test")}
      </button>
      {open ? (
        <ul>
          {rows.map(([label, text]) => (
            <li key={label}><strong>{label}</strong><p>{text}</p></li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** One row for either kind of finding. A subtle label says which kind, so they sit in one list. */
export function FindingRow({ f }: { f: Finding }) {
  const tone = f.status === "within_range" || f.status === "risk_healthy" ? "good" : f.status === "no_range" || f.status === "no_value" || f.status === "risk_unknown" ? "neutral" : "attention";
  const day = formatDay(f.measured_on);
  const kind = f.source_type === "predicted_risk"
    ? `${t("ui.unified.predicted", "Predicted")}${day ? `, ${t("ui.unified.bio_report", "Bio-AI report")} ${day}` : ""}`
    : `${t("ui.unified.measured", "Measured")}${day ? `, ${t("ui.unified.blood_report", "blood report")} ${day}` : ""}`;
  return (
    <li className="finding-row" data-tone={tone} data-kind={f.source_type}>
      <div className="finding-main">
        <strong>{f.name}</strong>
        {f.medical_name ? <span className="muted finding-medical">{f.medical_name}</span> : null}
        {f.explain ? <span className="muted">{f.explain}</span> : null}
        <span className="finding-kind">{kind}</span>
      </div>
      <div className="finding-side">
        <span className="finding-status" data-tone={tone}>{f.status_label}</span>
        {f.source_type === "measured" && f.value != null ? (
          <span className="muted finding-value">
            {formatValue(f)}
            {rangeText(f) ? ` (${rangeText(f)})` : ""}
          </span>
        ) : null}
      </div>
      {f.source_type === "predicted_risk" ? <ScoreDetails f={f} /> : null}
      {f.education ? <AboutTest note={f.education} status={f.status} /> : null}
    </li>
  );
}

function Summary({ data }: { data: NonNullable<ReturnType<typeof useHealthOverview>["data"]> }) {
  const tot = { blood_within: 0, blood_outside: 0, blood_no_range: 0, blood_unavailable: 0, risks_assessed: 0, risks_raised: 0, metabolic_age: null, ...(data.totals ?? {}) };
  const sum = tot.blood_within + tot.blood_outside + tot.blood_no_range + tot.blood_unavailable || 1;
  const pct = (n: number) => `${(n / sum) * 100}%`;
  const sub = [
    tot.blood_no_range ? `${tot.blood_no_range} ${t("ui.unified.no_range", "results without a reference range")}` : "",
    tot.blood_unavailable ? `${tot.blood_unavailable} ${t("ui.unified.unavailable", "results unavailable")}` : "",
    tot.risks_raised ? `${tot.risks_raised} ${t("ui.unified.risks_raised", "predicted risks need attention")}` : "",
  ].filter(Boolean);
  return (
    <section className="unified-summary" aria-label={t("ui.unified.summary", "Overall assessment")}>
      <dl className="unified-numbers">
        <div><dt>{t("ui.unified.within", "Blood results within range")}</dt><dd data-tone="good">{tot.blood_within}</dd></div>
        <div><dt>{t("ui.unified.outside", "Blood results outside range")}</dt><dd data-tone="attention">{tot.blood_outside}</dd></div>
        <div><dt>{t("ui.unified.risks", "Future risks assessed")}</dt><dd>{tot.risks_assessed}</dd></div>
      </dl>
      <div className="unified-bar" role="img" aria-label={`${tot.blood_within} within range, ${tot.blood_outside} outside range`}>
        <span data-tone="good" style={{ width: pct(tot.blood_within) }} />
        <span data-tone="attention" style={{ width: pct(tot.blood_outside) }} />
        <span data-tone="neutral" style={{ width: pct(tot.blood_no_range) }} />
        <span data-tone="faint" style={{ width: pct(tot.blood_unavailable) }} />
      </div>
      {sub.length > 0 ? <p className="muted">{sub.join(" · ")}</p> : null}
      {tot.metabolic_age != null ? (
        <div className="unified-metabolic">
          <span className="muted">{t("ui.unified.metabolic_age", "Your metabolic age")}</span>
          <strong>{`${tot.metabolic_age} years`}</strong>
          <span className="muted">{t("ui.unified.metabolic_note", "An estimate of your body's metabolic health.")}</span>
        </div>
      ) : null}
    </section>
  );
}

/** The whole card opens the category. It only introduces the area: icon, name, what it means, status, counts. */
function CategoryCardView({ card, onOpen }: { card: CategoryCard; onOpen: () => void }) {
  return (
    <button type="button" className="health-card" data-status={card.status} onClick={onOpen} aria-label={`${card.name}. ${card.status_label}.`}>
      <span className="health-card-icon"><HealthIcon name={card.icon} /></span>
      <strong className="health-card-name">{card.name}</strong>
      <span className="health-card-description">{card.description}</span>
      <span className="health-card-status" data-status={card.status}>{card.status_label}</span>
      <span className="health-card-foot">
        <span className="muted">{card.count_line}</span>
        <span className="health-card-arrow" aria-hidden="true">→</span>
      </span>
    </button>
  );
}

export function HealthOverviewView({
  onAsk,
  openId,
  onOpenChange,
  onOpenReport,
}: {
  onAsk: Ask;
  openId: string | null;
  onOpenChange: (id: string | null) => void;
  /** Individual reports stay available on request. */
  onOpenReport: (kind: "blood" | "bio_ai") => void;
}) {
  const query = useHealthOverview();
  const data = query.data;
  if (openId) return <CategoryScreen id={openId} onAsk={onAsk} />;
  if (query.isLoading) return <section className="overview" aria-busy="true"><p className="muted">{t("ui.unified.loading", "Putting your health picture together…")}</p></section>;
  if (query.isError || !data) {
    return (
      <section className="overview" role="alert">
        <p>{t("ui.unified.error", "Your health overview isn't available right now.")}</p>
        <button type="button" onClick={() => void query.refetch()}>{t("ui.overview.try_again", "Try again")}</button>
      </section>
    );
  }
  const categories = data.categories ?? [];
  const priorities = data.priorities ?? [];
  const prov: { blood_report_date?: string | null; bio_ai_report_date?: string | null } = data.provenance ?? {};
  if (!data.available || categories.length === 0) {
    return <section className="overview"><h2>{t("ui.unified.title", "My Health Overview")}</h2><p>{t("ui.unified.none", "No blood results or Bio-AI report are available yet.")}</p></section>;
  }
  const dates = [prov.blood_report_date && `Blood report · ${prov.blood_report_date}`, prov.bio_ai_report_date && `Bio-AI · ${prov.bio_ai_report_date}`].filter(Boolean);
  return (
    <section className="overview unified" aria-labelledby="unified-title">
      <h2 id="unified-title">{t("ui.unified.title", "My Health Overview")}</h2>
      {dates.length > 0 ? <p className="muted">{dates.join(" | ")}</p> : null}
      {data.opening ? <p className="unified-opening">{data.opening}</p> : null}
      <Summary data={data} />
      {priorities.length > 0 ? (
        <section aria-labelledby="priorities-title">
          <h3 id="priorities-title">{t("ui.unified.priorities", "Your health priorities")}</h3>
          <ul className="priority-list">
            {priorities.map((p) => (
              <li key={p.category_id + p.title} data-tone={p.tone}>
                <span className="priority-icon"><HealthIcon name={p.icon} size={20} /></span>
                <div><strong>{p.title}</strong><p>{p.detail}</p></div>
              </li>
            ))}
          </ul>
          <button type="button" className="unified-overall" onClick={() => onAsk(data.overall_question, AREA_REF)}>{data.overall_question}</button>
        </section>
      ) : null}
      <section aria-labelledby="explore-title">
        <h3 id="explore-title">{t("ui.unified.explore", "Explore your health")}</h3>
        <p className="muted">{t("ui.unified.explore_note", "Understand what's happening inside your body and what it could mean for your future health.")}</p>
        <div className="health-grid">
          {categories.map((c) => <CategoryCardView key={c.id} card={c} onOpen={() => onOpenChange(c.id)} />)}
        </div>
      </section>
      <p className="muted unified-disclaimer">{data.disclaimer}</p>
      <p className="unified-reports muted">
        {t("ui.unified.reports", "Looking for a single report?")}{" "}
        <button type="button" className="link-button" onClick={() => onOpenReport("blood")}>{t("ui.unified.blood_report", "View blood report")}</button>{" · "}
        <button type="button" className="link-button" onClick={() => onOpenReport("bio_ai")}>{t("ui.unified.bio_report", "View Bio-AI report")}</button>
      </p>
    </section>
  );
}

function CategoryScreen({ id, onAsk }: { id: string; onAsk: Ask }) {
  const query = useHealthCategory(id);
  const [all, setAll] = useState(false);
  const d: CategoryDetail | undefined = query.data;
  if (query.isLoading) return <section className="overview" aria-busy="true"><p className="muted">{t("ui.unified.loading_area", "Opening this part of your health…")}</p></section>;
  if (query.isError || !d) {
    return (
      <section className="overview" role="alert">
        <p>{t("ui.unified.area_error", "This part of your health overview isn't available right now.")}</p>
        <button type="button" onClick={() => void query.refetch()}>{t("ui.overview.try_again", "Try again")}</button>
      </section>
    );
  }
  const findings = d.findings ?? [];
  const actions = d.actions ?? [];
  const followUps = d.follow_ups ?? [];
  const important = findings.filter((f) => f.important);
  const shown = important.length > 0 ? important : findings.slice(0, 4);
  const rest = findings.filter((f) => !shown.includes(f));
  const within = rest.filter((f) => f.status === "within_range").length;
  return (
    <article className="overview unified category-screen" data-status={d.status} aria-labelledby="category-title">
      <header>
        <span className="health-card-icon"><HealthIcon name={d.icon} /></span>
        <div>
          <h2 id="category-title" tabIndex={-1} ref={(el) => el?.focus()}>{`Your ${d.name}`}</h2>
          <p className="health-card-status" data-status={d.status}>{d.status_label}</p>
        </div>
      </header>
      {d.caveat ? <p className="overview-note" role="note">{d.caveat}</p> : null}
      {d.summary ? <p className="category-lead">{d.summary}</p> : null}
      <section aria-labelledby="cat-results">
        <h3 id="cat-results">{t("ui.unified.results_say", "What your results show")}</h3>
        <ul className="finding-list">{shown.map((f) => <FindingRow key={f.id} f={f} />)}</ul>
        {rest.length > 0 ? (
          <>
            {!all ? <p className="muted">{within > 0 ? `${within} other ${within === 1 ? "result is" : "results are"} within range.` : ""}</p> : null}
            <button type="button" className="expand-button" aria-expanded={all} onClick={() => setAll(!all)}>
              {all ? t("ui.unified.hide_all", "Hide complete assessment") : t("ui.unified.view_all", "View complete assessment")}
            </button>
            {all ? <ul className="finding-list">{rest.map((f) => <FindingRow key={f.id} f={f} />)}</ul> : null}
          </>
        ) : null}
      </section>
      <section aria-labelledby="cat-mean">
        <h3 id="cat-mean">{`${t("ui.unified.understanding", "Understanding your")} ${d.name}`}</h3>
        {d.about ? <p>{d.about}</p> : null}
        {(d.interpretation ?? []).map((line) => <p key={line}>{line}</p>)}
      </section>
      {actions.length > 0 ? (
        <section aria-labelledby="cat-next">
          <h3 id="cat-next">{t("ui.unified.next", "What you can do next")}</h3>
          <ul className="action-list">
            {actions.map((a) => (
              <li key={a.title}><span className="priority-icon"><HealthIcon name={a.icon} size={20} /></span><div><strong>{a.title}</strong>{a.detail ? <p>{a.detail}</p> : null}</div></li>
            ))}
          </ul>
        </section>
      ) : null}
      {followUps.length > 0 ? (
        <section aria-labelledby="cat-follow">
          <h3 id="cat-follow" className="eyebrow">{t("ui.unified.continue", "Continue with CURA")}</h3>
          <div className="follow-list">
            {followUps.map((q) => <button key={q} type="button" onClick={() => onAsk(q, AREA_REF)}>{q}<span aria-hidden="true">↗</span></button>)}
          </div>
        </section>
      ) : null}
    </article>
  );
}
