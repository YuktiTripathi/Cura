import { useState } from "react";
import type { ContextRef } from "../types/chat";
import type { ChatMessage } from "../hooks/useCuraChat";
import { AssistantBody } from "./messages/AssistantBody";
import { EscalationNote, FollowUpChips, Recommendations } from "./messages/MessageExtras";
import { MessageActions, type FeedbackRating } from "./messages/MessageActions";
import { SourceViewer } from "./SourceViewer";
import { groupEvidence } from "../lib/sources";
import { mergeSuggestions, readHandoff, readInsights } from "../lib/companion";
import { DoctorSummary } from "./DoctorSummary";
import { InsightNote } from "./messages/InsightNote";
import { displayAssistantText } from "../types/chat";
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
  onRegenerate,
  editingDisabled = false,
}: {
  messages: ChatMessage[];
  onFollowUp: (value: string) => void;
  onAskContext: (value: string, contextRef: ContextRef) => void;
  onFeedback: (rating: FeedbackRating, comment?: string) => void;
  onEditQuestion?: (index: number, text: string) => void;
  /** Re-ask the question behind the assistant message at this index. Offered on the latest answer. */
  onRegenerate?: (index: number) => void;
  editingDisabled?: boolean;
}) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [sourcesIndex, setSourcesIndex] = useState<number | null>(null);
  const [handoffIndex, setHandoffIndex] = useState<number | null>(null);
  const latestAssistant = messages.map((m) => m.role).lastIndexOf("assistant");
  const sourceGroups = sourcesIndex != null ? groupEvidence(messages[sourcesIndex]?.evidence) : [];

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
            {m.role === "assistant" && m.presentation ? <InsightNote insights={readInsights(m.presentation.proactive_insights)} /> : null}
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
            {m.role === "assistant" && m.content && (
              <MessageActions
                text={displayAssistantText(m.content)}
                onFeedback={onFeedback}
                onRegenerate={onRegenerate && i === latestAssistant ? () => onRegenerate(i) : undefined}
                disabled={editingDisabled}
                sourceCount={groupEvidence(m.evidence).length}
                onViewSources={() => setSourcesIndex(i)}
                onDoctorSummary={readHandoff(m.presentation?.clinician_handoff) ? () => setHandoffIndex(i) : undefined}
              />
            )}
            {m.role === "assistant" ? (
              <FollowUpChips items={mergeSuggestions(m.followUps || [], m.presentation?.suggestion_chips || [])} onPick={onFollowUp} />
            ) : null}
          </article>
        );
      })}
      <DoctorSummary
        handoff={handoffIndex != null ? readHandoff(messages[handoffIndex]?.presentation?.clinician_handoff) : null}
        open={handoffIndex != null}
        onOpenChange={(open) => {
          if (!open) setHandoffIndex(null);
        }}
      />
      <SourceViewer
        groups={sourceGroups}
        open={sourcesIndex != null && sourceGroups.length > 0}
        onOpenChange={(open) => {
          if (!open) setSourcesIndex(null);
        }}
      />
    </div>
  );
}
