export type ProcessingStageKey =
  | "REQUEST_RECEIVED"
  | "PLANNING"
  | "FETCHING_PERSONAL_DATA"
  | "FETCHING_BLOOD_DATA"
  | "FETCHING_BIOAI_DATA"
  | "FETCHING_QUESTIONNAIRE"
  | "FETCHING_HISTORY"
  | "READING_DOCUMENT"
  | "RETRIEVING_DOCUMENT_SECTION"
  | "CHECKING_MEDICAL_EVIDENCE"
  | "COMPARING_RESULTS"
  | "ANALYZING_TRENDS"
  | "PERSONALIZING"
  | "REASONING"
  | "CHECKING_SAFETY"
  | "COMPOSING_RESPONSE"
  | "COMPLETE";

export type RequestFamily =
  | "blood"
  | "bioai"
  | "questionnaire"
  | "document"
  | "general"
  | "trend"
  | "cross"
  | "package"
  | "followup"
  | "priority"
  | "personal";

export type CuraProcessingUiStage =
  | "planning"
  | "health_data"
  | "blood"
  | "bioai"
  | "questionnaire"
  | "history"
  | "document"
  | "comparison"
  | "medical_evidence"
  | "reasoning"
  | "personalization"
  | "safety"
  | "composing";

export type ProcessingEvent = {
  stage: ProcessingStageKey;
  message_key: string;
  family?: RequestFamily;
  follow_up?: boolean;
  elapsed_ms?: number | null;
};

const UI_STAGE: Record<string, CuraProcessingUiStage> = {
  REQUEST_RECEIVED: "planning",
  PLANNING: "planning",
  FETCHING_PERSONAL_DATA: "health_data",
  FETCHING_BLOOD_DATA: "blood",
  FETCHING_BIOAI_DATA: "bioai",
  FETCHING_QUESTIONNAIRE: "questionnaire",
  FETCHING_HISTORY: "history",
  READING_DOCUMENT: "document",
  RETRIEVING_DOCUMENT_SECTION: "document",
  CHECKING_MEDICAL_EVIDENCE: "medical_evidence",
  COMPARING_RESULTS: "comparison",
  ANALYZING_TRENDS: "history",
  PERSONALIZING: "personalization",
  REASONING: "reasoning",
  CHECKING_SAFETY: "safety",
  COMPOSING_RESPONSE: "composing",
};

const COPY: Record<string, string> = {
  "request.received": "Starting…",
  planning: "Understanding your question…",
  "general.understand": "Understanding your question…",
  "followup.context": "Keeping the previous context in mind…",
  "followup.fetch": "Checking the relevant results…",
  "health.fetch": "Reviewing your health data…",
  "blood.fetch": "Reading your latest results…",
  "bioai.fetch": "Reviewing your Bio-AI results…",
  "questionnaire.fetch": "Reviewing your questionnaire…",
  "history.fetch": "Looking through your previous results…",
  "document.read": "Reading your report…",
  "document.section": "Finding the relevant section…",
  "medical.fetch": "Checking trusted health information…",
  "compare.results": "Checking where the findings agree or differ…",
  "trend.analyze": "Comparing changes over time…",
  personalize: "Connecting your reports and lifestyle…",
  reason: "Preparing your explanation…",
  "blood.reason": "Understanding what the results mean together…",
  "bioai.reason": "Looking for contributing factors…",
  "document.reason": "Understanding how the findings relate…",
  "safety.check": "Checking your explanation…",
  "response.compose": "Preparing your explanation…",
  complete: "",
};

function familyFallback(family: RequestFamily | undefined, followUp: boolean | undefined): Record<string, string> {
  if (followUp) {
    return {
      planning: "Keeping the previous context in mind…",
      FETCHING_PERSONAL_DATA: "Checking the relevant results…",
      FETCHING_BLOOD_DATA: "Checking the relevant results…",
      REASONING: "Preparing your answer…",
      COMPOSING_RESPONSE: "Preparing your answer…",
    };
  }
  switch (family) {
    case "blood":
      return {
        FETCHING_BLOOD_DATA: "Reading your latest results…",
        FETCHING_PERSONAL_DATA: "Checking your biomarkers…",
        COMPARING_RESULTS: "Comparing related health markers…",
        REASONING: "Understanding what the results mean together…",
        COMPOSING_RESPONSE: "Preparing your explanation…",
      };
    case "bioai":
      return {
        FETCHING_BIOAI_DATA: "Reviewing your Bio-AI results…",
        FETCHING_BLOOD_DATA: "Checking the biomarkers behind this score…",
        REASONING: "Looking for contributing factors…",
        COMPOSING_RESPONSE: "Preparing your explanation…",
      };
    case "priority":
    case "personal":
      return {
        FETCHING_PERSONAL_DATA: "Reviewing your health data…",
        PERSONALIZING: "Connecting your reports and lifestyle…",
        REASONING: "Identifying what matters most right now…",
        COMPOSING_RESPONSE: "Prioritizing your next steps…",
      };
    case "document":
      return {
        READING_DOCUMENT: "Reading your report…",
        RETRIEVING_DOCUMENT_SECTION: "Finding the relevant section…",
        FETCHING_BLOOD_DATA: "Checking important results…",
        REASONING: "Understanding how the findings relate…",
        COMPOSING_RESPONSE: "Preparing a simpler explanation…",
      };
    case "general":
      return {
        PLANNING: "Understanding your question…",
        CHECKING_MEDICAL_EVIDENCE: "Checking trusted health information…",
        COMPOSING_RESPONSE: "Preparing a clear explanation…",
      };
    case "trend":
      return {
        FETCHING_HISTORY: "Looking through your previous results…",
        ANALYZING_TRENDS: "Comparing changes over time…",
        REASONING: "Checking which changes matter…",
        COMPOSING_RESPONSE: "Preparing your trend summary…",
      };
    case "cross":
      return {
        FETCHING_PERSONAL_DATA: "Reviewing your health records…",
        COMPARING_RESULTS: "Checking where the findings agree or differ…",
        PERSONALIZING: "Connecting your blood, Bio-AI and lifestyle data…",
        COMPOSING_RESPONSE: "Preparing your health summary…",
      };
    case "package":
      return {
        FETCHING_PERSONAL_DATA: "Reviewing what you've already tested…",
        REASONING: "Checking what's still missing…",
        COMPOSING_RESPONSE: "Preparing your testing suggestion…",
      };
    default:
      return {};
  }
}

export function processingCopy(event: ProcessingEvent): string {
  const keyed = COPY[event.message_key];
  if (keyed) return keyed;
  const fallback = familyFallback(event.family, event.follow_up);
  return fallback[event.stage] || fallback[event.message_key] || "Working on your answer…";
}

export function uiStageFor(stage: string): CuraProcessingUiStage {
  return UI_STAGE[stage] || "planning";
}
