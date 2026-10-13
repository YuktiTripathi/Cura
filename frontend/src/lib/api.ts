import { explicitLocale, t } from "../i18n";
import type { AnswerPreview, ChatResponse, ContextRef, ExperienceBlock } from "../types/chat";
import type { MeResponse } from "../types/me";
import type { HealthOverview } from "../types/overview";

const API = (import.meta.env.VITE_CURA_API_URL || "").replace(/\/$/, "");
const USER = import.meta.env.VITE_CURA_USER_ID || "";
// SuperShyft apps send Authorization: Bearer <existing access token> only.
// Never put user_id in the chat body. X-Cura-User-Id is development-only.

function authHeaders(): HeadersInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  let token = "";
  try {
    token = window.localStorage.getItem("supershyft_access_token") || "";
  } catch {
    token = "";
  }
  token = token || import.meta.env.VITE_CURA_ACCESS_TOKEN || "";
  if (token) headers.Authorization = `Bearer ${token}`;
  else if (import.meta.env.DEV && USER) headers["X-Cura-User-Id"] = USER;
  return headers;
}

// A language the member picked in the app overrides detection from their message.
function languageFields(): Record<string, string> {
  const locale = explicitLocale();
  return locale ? { language: locale, language_mode: "manual" } : {};
}

type ConsentStatus = { version: string; notice: string; required: boolean; accepted: boolean };

export async function getConsent(): Promise<ConsentStatus> {
  const res = await fetch(`${API}/api/v1/consent`, { headers: authHeaders(), credentials: "include" });
  if (!res.ok) throw new Error("The data notice isn't available right now.");
  return (await res.json()) as ConsentStatus;
}

export async function acceptConsent(version: string, accepted = true): Promise<ConsentStatus> {
  const res = await fetch(`${API}/api/v1/consent`, {
    method: "POST",
    headers: authHeaders(),
    credentials: "include",
    body: JSON.stringify({ version, accepted, language: navigator.language || null }),
  });
  if (!res.ok) throw new Error("Couldn't save your choice. Please try again.");
  return (await res.json()) as ConsentStatus;
}

async function isConsentRequired(res: Response): Promise<boolean> {
  if (res.status !== 403) return false;
  const data = await parseJson(res.clone());
  return (data.error as { code?: string } | undefined)?.code === "CONSENT_REQUIRED";
}

// Shows the versioned data notice once, records the member's answer, and retries.
// Interim UI until the dedicated consent screen ships in the web and Flutter apps.
async function fetchWithConsent(url: string, init: RequestInit): Promise<Response> {
  const res = await fetch(url, init);
  if (!(await isConsentRequired(res))) return res;
  const status = await getConsent();
  const ok = window.confirm(`${status.notice}\n\n${t("consent.question", "Do you agree?")}`);
  if (!ok) throw new Error(t("consent.required", "Cura needs your consent before it can answer health questions."));
  await acceptConsent(status.version, true);
  return fetch(url, init);
}

async function parseJson(res: Response): Promise<Record<string, unknown>> {
  const raw = await res.text();
  try {
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function fallbackMe(): MeResponse {
  return {
    user_id: USER || null,
    first_name: null,
    last_name: null,
    display_name: null,
    greeting: "Hi there 👋",
    profile_available: false,
    capabilities: {
      has_blood_report: false,
      has_bio_ai_report: false,
      has_questionnaire: false,
      has_nutrition: false,
      has_health_scenario: false,
    },
    starters: {
      personal: [],
      general: [
        { text: "What does HbA1c measure?", knowledge_scope: "general", category: "general_education" },
        { text: "What is Vitamin D and why is it important?", knowledge_scope: "general", category: "general_education" },
      ],
      personal_unavailable: true,
    },
  };
}

export async function getCurrentUser(): Promise<MeResponse> {
  try {
    const res = await fetch(`${API}/api/v1/me`, { headers: authHeaders() });
    const data = await parseJson(res);
    if (!res.ok) return fallbackMe();
    return data as unknown as MeResponse;
  } catch {
    return fallbackMe();
  }
}

export async function getOverview(): Promise<HealthOverview> {
  const res = await fetch(`${API}/api/v1/me/overview`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Your health overview isn't available right now.");
  return (await res.json()) as HealthOverview;
}

export async function transcribeVoice(
  blob: Blob
): Promise<{ transcript: string; text?: string; detected_language: string | null; language?: string | null; confidence: number | null }> {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  const headers: Record<string, string> = {};
  const token = window.localStorage.getItem("supershyft_access_token") || import.meta.env.VITE_CURA_ACCESS_TOKEN || "";
  if (token) headers.Authorization = `Bearer ${token}`;
  else if (import.meta.env.DEV && USER) headers["X-Cura-User-Id"] = USER;
  let res: Response;
  try {
    res = await fetch(`${API}/api/v1/voice/transcribe`, { method: "POST", headers, body: form });
  } catch {
    throw new Error("Can't reach the Cura API for voice. You can continue by typing.");
  }
  const data = await parseJson(res);
  if (!res.ok) {
    const err = data.error as { message?: string } | undefined;
    throw new Error(err?.message || "Voice transcription failed.");
  }
  return {
    transcript: String(data.transcript || data.text || ""),
    text: String(data.text || data.transcript || ""),
    detected_language: (data.detected_language as string | null) || (data.language as string | null) || null,
    language: (data.language as string | null) || (data.detected_language as string | null) || null,
    confidence: (data.confidence as number | null) ?? null,
  };
}

const CONSENT_REQUIRED_EN = "Cura needs your consent before it can answer health questions.";
const RETRY_STATUSES = new Set([429, 502, 503, 504]);
const MAX_ATTEMPTS = 3;

class ServerStreamError extends Error {}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function retryDelayMs(res: Response | null, attempt: number): number {
  const header = res?.headers.get("Retry-After");
  const seconds = header ? Number(header) : NaN;
  if (Number.isFinite(seconds) && seconds >= 0) return Math.min(seconds, 10) * 1000;
  return Math.min(500 * 2 ** attempt, 4000) + Math.floor(Math.random() * 250);
}

/**
 * POST with safe retries (readiness plan 5.9). The same Idempotency-Key is sent on every
 * attempt, so a retry after a dropped connection returns the original answer instead of
 * running the question twice. Retries network failures, 429 and 502-504.
 */
async function postWithRetry(url: string, init: RequestInit): Promise<Response> {
  let lastError: unknown = null;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
    let res: Response | null = null;
    try {
      res = await fetchWithConsent(url, init);
    } catch (error) {
      if (error instanceof Error && error.message === t("consent.required", CONSENT_REQUIRED_EN)) throw error;
      lastError = error;
    }
    if (res && !RETRY_STATUSES.has(res.status)) return res;
    if (attempt === MAX_ATTEMPTS - 1) {
      if (res) return res;
      break;
    }
    await sleep(retryDelayMs(res, attempt));
  }
  void lastError;
  throw new Error(
    "Can't reach the Cura API. Check your connection and try again."
  );
}

function chatPayload(
  message: string,
  conversationId: string | null,
  documentIds: string[],
  contextRef?: ContextRef
): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    message,
    conversation_id: conversationId,
    ...languageFields(),
  };
  if (documentIds.length) payload.document_ids = documentIds;
  if (contextRef) payload.context_ref = contextRef;
  return payload;
}

export async function sendChat(
  message: string,
  conversationId: string | null,
  documentIds: string[] = [],
  contextRef?: ContextRef
): Promise<ChatResponse> {
  const headers = authHeaders() as Record<string, string>;
  headers["Idempotency-Key"] = crypto.randomUUID();
  const res = await postWithRetry(`${API}/api/v1/chat`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(chatPayload(message, conversationId, documentIds, contextRef)),
  });
  const data = await parseJson(res);
  if (!res.ok) {
    const err = data.error as { message?: string } | undefined;
    throw new Error(err?.message || "Request failed");
  }
  return data as unknown as ChatResponse;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  documentIds: string[],
  contextRef: ContextRef | undefined,
  onToken: (text: string) => void,
  onProgress?: (event: import("./processingMessages").ProcessingEvent) => void,
  onPreview?: (preview: AnswerPreview) => void,
  onExperienceBlock?: (block: ExperienceBlock) => void
): Promise<ChatResponse> {
  const headers = authHeaders() as Record<string, string>;
  headers.Accept = "text/event-stream";
  // One key for every attempt: a reconnect gets the finished answer, never a second run.
  headers["Idempotency-Key"] = crypto.randomUUID();
  const init: RequestInit = {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(chatPayload(message, conversationId, documentIds, contextRef)),
  };
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const res = await postWithRetry(`${API}/api/v1/chat/stream`, init);
    if (!res.ok || !res.body) {
      const data = await parseJson(res);
      const err = data.error as { message?: string } | undefined;
      throw new Error(err?.message || "Streaming request failed");
    }
    try {
      const completed = await readChatStream(res.body, onToken, onProgress, onPreview, onExperienceBlock);
      if (completed) return completed;
    } catch (error) {
      if (error instanceof ServerStreamError) throw new Error(error.message);
      // Connection dropped mid-stream: reconnect once with the same key.
    }
    if (attempt === 0) await sleep(retryDelayMs(null, 0));
  }
  throw new Error("The connection dropped before the answer arrived. Please try again.");
}

async function readChatStream(
  body: ReadableStream<Uint8Array>,
  onToken: (text: string) => void,
  onProgress?: (event: import("./processingMessages").ProcessingEvent) => void,
  onPreview?: (preview: AnswerPreview) => void,
  onExperienceBlock?: (block: ExperienceBlock) => void
): Promise<ChatResponse | null> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed: ChatResponse | null = null;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      const event = frame.match(/^event:\s*(.+)$/m)?.[1];
      const raw = frame.match(/^data:\s*(.+)$/m)?.[1];
      if (!event || !raw) continue;
      const data = JSON.parse(raw);
      if (event === "token") onToken(data.text || "");
      if (event === "progress" && onProgress) onProgress(data);
      if (event === "preview" && onPreview) onPreview(data as AnswerPreview);
      if (event === "experience_block" && onExperienceBlock) onExperienceBlock(data as ExperienceBlock);
      if (event === "error") throw new ServerStreamError(data.message || "Streaming request failed");
      if (event === "complete" || event === "answer") completed = data as ChatResponse;
    }
  }
  return completed;
}

export type UploadedDocument = {
  document_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  source: string;
  upload_status: string;
  extraction_status: string;
  extraction_error?: string | null;
  created_at: string;
  processing_status?: string | null;
  pageindex_status?: string | null;
  document_kind?: string | null;
  document_type?: string | null;
  structured_facts_ready?: boolean;
  narrative_ready?: boolean;
};

function authHeadersMultipart(): HeadersInit {
  const headers: Record<string, string> = {};
  const token = window.localStorage.getItem("supershyft_access_token") || import.meta.env.VITE_CURA_ACCESS_TOKEN || "";
  if (token) headers.Authorization = `Bearer ${token}`;
  else if (import.meta.env.DEV && USER) headers["X-Cura-User-Id"] = USER;
  return headers;
}

export async function uploadDocument(file: File, conversationId: string | null): Promise<UploadedDocument> {
  const form = new FormData();
  form.append("file", file, file.name);
  if (conversationId) form.append("conversation_id", conversationId);
  const res = await fetch(`${API}/api/v1/documents`, {
    method: "POST",
    headers: authHeadersMultipart(),
    body: form,
  });
  const data = await parseJson(res);
  if (!res.ok) {
    const err = data.error as { message?: string } | undefined;
    throw new Error(err?.message || "Upload failed");
  }
  return data as unknown as UploadedDocument;
}

export async function getDocument(documentId: string): Promise<UploadedDocument> {
  const res = await fetch(`${API}/api/v1/documents/${documentId}`, { headers: authHeaders() });
  const data = await parseJson(res);
  if (!res.ok) throw new Error("Document not found.");
  return data as unknown as UploadedDocument;
}

export type DocumentPage = {
  document_id: string;
  filename: string;
  page: number;
  page_count: number;
  text: string;
  approximate: boolean;
};

export async function getDocumentPage(documentId: string, page: number): Promise<DocumentPage> {
  const res = await fetch(`${API}/api/v1/documents/${documentId}/pages/${page}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("That page isn't available.");
  return (await res.json()) as DocumentPage;
}

export type DocumentFact = {
  key: string;
  label: string;
  value?: number | null;
  unit?: string | null;
  reference_low?: number | null;
  reference_high?: number | null;
  reference_text?: string | null;
  status?: string | null;
  page?: number | null;
  line?: number | null;
  excerpt?: string | null;
};

export type DocumentFacts = { document_id: string; filename: string; ready: boolean; facts: DocumentFact[] };

export async function getDocumentFacts(documentId: string): Promise<DocumentFacts> {
  const res = await fetch(`${API}/api/v1/documents/${documentId}/facts`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Those values aren't available.");
  return (await res.json()) as DocumentFacts;
}

export async function listDocuments(): Promise<UploadedDocument[]> {
  const res = await fetch(`${API}/api/v1/documents`, { headers: authHeaders() });
  const data = await parseJson(res);
  if (!res.ok) return [];
  const docs = data.documents as UploadedDocument[] | undefined;
  return docs || [];
}

export async function deleteDocument(documentId: string): Promise<void> {
  await fetch(`${API}/api/v1/documents/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}

export type ConversationSummary = {
  id: string;
  title: string | null;
  updated_at: string;
};

export type ConversationDetail = {
  id: string;
  title: string | null;
  messages: Array<{ id: string; role: "user" | "assistant"; content: string; created_at: string }>;
  suggested_questions?: Array<{ id: string; text: string; category: string }>;
};

export async function createConversation(): Promise<ConversationDetail> {
  const res = await fetch(`${API}/api/v1/conversations`, { method: "POST", headers: authHeaders() });
  if (!res.ok) throw new Error("Could not start a conversation.");
  return (await res.json()) as ConversationDetail;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API}/api/v1/conversations`, { headers: authHeaders() });
  if (!res.ok) return [];
  return (await res.json()) as ConversationSummary[];
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`${API}/api/v1/conversations/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Conversation not found.");
  return (await res.json()) as ConversationDetail;
}

export async function deleteConversation(id: string): Promise<void> {
  await fetch(`${API}/api/v1/conversations/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}

export async function rewindConversation(id: string, keep: number): Promise<void> {
  const res = await fetch(`${API}/api/v1/conversations/${id}/rewind`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ keep }),
  });
  if (!res.ok) throw new Error("Could not edit that question.");
}

export async function sendFeedback(
  conversationId: string,
  rating: "up" | "down",
  comment?: string
): Promise<void> {
  const res = await fetch(`${API}/api/v1/feedback`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      conversation_id: conversationId,
      rating,
      comment: comment || null,
    }),
  });
  if (!res.ok) throw new Error("Could not save feedback.");
}
