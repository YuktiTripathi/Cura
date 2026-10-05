import type { RefObject } from "react";
import type { ContextRef } from "../types/chat";
import type { MeResponse } from "../types/me";
import { StarterChips } from "./StarterChips";

export function WelcomeExperience({
  me,
  meLoading,
  onSend,
  inputRef,
}: {
  me: MeResponse | null;
  meLoading: boolean;
  onSend: (text: string, documentIds?: string[], contextRef?: ContextRef) => void;
  inputRef: RefObject<HTMLInputElement>;
}) {
  const greeting = meLoading ? "Hi 👋" : me?.greeting || "Hi there 👋";
  const personal = me?.starters?.personal || [];
  const general = me?.starters?.general || [];
  const personalUnavailable = Boolean(me?.starters?.personal_unavailable);
  const capabilities = me?.capabilities;

  return (
    <section className="welcome">
      <p className="greeting">{greeting}</p>
      <p className="welcome-lead">How can I help you understand your health better?</p>
      <p className="muted">
        I can explain your available SuperShyft reports, build your health scenario, explore nutrition,
        and answer general health questions.
      </p>
      <div className="capability-grid">
        {capabilities?.has_blood_report && (
          <button type="button" onClick={() => onSend("Show me my latest blood report")}>
            🩸 <strong>My Blood Report</strong>
            <span>Understand markers and trends</span>
          </button>
        )}
        {capabilities?.has_bio_ai_report && (
          <button type="button" onClick={() => onSend("Explain my latest Bio-AI report")}>
            🧬 <strong>My Bio-AI Report</strong>
            <span>Explore risk assessments</span>
          </button>
        )}
        {capabilities?.has_health_scenario && (
          <button
            type="button"
            onClick={() =>
              onSend("Summarize my health scenario", [], {
                type: "health_scenario",
                source: "supershyft",
              })
            }
          >
            ❤️ <strong>My Health Scenario</strong>
            <span>See what is going well and what needs attention</span>
          </button>
        )}
        {capabilities?.has_nutrition && (
          <button
            type="button"
            onClick={() =>
              onSend("What should I know about my nutrition?", [], {
                type: "nutrition_item",
                source: "supershyft",
              })
            }
          >
            🥗 <strong>Nutrition</strong>
            <span>Explore policy-checked food guidance</span>
          </button>
        )}
        <button type="button" onClick={() => inputRef.current?.focus()}>
          💬 <strong>Ask Cura</strong>
          <span>Ask a health question</span>
        </button>
      </div>
      {personal.length > 0 && (
        <>
          <p className="muted">Based on your health</p>
          <StarterChips
            items={personal.map((q, i) => ({ id: `p-${i}`, label: q.text, prompt: q.text }))}
            onPick={onSend}
            onAsk={() => inputRef.current?.focus()}
          />
        </>
      )}
      {personalUnavailable && personal.length === 0 && (
        <p className="muted">Your personal health questions will appear when your health data is available.</p>
      )}
      {general.length > 0 && (
        <>
          <p className="muted">Learn about health</p>
          <StarterChips
            items={general.map((q, i) => ({ id: `g-${i}`, label: q.text, prompt: q.text }))}
            onPick={onSend}
            onAsk={() => inputRef.current?.focus()}
          />
        </>
      )}
    </section>
  );
}
