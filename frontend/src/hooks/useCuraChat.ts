import { useState } from "react";
import { rewindConversation, streamChat } from "../lib/api";
import type { ConversationDetail } from "../lib/api";
import type { ChatMeta, ContextRef, EvidenceItem, FollowUp, Recommendation, UserProvenance } from "../types/chat";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  evidence?: EvidenceItem[];
  followUps?: Array<FollowUp | string>;
  recommendations?: Recommendation[];
  meta?: ChatMeta;
  provenance?: UserProvenance;
};

export function useCuraChat(language = "auto") {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(
    () => window.sessionStorage.getItem("cura_conversation_id")
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationEpoch, setConversationEpoch] = useState(0);

  async function send(text: string, documentIds: string[] = [], contextRef?: ContextRef) {
    setLoading(true);
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }]);
    try {
      setMessages((m) => [...m, { role: "assistant", content: "" }]);
      const res = await streamChat(
        text,
        conversationId,
        language,
        documentIds,
        contextRef,
        (token) => {
          setMessages((current) => {
            const next = [...current];
            const last = next.length - 1;
            if (last >= 0 && next[last].role === "assistant") {
              next[last] = { ...next[last], content: next[last].content + token };
            }
            return next;
          });
        }
      );
      setConversationId(res.conversation_id);
      window.sessionStorage.setItem("cura_conversation_id", res.conversation_id);
      setConversationEpoch((n) => n + 1);
      setMessages((current) => {
        const next = [...current];
        const last = next.length - 1;
        next[last] = {
          role: "assistant",
          content: res.answer,
          evidence: res.evidence,
          followUps: res.follow_ups,
          recommendations: res.recommendations || [],
          meta: res.meta,
          provenance: res.provenance,
        };
        return next;
      });
    } catch (err) {
      setMessages((current) => {
        const last = current[current.length - 1];
        if (last?.role === "assistant" && !last.content) {
          return current.slice(0, -1);
        }
        return current;
      });
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    window.sessionStorage.removeItem("cura_conversation_id");
    setConversationEpoch((n) => n + 1);
  }

  async function editAndResend(index: number, text: string) {
    const next = text.trim();
    if (!next || loading) return;
    const target = messages[index];
    if (!target || target.role !== "user") return;
    if (conversationId) {
      try {
        await rewindConversation(conversationId, index);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not edit that question.");
        return;
      }
    }
    setMessages((current) => current.slice(0, index));
    await send(next);
  }

  function resumeConversation(detail: ConversationDetail) {
    setConversationId(detail.id);
    setMessages(
      detail.messages.map((message) => ({
        role: message.role,
        content: message.content,
      }))
    );
    window.sessionStorage.setItem("cura_conversation_id", detail.id);
    setConversationEpoch((n) => n + 1);
  }

  return {
    messages,
    loading,
    error,
    send,
    editAndResend,
    conversationId,
    conversationEpoch,
    newConversation,
    resumeConversation,
  };
}
