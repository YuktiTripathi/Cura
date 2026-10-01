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
  response_mode?: string;
  conversation_goal?: string;
  response_depth?: string;
  next_conversation_action?: string;
};

export type ProvenanceSource = {
  name: string;
  url?: string | null;
  source_type: string;
  source_id?: string | null;
  occurred_at?: string | null;
};

export type UserProvenance = {
  type: string;
  sources: ProvenanceSource[];
};

export type PresentedFinding = {
  label: string;
  value?: string | null;
  unit?: string | null;
  status?: string | null;
  source_type?: string | null;
  source_date?: string | null;
  source_id?: string | null;
  source_label?: string | null;
  canonical_key?: string | null;
  numeric_value?: number | null;
  reference_low?: number | null;
  reference_high?: number | null;
};

/** SSE `preview`: values from the user's records, sent before the explanation is ready. */
export type AnswerPreview = {
  findings: PresentedFinding[];
};

export type HealthTheme = {
  title: string;
  priority: "high" | "medium" | "low";
  status: "needs_attention" | "monitor" | "reassuring" | "uncertain";
  supporting_fact_ids: string[];
  interpretation?: string | null;
  missing_information: string[];
  next_step?: string | null;
  related_findings: PresentedFinding[];
};

export type PackageAction = {
  type: "OPEN_PACKAGE" | "COMPARE_WITH_EXISTING_RESULTS";
  label: string;
  package_id?: string | null;
  catalog_kind?: "package" | "test_group" | null;
};

export type ExistingResult = {
  key: string;
  label: string;
  measured_on?: string | null;
};

export type PackageComparison = {
  included: string[];
  already_have: ExistingResult[];
  adds_information: string[];
  timing_note?: string | null;
  recently_available?: string[];
  missing?: string[];
  stale?: string[];
  new_information?: string[];
};

export type TestingOption = {
  type?: "package_recommendation";
  relevance?: "HIGH_RELEVANCE" | "MODERATE_RELEVANCE" | "OPTIONAL" | "NOT_RECOMMENDED_NOW";
  headline?: string;
  package?: { id: string; name: string; kind?: "package" | "test_group" };
  reason?: string;
  helps_answer?: string;
  relevant_tests?: string[];
  already_recent?: string[];
  primary_action?: PackageAction;
  secondary_action?: PackageAction | null;
  comparison?: PackageComparison;
  catalog_id: string;
  kind: "package" | "test_group";
  display_name: string;
  provider?: string | null;
  included_matched_tests: string[];
  included_matched_labels: string[];
  price?: number | null;
  currency?: string;
  medical_rationale?: string;
  match_reason?: string;
  cta_label?: string;
  invitation?: string;
};

export type StructuredResponse = {
  mode: string;
  headline?: string | null;
  summary?: string | null;
  findings: PresentedFinding[];
  interpretation?: string | null;
  uncertainties: string[];
  next_steps: string[];
  follow_up?: string | null;
  display_entities?: string[];
  reasoning_context?: string[];
  summary_style?: "RAW_HEALTH_SNAPSHOT" | "NARRATIVE_HEALTH_SUMMARY" | null;
  overall_summary?: string | null;
  themes?: HealthTheme[];
  raw_findings?: PresentedFinding[];
  testing_option?: TestingOption | null;
  personal_relevance?: string | null;
  clinician_handoff?: Record<string, unknown> | null;
  quiet_mode?: boolean;
  proactive_insights?: Array<Record<string, unknown>>;
  structured_next_steps?: Array<Record<string, unknown>>;
  health_journey?: Record<string, unknown> | null;
  conversation_goal?: string | null;
  response_depth?: string | null;
  next_conversation_action?: string | null;
  blocks?: Array<{ kind: string; title?: string | null; text?: string | null; expandable?: boolean }>;
  topic_summary?: { main_facts?: string[]; user_told_cura?: string[]; remaining_question?: string | null; text?: string | null } | null;
  related_findings?: PresentedFinding[];
  suggestion_chips?: string[];
};

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  evidence: EvidenceItem[];
  follow_ups: FollowUp[] | string[];
  recommendations?: Recommendation[];
  meta: ChatMeta;
  provenance?: UserProvenance;
  presentation?: StructuredResponse | null;
  testing_option?: TestingOption | null;
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
        return null;
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
