import { useState } from "react";
import type { ContextRef } from "../../../types/chat";
import type { BiomarkerCard, HealthStory } from "../../../types/unifiedHealth";
import { RangeBar } from "../../messages/RangeBar";
import { HealthIcon } from "../HealthIcon";
import { t } from "../../../i18n";

type Ask = (text: string, contextRef: ContextRef) => void;
const AREA_REF: ContextRef = { type: "bio_ai_report", source: "supershyft", entry_point: "health_area" };

function day(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function tone(status: string) {
  if (status === "within_range" || status === "risk_healthy") return "good";
  if (status === "no_range" || status === "no_value" || status === "risk_unknown") return "neutral";
  return "attention";
}

/** A short, generic picture of a blood vessel narrowing over time. It explains the idea and shows nothing about the member. */
function VesselDiagram() {
  const stage = (cx: number, narrow: number, label: string) => (
    <g key={label} transform={`translate(${cx} 0)`}>
      <circle cx="0" cy="48" r="38" fill="none" stroke="currentColor" strokeWidth="6" opacity="0.7" />
      <circle cx="0" cy="48" r={32 - narrow} fill="currentColor" opacity="0.12" />
      <text x="0" y="104" textAnchor="middle" fontSize="11" fill="currentColor">{label}</text>
    </g>
  );
  return (
    <figure className="story-figure">
      <svg viewBox="0 0 330 112" role="img" aria-label={t("ui.story.vessel_alt", "Three cross sections of a blood vessel, open, partly narrowed and more narrowed")}>
        {stage(55, 0, t("ui.story.vessel_open", "Open"))}
        {stage(165, 12, t("ui.story.vessel_part", "Narrowing"))}
        {stage(275, 22, t("ui.story.vessel_more", "More narrowed"))}
      </svg>
      <figcaption className="muted">{t("ui.story.vessel_caption", "When too much cholesterol circulates for years, it can slowly build up in artery walls. This is a general picture, not a picture of you.")}</figcaption>
    </figure>
  );
}

function Chapter({ id, n, title, children }: { id: string; n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="story-chapter" aria-labelledby={`ch-${id}`} id={`story-${id}`}>
      <p className="eyebrow">{`${t("ui.story.chapter", "Chapter")} ${n}`}</p>
      <h3 id={`ch-${id}`}>{title}</h3>
      {children}
    </section>
  );
}

function Lead({ text }: { text?: string | null }) {
  return text ? <p className="story-lead">{text}</p> : null;
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="bio-block">
      <h5>{title}</h5>
      <ul>{items.map((x) => <li key={x}>{x}</li>)}</ul>
    </div>
  );
}

export function BiomarkerEducationCard({ card }: { card: BiomarkerCard }) {
  const [open, setOpen] = useState(false);
  const r = card.your_result;
  const d = day(r.measured_on);
  return (
    <li className="bio-card" data-tone={tone(r.status)} data-open={open}>
      <button type="button" className="bio-card-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span><strong>{card.name}</strong><span className="muted">{card.measures ? ` ${card.measures}` : ""}</span></span>
        <span className="finding-status" data-tone={tone(r.status)}>{r.status_label}</span>
      </button>
      {open ? (
        <div className="bio-card-body">
          {r.value != null ? (
            <div className="bio-yours">
              <RangeBar label={card.name} value={r.value} unit={r.unit ?? undefined} low={r.reference_low ?? undefined} high={r.reference_high ?? undefined} />
              <p className="muted">{t("ui.story.source_line", "Measured in your blood report")}{d ? `, ${d}` : ""}. {t("ui.story.range_source", "The range is your laboratory's own reference range.")}</p>
            </div>
          ) : null}
          {card.body_function ? <div className="bio-block"><h5>{t("ui.story.does", "What does it do in your body?")}</h5><p>{card.body_function}</p></div> : null}
          {card.why_it_matters ? <div className="bio-block"><h5>{t("ui.story.matters", "Why does it matter?")}</h5><p>{card.why_it_matters}</p></div> : null}
          {card.effects_when_low ? <div className="bio-block"><h5>{t("ui.story.when_low", "What can a low result mean?")}</h5><p>{card.effects_when_low}</p></div> : null}
          {card.effects_when_high ? <div className="bio-block"><h5>{t("ui.story.when_high", "What can a high result mean?")}</h5><p>{card.effects_when_high}</p></div> : null}
          <ListBlock title={t("ui.story.causes_low", "What can lower it?")} items={card.causes_when_low ?? []} />
          <ListBlock title={t("ui.story.causes_high", "What can raise it?")} items={card.causes_when_high ?? []} />
          <ListBlock title={t("ui.story.influences", "What influences it?")} items={card.influences ?? []} />
          <ListBlock title={t("ui.story.steps", "What may help keep it healthy?")} items={card.practical_steps ?? []} />
          {card.age_sex_note ? <p className="muted">{card.age_sex_note}</p> : null}
          {card.unit_note ? <p className="muted">{card.unit_note}</p> : null}
          <p className="muted bio-review">{card.detail_level === "basic" ? t("ui.story.basic", "Short explanation only for this test.") : t("ui.story.unreviewed", "General education, not yet reviewed by clinicians.")}</p>
        </div>
      ) : null}
    </li>
  );
}

/** The server omits empty lists from its schema defaults, so every list is made explicit once here. */
function normalize(s: HealthStory) {
  return {
    ...s,
    biomarker_education: s.biomarker_education ?? [],
    limitations: s.limitations ?? [],
    understand_body: { ...s.understand_body, sections: s.understand_body.sections ?? [] },
    your_assessment: { ...s.your_assessment, risks: s.your_assessment.risks ?? [] },
    personal_factors: { ...s.personal_factors, measured: s.personal_factors.measured ?? [], lifestyle: s.personal_factors.lifestyle ?? [], relationships: s.personal_factors.relationships ?? [], missing: s.personal_factors.missing ?? [] },
    improvement_plan: { ...s.improvement_plan, actions: s.improvement_plan.actions ?? [] },
    next_steps: { ...s.next_steps, monitoring: s.next_steps.monitoring ?? [], suggested_questions: s.next_steps.suggested_questions ?? [], related_categories: s.next_steps.related_categories ?? [] },
  };
}

export function HealthStoryView({ story: raw, onAsk, onOpenCategory, onShowSummary }: { story: HealthStory; onAsk: Ask; onOpenCategory?: (id: string) => void; onShowSummary?: () => void }) {
  const story = normalize(raw);
  const [question, setQuestion] = useState("");
  const [openRisk, setOpenRisk] = useState<string | null>(null);
  const [openSource, setOpenSource] = useState<string | null>(null);
  const a = story.your_assessment;
  const pf = story.personal_factors;
  const ub = story.understand_body;
  const ns = story.next_steps;
  const nav = [
    ["understand_body", t("ui.story.nav1", "Your body")],
    ...(a.available ? [["assessment", t("ui.story.nav2", "Your assessment")]] : []),
    ["personal", t("ui.story.nav3", "What influences it")],
    ...(story.biomarker_education.length ? [["biomarkers", t("ui.story.nav4", "Your tests")]] : []),
    ["plan", t("ui.story.nav5", "Your plan")],
    ["next", t("ui.story.nav6", "Next steps")],
  ];
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = question.trim();
    if (!text) return;
    onAsk(text, AREA_REF);
    setQuestion("");
  };
  return (
    <article className="overview unified category-screen story" data-status={story.status} aria-labelledby="story-title">
      <header>
        <span className="health-card-icon"><HealthIcon name={story.icon} /></span>
        <div>
          <h2 id="story-title" tabIndex={-1} ref={(el) => el?.focus()}>{story.headline}</h2>
          <p className="health-card-status" data-status={story.status}>{story.status_label}</p>
        </div>
      </header>
      {story.metadata.data_state !== "complete" ? <p className="overview-note" role="note">{t("ui.story.partial", "Some information for this area is missing, so parts of this story are shorter. Each section says what is missing.")}</p> : null}
      <nav className="story-nav" aria-label={t("ui.story.nav", "Parts of this story")}>
        {nav.map(([id, label]) => <a key={id} href={`#story-${id}`}>{label}</a>)}
      </nav>

      <Chapter id="understand_body" n={1} title={ub.title || t("ui.story.c1", "Understand your body")}>
        {ub.available ? (
          <>
            {story.category_id === "heart_circulation" ? <VesselDiagram /> : null}
            {ub.sections.map((s, i) => (
              <details key={s.heading} open={i === 0} className="story-section">
                <summary>{s.heading}</summary>
                <p>{s.text}</p>
              </details>
            ))}
            {ub.report_scope ? <p className="overview-note" role="note">{ub.report_scope}</p> : null}
          </>
        ) : <p className="muted">{ub.report_scope}</p>}
      </Chapter>

      <Chapter id="assessment" n={2} title={t("ui.story.c2", "What your Bio-AI assessment says")}>
        {a.available ? (
          <>
            <Lead text={a.lead} />
            <ul className="finding-list">
              {a.risks.map((r) => (
                <li key={r.finding_id} className="finding-row" data-kind="predicted_risk">
                  <div className="finding-main">
                    <strong>{r.name}</strong>
                    <span className="finding-kind">{`${t("ui.unified.predicted", "Predicted")}${r.assessed_on ? `, ${t("ui.unified.bio_report", "Bio-AI report")} ${day(r.assessed_on)}` : ""}`}</span>
                  </div>
                  <div className="finding-side">
                    <span className="finding-status" data-tone="attention">{r.classification}</span>
                    {r.score != null ? <span className="muted finding-value">{`${t("ui.story.score", "Score")} ${r.score} ${t("ui.story.of100", "out of 100")}`}</span> : null}
                  </div>
                  <button type="button" className="expand-button" aria-expanded={openRisk === r.finding_id} onClick={() => setOpenRisk(openRisk === r.finding_id ? null : r.finding_id)}>
                    {t("ui.story.risk_more", "What this does and does not mean")}
                  </button>
                  {openRisk === r.finding_id ? (
                    <div className="bio-card-body">
                      <p>{r.what_it_means}</p>
                      <ListBlock title={t("ui.story.not_mean", "What it does not mean")} items={r.what_it_does_not_mean} />
                      <ListBlock title={t("ui.story.limits", "Limits")} items={r.limitations} />
                      {r.contributing_factors?.length ? <ListBlock title={t("ui.story.factors", "Factors listed by your assessment")} items={r.contributing_factors} /> : null}
                      <p className="muted">{r.contributing_note}</p>
                      <p className="muted">{r.model_name ? `${r.model_name} ${r.model_version ?? ""}` : t("ui.story.model_unknown", "Model name and version: not stated in your report.")}</p>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        ) : <p className="muted">{a.note || t("ui.story.no_risk", "No Bio-AI risk was assessed for this area.")}</p>}
        {a.available && a.note ? <p className="muted">{a.note}</p> : null}
      </Chapter>

      <Chapter id="personal" n={3} title={t("ui.story.c3", "What could be influencing your health?")}>
        <Lead text={pf.lead} />
        <h4>{t("ui.story.measured", "Measured in your blood report")}</h4>
        {pf.measured.length ? (
          <ul className="finding-list">
            {pf.measured.map((m) => (
              <li key={m.finding.id} className="finding-row" data-tone={tone(m.finding.status)} data-kind="measured">
                <div className="finding-main">
                  <strong>{m.finding.name}</strong>
                  {m.why_relevant ? <span className="muted">{m.why_relevant}</span> : null}
                  <button type="button" className="link-button" aria-expanded={openSource === m.finding.id} onClick={() => setOpenSource(openSource === m.finding.id ? null : m.finding.id)}>
                    {t("ui.story.show_source", "Show source")}
                  </button>
                  {openSource === m.finding.id ? <span className="muted">{`${m.source}${m.finding.measured_on ? `, ${day(m.finding.measured_on)}` : ""}. ${t("ui.story.measured_note", "This value is exactly as printed in your report.")}`}</span> : null}
                </div>
                <div className="finding-side">
                  <span className="finding-status" data-tone={tone(m.finding.status)}>{m.finding.status_label}</span>
                  {m.finding.value != null ? <span className="muted finding-value">{`${m.finding.value}${m.finding.unit ? ` ${m.finding.unit}` : ""}`}</span> : null}
                  {m.finding.reference_low != null || m.finding.reference_high != null ? <span className="muted">{`${t("ui.story.lab_range", "Laboratory range")} ${m.finding.reference_low ?? ""} to ${m.finding.reference_high ?? ""}`}</span> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="muted">{t("ui.story.no_blood", "No blood results for this area are available.")}</p>}
        {pf.within_range_count > 0 ? <p className="muted">{`${pf.within_range_count} ${t("ui.story.others_within", "other results are within range.")}`}</p> : null}

        <h4>{t("ui.story.reported", "Reported by you")}</h4>
        <ul className="lifestyle-list">
          {pf.lifestyle.map((x) => (
            <li key={x.key} data-state={x.state}>
              <strong>{x.label}</strong>
              <span>{x.state === "reported" ? x.value : t("ui.story.not_reported", "Not reported")}</span>
              {x.state === "reported" ? <span className="muted">{`${x.source}${x.recorded_at ? `, ${day(x.recorded_at)}` : ""}. ${t("ui.story.self_reported", "Not independently verified.")}`}</span> : null}
            </li>
          ))}
        </ul>

        {pf.relationships.length ? (
          <>
            <h4>{t("ui.story.how_connect", "How these fit together")}</h4>
            <ul className="relationship-list">
              {pf.relationships.map((r) => (
                <li key={r.relationship_id} data-type={r.relationship_type}>
                  <p>{r.text}</p>
                  <p className="muted">{t("ui.story.rule_based", "Based on a general rule, not on a clinical review of you. It does not say one thing caused another.")}</p>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {pf.missing.length ? (
          <details className="story-section">
            <summary>{t("ui.story.missing", "What we do not know")}</summary>
            <ul>{pf.missing.map((x) => <li key={x}>{x}</li>)}</ul>
          </details>
        ) : null}
      </Chapter>

      {story.biomarker_education.length ? (
        <Chapter id="biomarkers" n={4} title={t("ui.story.c4", "Get to know your biomarkers")}>
          <p className="muted">{t("ui.story.tap", "Tap a test to learn what it does and where your result sits.")}</p>
          <ul className="bio-list">{story.biomarker_education.map((c) => <BiomarkerEducationCard key={c.finding_id} card={c} />)}</ul>
        </Chapter>
      ) : null}

      <Chapter id="plan" n={story.biomarker_education.length ? 5 : 4} title={t("ui.story.c5", "Ways to support your health")}>
        <Lead text={story.improvement_plan.lead} />
        {story.improvement_plan.actions.length ? (
          <ul className="action-list">
            {story.improvement_plan.actions.map((x) => (
              <li key={x.action_id}>
                <span className="priority-icon"><HealthIcon name="check" size={20} /></span>
                <div>
                  <strong>{x.title}</strong>
                  <p>{x.what}</p>
                  <p className="muted">{`${t("ui.story.why", "Why")}: ${x.why}`}</p>
                  {x.safety_note ? <p className="muted">{x.safety_note}</p> : null}
                </div>
              </li>
            ))}
          </ul>
        ) : <p className="muted">{t("ui.story.no_actions", "There are no specific steps to suggest from your results.")}</p>}
        <p className="muted">{story.improvement_plan.note}</p>
      </Chapter>

      <Chapter id="next" n={story.biomarker_education.length ? 6 : 5} title={t("ui.story.c6", "Your next steps")}>
        {ns.monitoring.length ? <ul>{ns.monitoring.map((x) => <li key={x}>{x}</li>)}</ul> : null}
        {ns.suggested_questions.length ? (
          <div className="follow-list">
            {ns.suggested_questions.map((q) => <button key={q} type="button" onClick={() => onAsk(q, AREA_REF)}>{q}<span aria-hidden="true">↗</span></button>)}
          </div>
        ) : null}
        <form className="story-ask" onSubmit={submit}>
          <label htmlFor="story-ask-input" className="muted">{t("ui.story.ask_label", "Ask CURA about this area")}</label>
          <div>
            <input id="story-ask-input" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={t("ui.story.ask_ph", "Type your question")} />
            <button type="submit" disabled={!question.trim()}>{t("ui.story.ask", "Ask")}</button>
          </div>
        </form>
        {ns.related_categories.length && onOpenCategory ? (
          <>
            <h4>{t("ui.story.related", "Related areas")}</h4>
            <div className="related-list">
              {ns.related_categories.map((c) => (
                <button key={c.id} type="button" onClick={() => onOpenCategory(c.id)}><HealthIcon name={c.icon} size={18} /> {c.name}<span className="muted"> {c.status_label}</span></button>
              ))}
            </div>
          </>
        ) : null}
      </Chapter>

      <footer className="story-foot muted">
        {story.limitations.map((x) => <p key={x}>{x}</p>)}
        <p>{story.disclaimer}</p>
        <p>{`${t("ui.story.kb", "Education text version")} ${story.metadata.knowledge_version}. ${story.metadata.generation === "model" ? t("ui.story.worded", "Opening lines were written by an AI model from the facts above.") : t("ui.story.rules", "Every line here comes from your reports and approved text.")}`}</p>
        {onShowSummary ? <button type="button" className="link-button" onClick={onShowSummary}>{t("ui.story.summary_view", "Show the short summary instead")}</button> : null}
      </footer>
    </article>
  );
}
