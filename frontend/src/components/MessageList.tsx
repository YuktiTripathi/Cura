import { useState } from "react";
import { assistantTextSegments, followUpText, displayAssistantText, type ContextRef, type UserProvenance } from "../types/chat";
import type { ChatMessage } from "../hooks/useCuraChat";

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
      {messages.map((m, i) => (
        <article key={i} className={m.role}>
          {m.role === "user" && editingIndex === i ? (
            <div className="edit-question">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                aria-label="Edit question"
              />
              <div className="edit-question-actions">
                <button type="button" onClick={saveEdit} disabled={!draft.trim()}>
                  Save
                </button>
                <button type="button" className="text-button" onClick={() => setEditingIndex(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p>{m.role === "assistant" ? <AssistantBody content={m.content} /> : m.content}</p>
          )}
          {m.role === "user" && editingIndex !== i && onEditQuestion && (
            <div className="user-actions">
              <button
                type="button"
                className="text-button"
                disabled={editingDisabled}
                onClick={() => startEdit(i, m.content)}
              >
                Edit
              </button>
            </div>
          )}
          {m.recommendations && m.recommendations.length > 0 && (
            <div className="recommendations">
              <p>Suggested actions</p>
              {m.recommendations.map((r, index) => (
                <div className="recommendation-card" key={`${r.category}-${index}`}>
                  <strong>{r.category.replace(/_/g, " ")}</strong>
                  <p>{r.text}</p>
                </div>
              ))}
            </div>
          )}
          {m.meta?.escalation && (
            <div className="escalation">
              <strong>Next step</strong>
              <p>
                {m.meta.escalation === "urgent_care"
                  ? "Seek urgent in-person medical care."
                  : "Discuss this with a qualified clinician."}
              </p>
            </div>
          )}
          {m.role === "assistant" && <ProvenanceLine provenance={m.provenance} />}
          {m.role === "assistant" && m.content && (
            <div className="feedback-actions">
              <span className="muted">Was this helpful?</span>
              <button type="button" className="text-button" onClick={() => onFeedback("up")}>👍</button>
              <button type="button" className="text-button" onClick={() => onFeedback("down")}>👎</button>
            </div>
          )}
          {m.followUps && m.followUps.length > 0 && (
            <div className="chips">
              {m.followUps.map((f) => {
                const text = followUpText(f);
                return (
                  <button key={text} type="button" onClick={() => onFollowUp(text)}>
                    {text}
                  </button>
                );
              })}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function debugMode(): boolean {
  return import.meta.env.VITE_CURA_DEBUG === "true";
}

function AssistantBody({ content }: { content: string }) {
  const text = displayAssistantText(content, debugMode());
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, index) => (
        <span key={index}>
          {index > 0 ? <br /> : null}
          {assistantTextSegments(line).map((part, partIndex) =>
            part.bold ? <strong key={partIndex}>{part.text}</strong> : <span key={partIndex}>{part.text}</span>
          )}
        </span>
      ))}
    </>
  );
}

function ProvenanceLine({ provenance }: { provenance?: UserProvenance }) {
  const sources = provenance?.sources || [];
  if (!sources.length) return null;
  const label = sources.length === 1 ? "Source" : "Sources";
  return (
    <p className="source-line" data-testid="provenance-line">
      {label}:{" "}
      {sources.map((source, index) => (
        <span key={`${source.name}-${index}`}>
          {index > 0 ? " · " : null}
          {source.url ? (
            <a href={source.url} target="_blank" rel="noreferrer">
              {source.name}
            </a>
          ) : (
            source.name
          )}
        </span>
      ))}
    </p>
  );
}
