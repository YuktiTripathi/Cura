import { useState } from "react";
import { rewindConversation, streamChat } from "../lib/api";
import type { ConversationDetail } from "../lib/api";
import type { ProcessingEvent } from "../lib/processingMessages";
import type { SemanticResponse } from "../types/semantic";
import type { ChatMeta, ContextRef, EvidenceItem, ExperienceBlock, FollowUp, PresentedFinding, Recommendation, StructuredResponse, TestingOption, TurnExperience, UserProvenance } from "../types/chat";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  evidence?: EvidenceItem[];
  followUps?: Array<FollowUp | string>;
  recommendations?: Recommendation[];
  meta?: ChatMeta;
  provenance?: UserProvenance;
  presentation?: StructuredResponse | null;
  experience?: TurnExperience | null;
  experienceBlocks?: ExperienceBlock[];
  testingOption?: TestingOption | null;
  semantic?: SemanticResponse | null;
  /** Values shown while the answer is still being written (SSE `preview`). */
  preview?: PresentedFinding[];
  /** User messages: what was attached when asked, so edit/regenerate ask the same thing. */
  documentIds?: string[];
  contextRef?: ContextRef;
};

export function useCuraChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(
    () => window.sessionStorage.getItem("cura_conversation_id")
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<ProcessingEvent | null>(null);
  // Every status shown during the current turn, in order, for the progress stepper.
  const [processingSteps, setProcessingSteps] = useState<ProcessingEvent[]>([]);
  const [conversationEpoch, setConversationEpoch] = useState(0);

  async function send(text: string, documentIds: string[] = [], contextRef?: ContextRef) {
    setLoading(true);
    setError(null);
    const initial: ProcessingEvent = { stage: "PLANNING", message_key: "planning", family: "personal" };
    setProcessing(initial);
    setProcessingSteps([initial]);
    setMessages((m) => [...m, { role: "user", content: text, documentIds, contextRef }]);
    let lastShown = 0;
    let pending: ProcessingEvent | null = null;
    let timer: number | null = null;
    let finished = false;
    const show = (event: ProcessingEvent) => {
      if (finished) return;
      lastShown = Date.now();
      setProcessing(event);
      setProcessingSteps((steps) => [...steps, event]);
    };
    const flush = (event: ProcessingEvent | null, immediate = false) => {
      if (!event) {
        setProcessing(null);
        return;
      }
      const now = Date.now();
      if (immediate || now - lastShown >= 300) {
        show(event);
        pending = null;
        return;
      }
      pending = event;
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (pending) {
          show(pending);
          pending = null;
        }
      }, 300);
    };
    try {
      setMessages((m) => [...m, { role: "assistant", content: "" }]);
      const res = await streamChat(
        text,
        conversationId,
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
        },
        (preview) => {
          setMessages((current) => {
            const next = [...current];
            const last = next.length - 1;
            if (last >= 0 && next[last].role === "assistant" && !next[last].content) {
              next[last] = { ...next[last], preview: preview.findings };
            }
            return next;
          });
        },
        (block) => {
          setMessages((current) => {
            const next = [...current];
            const last = next.length - 1;
            if (last < 0 || next[last].role !== "assistant") return current;
            const existingBlocks = next[last].experienceBlocks || [];
            if (existingBlocks.some((item) => item.sequence === block.sequence && item.kind === block.kind)) {
              return current;
            }
            const shouldAppendText = Boolean(block.text) && block.kind !== "continuation";
            const separator = shouldAppendText && next[last].content.trim() ? "\n\n" : "";
            next[last] = {
              ...next[last],
              preview: undefined,
              experienceBlocks: [...existingBlocks, block],
              content: shouldAppendText
                ? `${next[last].content}${separator}${block.text}`
                : next[last].content,
            };
            return next;
          });
        }
      );
      finished = true;
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
          experience: res.experience || null,
          experienceBlocks: res.experience?.blocks || next[last].experienceBlocks,
          testingOption: res.testing_option || res.presentation?.testing_option || null,
          semantic: res.semantic || null,
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
      finished = true;
      if (timer) window.clearTimeout(timer);
      setProcessing(null);
      setProcessingSteps([]);
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
    await send(next, target.documentIds || [], target.contextRef);
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
    processingSteps,
    error,
    send,
    editAndResend,
    conversationId,
    conversationEpoch,
    newConversation,
    resumeConversation,
  };
}
