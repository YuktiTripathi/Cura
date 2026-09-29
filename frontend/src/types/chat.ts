export type EvidenceItem = {
  evidence_id: string;
  report_id: string;
  report_type: string;
  report_date: string;
  marker?: string | null;
  risk_code?: string | null;
  source?: string;
  document_id?: string | null;
  chunk_id?: string | null;
  filename?: string | null;
  page_start?: number | null;
  page_end?: number | null;
  excerpt?: string | null;
  value?: number | null;
  unit?: string | null;
  reference_range?: string | null;
};

export type FollowUp = {
  text: string;
  category: string;
  intent?: string | null;
  requires_personal_context?: boolean;
  knowledge_scope?: string;
};

export type ContextRef = {
  type: "blood_marker" | "blood_report" | "bio_ai_risk" | "bio_ai_report" | "health_scenario" | "nutrition_item" | "uploaded_document";
  source: "supershyft" | "user_uploaded";
  marker_code?: string | null;
  risk_code?: string | null;
  report_id?: string | null;
  document_id?: string | null;
};

export type Recommendation = {
  category: string;
  text: string;
  rationale?: string | null;
  evidence_codes: string[];
};

export type ChatMeta = {
  intent?: string;
  status?: string;
  llm_mode?: string;
  detected_language?: string;
  response_language?: string;
  sources_used?: string[];
  safety_flags?: string[];
  recommendation_flags?: string[];
  grounding_flags?: string[];
  escalation?: string | null;
  request_id?: string;
};

export type ProvenanceSource = {
  name: string;
  url?: string | null;
  source_type: string;
};

export type UserProvenance = {
  type: string;
  sources: ProvenanceSource[];
};

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  evidence: EvidenceItem[];
  follow_ups: FollowUp[] | string[];
  recommendations?: Recommendation[];
  meta: ChatMeta;
  provenance?: UserProvenance;
};

export function followUpText(item: FollowUp | string): string {
  return typeof item === "string" ? item : item.text;
}

const STRUCTURED_KEYS = [
  "answer",
  "claims",
  "recommendation_candidates",
  "follow_up_questions",
  "safety_flags",
  "escalation",
];

export function displayAssistantText(content: string, debug = false): string {
  if (debug) return content;
  const extracted = extractStructuredAnswer(content);
  return extracted ?? content;
}

export function assistantTextSegments(line: string): Array<{ text: string; bold: boolean }> {
  const parts = line.split(/(\*\*[^*]+\*\*)/g).filter((part) => part.length > 0);
  return parts.map((part) => {
    const match = part.match(/^\*\*([^*]+)\*\*$/);
    return match ? { text: match[1], bold: true } : { text: part, bold: false };
  });
}

export function extractStructuredAnswer(content: string, depth = 0): string | null {
  if (!content || depth > 3) return null;
  const trimmed = content.trim();
  if (!trimmed.startsWith("{") || !trimmed.includes("answer")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object") {
      const answer = parsed.answer;
      if (typeof answer === "string") {
        const nested = extractStructuredAnswer(answer, depth + 1);
        return nested ?? answer;
      }
      if (answer && typeof answer === "object" && typeof answer.answer === "string") {
        return answer.answer;
      }
      if (STRUCTURED_KEYS.some((key) => key in parsed)) {
        return "I had trouble formatting that answer. Please try asking again.";
      }
    }
  } catch {
    const match = trimmed.match(/"answer"\s*:\s*"((?:\\.|[^"\\])*)"/);
    if (match) {
      try {
        return JSON.parse(`"${match[1]}"`);
      } catch {
        return match[1];
      }
    }
  }
  return null;
}
