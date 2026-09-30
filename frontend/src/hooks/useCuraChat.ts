import { useState } from "react";
import { rewindConversation, streamChat } from "../lib/api";
import type { ConversationDetail } from "../lib/api";
import type { ChatMeta, ContextRef, EvidenceItem, FollowUp, Recommendation, StructuredResponse, TestingOption, UserProvenance } from "../types/chat";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  evidence?: EvidenceItem[];
  followUps?: Array<FollowUp | string>;
  recommendations?: Recommendation[];
  meta?: ChatMeta;
  provenance?: UserProvenance;
  presentation?: StructuredResponse | null;
  testingOption?: TestingOption | null;
};

export function useCuraChat(language = "auto") {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(
    () => window.sessionStorage.getItem("cura_conversation_id")
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<import("../lib/processingMessages").ProcessingEvent | null>(null);
  const [conversationEpoch, setConversationEpoch] = useState(0);

  async function send(text: string, documentIds: string[] = [], contextRef?: ContextRef) {
    setLoading(true);
    setError(null);
    setProcessing({ stage: "PLANNING", message_key: "planning", family: "personal" });
    setMessages((m) => [...m, { role: "user", content: text }]);
    let lastShown = 0;
    let pending: import("../lib/processingMessages").ProcessingEvent | null = null;
    let timer: number | null = null;
    const flush = (event: import("../lib/processingMessages").ProcessingEvent | null, immediate = false) => {
      if (!event) {
        setProcessing(null);
        return;
      }
      const now = Date.now();
      if (immediate || now - lastShown >= 300) {
        lastShown = now;
        setProcessing(event);
        pending = null;
        return;
      }
      pending = event;
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (pending) {
          lastShown = Date.now();
          setProcessing(pending);
          pending = null;
        }
      }, 300);
    };
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
        },
        (event) => {
          if (event.stage === "COMPLETE") return;
          flush(event);
        }
      );
      if (timer) window.clearTimeout(timer);
      setProcessing(null);
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
          presentation: res.presentation,
          testingOption: res.testing_option || res.presentation?.testing_option || null,
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
      setProcessing(null);
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
    processing,
    error,
    send,
    editAndResend,
    conversationId,
    conversationEpoch,
    newConversation,
    resumeConversation,
  };
}
