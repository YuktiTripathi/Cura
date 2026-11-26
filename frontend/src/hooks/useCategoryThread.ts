import { useState } from "react";
import { streamChat } from "../lib/api";
import type { ChatMessage } from "./useCuraChat";
import type { ContextRef } from "../types/chat";

type Thread = { id: string | null; messages: ChatMessage[]; loading: boolean; error: string | null };

const empty: Thread = { id: null, messages: [], loading: false, error: null };

function storedId(categoryId: string): string | null {
  return window.sessionStorage.getItem(`cura_category_conversation:${categoryId}`);
}

/** A conversation per health category, separate from the main CURA chat. */
export function useCategoryThread() {
  const [threads, setThreads] = useState<Record<string, Thread>>({});

  function threadFor(categoryId: string | null): Thread {
    if (!categoryId) return empty;
    return threads[categoryId] || { ...empty, id: storedId(categoryId) };
  }

  async function ask(categoryId: string, text: string, contextRef?: ContextRef) {
    const current = threads[categoryId] || { ...empty, id: storedId(categoryId) };
    setThreads((all) => ({
      ...all,
      [categoryId]: { ...current, loading: true, error: null, messages: [...current.messages, { role: "user", content: text }, { role: "assistant", content: "" }] },
    }));
    try {
      let answer = "";
      const response = await streamChat(text, current.id, [], contextRef, (token) => {
        answer += token;
        setThreads((all) => {
          const thread = all[categoryId];
          if (!thread) return all;
          const messages = thread.messages.slice();
          const last = messages.length - 1;
          if (last >= 0) messages[last] = { ...messages[last], content: answer };
          return { ...all, [categoryId]: { ...thread, messages } };
        });
      });
      if (response.conversation_id) window.sessionStorage.setItem(`cura_category_conversation:${categoryId}`, response.conversation_id);
      setThreads((all) => {
        const thread = all[categoryId];
        if (!thread) return all;
        const messages = thread.messages.slice();
        const last = messages.length - 1;
        if (last >= 0) {
          messages[last] = {
            role: "assistant",
            content: response.answer || answer,
            followUps: response.follow_ups,
            evidence: response.evidence,
            recommendations: response.recommendations || [],
            meta: response.meta,
            provenance: response.provenance,
            presentation: response.presentation,
            experience: response.experience || null,
            testingOption: response.testing_option || response.presentation?.testing_option || null,
            semantic: response.semantic || null,
          };
        }
        return { ...all, [categoryId]: { id: response.conversation_id, messages, loading: false, error: null } };
      });
    } catch (error) {
      setThreads((all) => ({
        ...all,
        [categoryId]: { ...(all[categoryId] || current), loading: false, error: error instanceof Error ? error.message : "The answer could not be loaded." },
      }));
    }
  }

  return { threadFor, ask };
}
