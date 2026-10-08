/**
 * Semantic response contract (mirrors backend app/contracts/semantic_response.py).
 *
 * CURA decides what matters (summary + which blocks), the backend guarantees the values
 * (every `values` entry is read from the member's record, never from model text), and the
 * frontend only decides presentation. No block type belongs to an intent.
 */

export type BlockType =
  | "text"
  | "metric"
  | "metric_group"
  | "priority_list"
  | "risk"
  | "comparison"
  | "insight"
  | "reassurance"
  | "action_list"
  | "nutrition"
  | "warning";

export interface ResolvedValue {
  key: string; // blood.<code>.latest | blood.<code>.trend | bioai.<code>
  label: string;
  kind: "blood" | "bio_ai";
  value?: number | string | null;
  unit?: string | null;
  status?: string | null;
  reference_low?: number | null;
  reference_high?: number | null;
  date?: string | null;
  previous?: number | string | null;
  previous_date?: string | null;
  direction?: string | null;
}

export interface BlockItem {
  title?: string | null;
  text?: string | null;
  evidence?: string[];
  values?: ResolvedValue[];
}

export interface ResponseBlock {
  type: BlockType;
  title?: string | null;
  text?: string | null; // safe Markdown
  items?: BlockItem[];
  evidence?: string[];
  values?: ResolvedValue[];
  increase?: string[];
  reduce?: string[];
  collapsed?: boolean;
}

export interface ResponseSource {
  type: "blood_report" | "bio_ai" | "questionnaire" | "uploaded_document" | "medical_reference";
  date?: string | null;
  label?: string | null;
}

export interface SemanticResponse {
  summary: string; // safe Markdown, stands alone
  blocks: ResponseBlock[];
  follow_ups: string[];
  sources: ResponseSource[];
}
