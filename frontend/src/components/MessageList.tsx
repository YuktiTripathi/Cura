import { useState } from "react";
import type { ContextRef } from "../types/chat";
import type { ChatMessage } from "../hooks/useCuraChat";
import { AssistantBody } from "./messages/AssistantBody";
import { EscalationNote, FeedbackActions, FollowUpChips, Recommendations } from "./messages/MessageExtras";
import { PresentedAnswer } from "./messages/PresentedAnswer";
import { PreviewAnswer } from "./messages/PreviewAnswer";
import { ProvenanceLine } from "./messages/ProvenanceLine";
import { TestingOptionCard } from "./messages/TestingOptionCard";
import { UserQuestionActions, UserQuestionEditor } from "./messages/UserQuestion";

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
      {messages.map((m, i) => {
        // An assistant placeholder stays empty until the answer arrives; the progress stepper covers that
        // wait. If Cura already sent the values being asked about, show them meanwhile.
        if (m.role === "assistant" && !m.content && !m.presentation) {
          return m.preview && m.preview.length > 0 ? (
            <article key={i} className="assistant pending" aria-busy="true">
              <PreviewAnswer findings={m.preview} />
            </article>
          ) : null;
        }
        return (
          <article key={i} className={m.role}>
            {m.role === "user" && editingIndex === i ? (
              <UserQuestionEditor
                draft={draft}
                onDraftChange={setDraft}
                onSave={saveEdit}
                onCancel={() => setEditingIndex(null)}
              />
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
              <UserQuestionActions disabled={editingDisabled} onEdit={() => startEdit(i, m.content)} />
            )}
            {m.testingOption && !m.presentation ? <TestingOptionCard option={m.testingOption} /> : null}
            {m.recommendations && <Recommendations items={m.recommendations} />}
            {m.meta?.escalation && <EscalationNote escalation={m.meta.escalation} />}
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
            {m.role === "assistant" && m.content && <FeedbackActions onFeedback={onFeedback} />}
            {m.followUps && <FollowUpChips items={m.followUps} onPick={onFollowUp} />}
          </article>
        );
      })}
    </div>
  );
}
