import type { RefObject } from "react";
import type { ContextRef } from "../types/chat";
import type { MeResponse } from "../types/me";
import { StarterChips } from "./StarterChips";
import { t } from "../i18n";

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
      <p className="welcome-lead">{t("ui.WelcomeExperience.how_can_i_help_you_understand_your_healt", "How can I help you understand your health better?")}</p>
      <p className="muted">
        I can explain your available SuperShyft reports, build your health scenario, explore nutrition,
        and answer general health questions.
      </p>
      <div className="capability-grid">
        {capabilities?.has_blood_report && (
          <button type="button" onClick={() => onSend("Show me my latest blood report")}>
            🩸 <strong>{t("ui.WelcomeExperience.my_blood_report", "My Blood Report")}</strong>
            <span>{t("ui.WelcomeExperience.understand_markers_and_trends", "Understand markers and trends")}</span>
          </button>
        )}
        {capabilities?.has_bio_ai_report && (
          <button type="button" onClick={() => onSend("Explain my latest Bio-AI report")}>
            🧬 <strong>{t("ui.WelcomeExperience.my_bio_ai_report", "My Bio-AI Report")}</strong>
            <span>{t("ui.WelcomeExperience.explore_risk_assessments", "Explore risk assessments")}</span>
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
            ❤️ <strong>{t("ui.WelcomeExperience.my_health_scenario", "My Health Scenario")}</strong>
            <span>{t("ui.WelcomeExperience.see_what_is_going_well_and_what_needs_at", "See what is going well and what needs attention")}</span>
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
            🥗 <strong>{t("ui.WelcomeExperience.nutrition", "Nutrition")}</strong>
            <span>{t("ui.WelcomeExperience.explore_policy_checked_food_guidance", "Explore policy-checked food guidance")}</span>
          </button>
        )}
        <button type="button" onClick={() => inputRef.current?.focus()}>
          💬 <strong>{t("ui.WelcomeExperience.ask_cura", "Ask Cura")}</strong>
          <span>{t("ui.WelcomeExperience.ask_a_health_question", "Ask a health question")}</span>
        </button>
      </div>
      {personal.length > 0 && (
        <>
          <p className="muted">{t("ui.WelcomeExperience.based_on_your_health", "Based on your health")}</p>
          <StarterChips
            items={personal.map((q, i) => ({ id: `p-${i}`, label: q.text, prompt: q.text }))}
            onPick={onSend}
            onAsk={() => inputRef.current?.focus()}
          />
        </>
      )}
      {personalUnavailable && personal.length === 0 && (
        <p className="muted">{t("ui.WelcomeExperience.your_personal_health_questions_will_appe", "Your personal health questions will appear when your health data is available.")}</p>
      )}
      {general.length > 0 && (
        <>
          <p className="muted">{t("ui.WelcomeExperience.learn_about_health", "Learn about health")}</p>
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
