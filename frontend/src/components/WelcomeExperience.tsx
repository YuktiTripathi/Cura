import type { RefObject } from "react";
import type { ContextRef } from "../types/chat";
import type { MeResponse } from "../types/me";
import { StarterChips } from "./StarterChips";
import { t } from "../i18n";

export function WelcomeExperience({
  me,
  meLoading,
  suggestions = [],
  onSend,
  onOpenOverview,
  inputRef,
  returning = false,
}: {
  me: MeResponse | null;
  meLoading: boolean;
  suggestions?: Array<{ id: string; text: string }>;
  onSend: (text: string, documentIds?: string[], contextRef?: ContextRef) => void;
  /** Opens the visual overview. Without it the buttons start a chat, as before. */
  onOpenOverview?: (kind: "blood" | "bio_ai" | "unified") => void;
  inputRef: RefObject<HTMLInputElement>;
  /** True when this person has used Cura before on this device. */
  returning?: boolean;
}) {
  const greeting = meLoading ? "Hi 👋" : me?.greeting || "Hi there 👋";
  const personal = me?.starters?.personal || [];
  const general = me?.starters?.general || [];
  const personalUnavailable = Boolean(me?.starters?.personal_unavailable);
  const capabilities = me?.capabilities;

  return (
    <section className="welcome">
      <p className="greeting">{greeting}</p>
      <p className="welcome-lead">
        {returning
          ? t("ui.WelcomeExperience.welcome_back", "Welcome back. Pick up where you left off, or ask something new.")
          : t("ui.WelcomeExperience.how_can_i_help_you_understand_your_healt", "How can I help you understand your health better?")}
      </p>
      <p className="muted">{introLine(capabilities)}</p>
      <div className="capability-grid">
        {(capabilities?.has_blood_report || capabilities?.has_bio_ai_report) && (
          <button
            type="button"
            onClick={() =>
              onOpenOverview
                ? onOpenOverview("unified")
                : onSend("Help me understand my overall health.", [], {
                    type: "bio_ai_report",
                    source: "supershyft",
                    entry_point: "health_area",
                  })
            }
          >
            🩺 <strong>{t("ui.WelcomeExperience.my_health_overview", "My Health Overview")}</strong>
            <span>{t("ui.WelcomeExperience.blood_results_and_risks_together", "Your blood results and future risks together")}</span>
          </button>
        )}
        {capabilities?.has_nutrition && (
          <button
            type="button"
            onClick={() =>
              onSend("What does my nutrition data say, and what should I improve?", [], {
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
      {suggestions.length > 0 ? (
        <>
          <p className="muted">Suggested questions</p>
          <StarterChips
            items={suggestions.map((q) => ({ id: q.id, label: q.text, prompt: q.text }))}
            onPick={onSend}
            onAsk={() => inputRef.current?.focus()}
          />
        </>
      ) : (
        <>
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
        </>
      )}
      {suggestions.length === 0 && general.length > 0 && (
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

/** Mentions only what this person actually has, so nothing is promised that is not there. */
export function introLine(c?: { has_blood_report?: boolean; has_bio_ai_report?: boolean; has_nutrition?: boolean } | null): string {
  const parts: string[] = [];
  if (c?.has_blood_report) parts.push("your blood report");
  if (c?.has_bio_ai_report) parts.push("your Bio-AI report");
  if (c?.has_nutrition) parts.push("your nutrition");
  if (parts.length === 0) return "Ask me any health question and I will explain it in simple words.";
  const list = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  return `I can help you understand ${list} in plain language. You can also ask any general health question.`;
}
