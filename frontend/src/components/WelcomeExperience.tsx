import type { RefObject } from "react";
import type { ContextRef } from "../types/chat";
import { StarterChips } from "./StarterChips";
import { CARD_COPY } from "../welcome/greetings";
import type { GreetingChoice } from "../welcome/selectGreeting";

export function WelcomeExperience({
  greeting,
  questions,
  reportsConfirmedAbsent = false,
  onSend,
  onOpenOverview,
  inputRef,
}: {
  greeting: GreetingChoice | null;
  questions: string[];
  reportsConfirmedAbsent?: boolean;
  onSend: (text: string, documentIds?: string[], contextRef?: ContextRef) => void;
  onOpenOverview?: (kind: "blood" | "bio_ai" | "unified") => void;
  inputRef: RefObject<HTMLInputElement>;
}) {
  const understand = reportsConfirmedAbsent ? CARD_COPY.understand.descriptionWithoutReports : CARD_COPY.understand.description;
  return (
    <section className="welcome">
      <h1 className="greeting">{greeting?.heading || "Hi there 👋"}</h1>
      {greeting && (
        <>
          <p className="welcome-primary">{greeting.primary}</p>
          <p className="welcome-support">{greeting.supporting}</p>
        </>
      )}
      <div className="capability-grid">
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
          <strong>{CARD_COPY.understand.title}</strong>
          <span>{understand}</span>
        </button>
        <button
          type="button"
          onClick={() =>
            onSend("Based on my health results and eating habits, how can I eat better for my body?", [], {
              type: "nutrition_item",
              source: "supershyft",
            })
          }
        >
          <strong>{CARD_COPY.eat.title}</strong>
          <span>{CARD_COPY.eat.description}</span>
        </button>
        <button type="button" onClick={() => inputRef.current?.focus()}>
          <strong>{CARD_COPY.talk.title}</strong>
          <span>{CARD_COPY.talk.description}</span>
        </button>
      </div>
      {questions.length > 0 && (
        <>
          <p className="welcome-questions">Curious about your health?</p>
          <StarterChips
            items={questions.slice(0, 4).map((text, i) => ({ id: `home-${i}`, label: text, prompt: text }))}
            onPick={onSend}
            onAsk={() => inputRef.current?.focus()}
          />
        </>
      )}
    </section>
  );
}
