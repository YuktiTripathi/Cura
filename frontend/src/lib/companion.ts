/**
 * Readers for presentation fields the API declares as plain objects. Shapes mirror the backend's
 * ProactiveInsight and ClinicianHandoff models (contracts/personalization.py); anything that does
 * not match is dropped rather than rendered.
 */

export type AnswerInsight = { title: string; summary: string; entity: string | null };

export type DoctorHandoff = {
  key_findings: string[];
  longitudinal_changes: string[];
  relevant_context: string[];
  missing_information: string[];
  questions_for_clinician: string[];
};

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim() !== "") : [];

/** Insights the backend attached to this answer, minus suppressed ones, at most `limit`. */
export function readInsights(raw: unknown, limit = 2): AnswerInsight[] {
  if (!Array.isArray(raw)) return [];
  const out: AnswerInsight[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    if (row.suppressed === true) continue;
    if (typeof row.summary !== "string" || !row.summary.trim()) continue;
    out.push({
      title: typeof row.title === "string" && row.title.trim() ? row.title : "Worth a look",
      summary: row.summary,
      entity: typeof row.entity === "string" ? row.entity : null,
    });
  }
  return out.slice(0, limit);
}

export function readHandoff(raw: unknown): DoctorHandoff | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const handoff: DoctorHandoff = {
    key_findings: strings(row.key_findings),
    longitudinal_changes: strings(row.longitudinal_changes),
    relevant_context: strings(row.relevant_context),
    missing_information: strings(row.missing_information),
    questions_for_clinician: strings(row.questions_for_clinician),
  };
  return handoff.key_findings.length ? handoff : null;
}

export function handoffAsText(handoff: DoctorHandoff, preparedOn: Date = new Date()): string {
  const sections: Array<[string, string[]]> = [
    ["Key findings", handoff.key_findings],
    ["Changes over time", handoff.longitudinal_changes],
    ["Relevant context", handoff.relevant_context],
    ["Not yet available", handoff.missing_information],
    ["Questions to ask", handoff.questions_for_clinician],
  ];
  const lines = [`Health summary for my doctor (prepared with Cura, ${preparedOn.toLocaleDateString()})`, ""];
  for (const [title, items] of sections) {
    if (!items.length) continue;
    lines.push(`${title}:`, ...items.map((item) => `- ${item}`), "");
  }
  lines.push("Educational summary from my own records; not a diagnosis.");
  return lines.join("\n");
}

/** Follow-ups first, then extra suggestion chips, without repeats. */
export function mergeSuggestions<T extends string | { text: string }>(followUps: T[] = [], chips: string[] = [], limit = 3): Array<T | string> {
  const seen = new Set<string>();
  const out: Array<T | string> = [];
  for (const item of [...followUps, ...chips]) {
    const text = (typeof item === "string" ? item : item.text).trim();
    const key = text.toLowerCase();
    if (!text || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
    if (out.length >= limit) break;
  }
  return out;
}
