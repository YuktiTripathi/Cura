import { useState } from "react";
import { TrendChart } from "../components/marker/TrendChart";
import { DEMO_LABEL, followups, hba1cHistory, markers, meals, reportRows, risks, type DemoMarker } from "./demoData";
import "./prototype.css";

type Screen = "plan" | "companion" | "report" | "nutrition";

export function CompanionPrototype() {
  const [screen, setScreen] = useState<Screen>("companion");
  return (
    <div className="companion-proto">
      <div className="cp-wrap">
        <div className="cp-kicker">
          <span className="cp-badge">{DEMO_LABEL}</span>
          <a className="cp-back" href="./">Back to CURA chat</a>
        </div>
        <header className="cp-hero">
          <h1>Your health, in plain language</h1>
          <p>A calm companion view for measurements, estimates, and the next question. This screen uses demo numbers only.</p>
        </header>
        <nav className="cp-nav" aria-label="Prototype screens">
          {(
            [
              ["companion", "Answer"],
              ["report", "Blood report"],
              ["nutrition", "Meals"],
              ["plan", "Design notes"],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" aria-selected={screen === id} onClick={() => setScreen(id)}>
              {label}
            </button>
          ))}
        </nav>
        {screen === "companion" && <CompanionScreen />}
        {screen === "report" && <ReportScreen />}
        {screen === "nutrition" && <NutritionScreen />}
        {screen === "plan" && <PlanScreen />}
      </div>
    </div>
  );
}

function CompanionScreen() {
  return (
    <div className="cp-grid">
      {markers.map((marker) => (
        <MarkerCard key={marker.name} marker={marker} />
      ))}
      {risks.map((risk) => (
        <article key={risk.name} className="cp-card cp-estimate">
          <header>
            <h3>{risk.name}</h3>
            <span className="cp-pill">Estimate</span>
          </header>
          <p className="cp-value">{risk.score}<span>/100</span></p>
          <p className="cp-meta">{risk.band} · Bio-AI · {risk.date}</p>
          <Explain plain={risk.plain} detail={risk.detail} />
        </article>
      ))}
      <article className="cp-card" style={{ gridColumn: "1 / -1" }}>
        <h3>HbA1c across demo reports</h3>
        <TrendChart label="HbA1c" unit="%" points={hba1cHistory} low={4} high={5.6} />
        <section>
          <h3>Ask next</h3>
          <div className="cp-follow">
            {followups.map((q) => (
              <button key={q} type="button" className="cp-chip">{q}</button>
            ))}
          </div>
        </section>
      </article>
    </div>
  );
}

function MarkerCard({ marker }: { marker: DemoMarker }) {
  const out = marker.status === "above range";
  return (
    <article className="cp-card">
      <header>
        <h3>{marker.name}</h3>
        <span className="cp-meta">{marker.date}</span>
      </header>
      <p className="cp-value">{marker.value}<span>{marker.unit}</span></p>
      <p className={`cp-status ${out ? "out" : "in"}`}><span className="cp-dot" aria-hidden="true" />{marker.status}</p>
      <p className="cp-meta">{marker.source}</p>
      <Explain plain={marker.plain} detail={marker.detail} />
    </article>
  );
}

function Explain({ plain, detail }: { plain: string; detail: string }) {
  const [mode, setMode] = useState<"simple" | "more" | null>("simple");
  return (
    <>
      <div className="cp-actions">
        <button type="button" onClick={() => setMode("simple")}>Explain simply</button>
        <button type="button" onClick={() => setMode("more")}>More details</button>
      </div>
      {mode ? <p className="cp-explain">{mode === "simple" ? plain : detail}</p> : null}
    </>
  );
}

function ReportScreen() {
  return (
    <article className="cp-card">
      <header>
        <h2>Blood report · 6 Sep 2026</h2>
        <span className="cp-meta">3 in range · 1 above range</span>
      </header>
      <table className="cp-table">
        <thead>
          <tr><th>Measurement</th><th>Result</th><th>Status</th></tr>
        </thead>
        <tbody>
          {reportRows.map((row) => (
            <tr key={row.name}>
              <td>{row.name}</td>
              <td>{row.value}</td>
              <td>{row.flag}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="cp-note">LDL is the only value above the range printed on this demo report. Nothing here is copied from a live record.</p>
    </article>
  );
}

function NutritionScreen() {
  const max = Math.max(...meals.map((m) => m.kcal));
  const total = meals.reduce((sum, meal) => sum + meal.kcal, 0);
  return (
    <article className="cp-card">
      <header>
        <h2>Today’s meals</h2>
        <span className="cp-meta">{total} kcal logged</span>
      </header>
      {meals.map((meal) => (
        <div className="cp-meal" key={meal.name}>
          <span>{meal.name}</span>
          <div className="cp-bar" aria-hidden="true"><span style={{ width: `${(meal.kcal / max) * 100}%` }} /></div>
          <span>{meal.kcal}</span>
        </div>
      ))}
      <p className="cp-note">Meal bars are a visualization of the demo log. They do not change nutrition records.</p>
    </article>
  );
}

function PlanScreen() {
  return (
    <div className="cp-plan">
      <section className="cp-card">
        <h2>What stays</h2>
        <ul>
          <li>FastAPI chat, streaming, documents, nutrition, and auth stay on the existing pages.</li>
          <li>This prototype is opened with <code>?prototype=1</code> and does not call the API.</li>
          <li>Clinical answers still come from the current grounding path when you return to chat.</li>
        </ul>
      </section>
      <section className="cp-card">
        <h2>What this view adds</h2>
        <ul>
          <li>Measurement cards keep value, unit, in-range status, source, and date together.</li>
          <li>Bio-AI cards are labeled Estimate and stay separate from blood results.</li>
          <li>Trends reuse the existing chart and only plot the demo series.</li>
          <li>Explain simply and More details expand locally. Suggested questions are visible, not sent.</li>
        </ul>
      </section>
      <section className="cp-card">
        <h2>Migration, after review</h2>
        <ul>
          <li>Map these cards onto the existing presented-answer findings instead of a second data model.</li>
          <li>Keep the chat composer, sidebar, and document review where they are.</li>
          <li>Ship one answer layout first, then the report and meal views.</li>
        </ul>
      </section>
    </div>
  );
}
