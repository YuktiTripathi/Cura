import { GREETINGS, type GreetingId } from "./greetings";

const SENSITIVE = /\b(suicid|self-harm|emergency|chest pain|cancer|tumou?r|hiv|pregnan|miscarriage|depress|anxiety|panic|medication|dose|diagnos|symptom|sexual|std|sti|abuse|overdose)\b/i;

export type GreetingInput = {
  firstName: string | null;
  /** Successful history says whether this member has talked before. Null means the request failed or is still loading. */
  hasConversations: boolean | null;
  /** True only when health data loaded and reports are confirmed present or absent. */
  reportsKnown: boolean;
  hasReports: boolean;
  /** Report ids on the current view that this member has not opened. */
  hasUnexploredReport: boolean;
  /** Previous completed visit, not the current page load. */
  previousVisitAt: string | null;
  now: string;
  /** Safe topic from a conversation in the last 7 days, or null. */
  recentTopic: string | null;
};

export type GreetingChoice = {
  id: GreetingId;
  heading: string;
  primary: string;
  supporting: string;
};

function daysBetween(earlier: string, later: string): number | null {
  const a = Date.parse(earlier);
  const b = Date.parse(later);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return (b - a) / 86_400_000;
}

export function selectGreeting(input: GreetingInput): GreetingChoice {
  const name = input.firstName?.trim() || null;
  const firstTime = input.hasConversations === false && input.previousVisitAt == null;
  let id: GreetingId = "returning";
  if (firstTime && input.reportsKnown && input.hasReports) id = "first_with_reports";
  else if (firstTime && input.reportsKnown && !input.hasReports) id = "no_reports";
  else if (!firstTime && input.reportsKnown && input.hasReports && input.hasUnexploredReport) id = "new_report";
  else if (!firstTime && input.previousVisitAt && (daysBetween(input.previousVisitAt, input.now) ?? 0) >= 30) id = "long_absence";
  else if (!firstTime && input.recentTopic) id = "continue_conversation";
  else if (!firstTime && input.reportsKnown && !input.hasReports) id = "no_reports";
  else id = "returning";
  const copy = GREETINGS[id];
  return {
    id,
    heading: copy.heading(name),
    primary: copy.primary,
    supporting: copy.supporting(input.recentTopic),
  };
}

/** A short, non-sensitive topic suitable for the landing screen. */
export function safeTopic(title: string | null | undefined): string | null {
  const text = (title || "").replace(/\s+/g, " ").trim();
  if (!text || text.length > 80 || SENSITIVE.test(text)) return null;
  if (/[?]/.test(text) || text.split(" ").length > 6) return null;
  const phrase = /^your\b/i.test(text) ? text : `your ${text.charAt(0).toLowerCase()}${text.slice(1)}`;
  return phrase;
}

export function recentSafeTopic(
  conversations: Array<{ title: string | null; updated_at: string }>,
  now: string,
): string | null {
  const sorted = [...conversations].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  for (const item of sorted) {
    const age = daysBetween(item.updated_at, now);
    if (age == null || age > 7) continue;
    const topic = safeTopic(item.title);
    if (topic) return topic;
  }
  return null;
}
