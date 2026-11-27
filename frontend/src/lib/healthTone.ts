export type MeasuredTone = "within" | "above" | "below" | "unknown";
export type BioTone = "healthy" | "increased" | "high" | "very_high" | "unknown";

export function measuredTone(status?: string | null): MeasuredTone {
  const text = (status || "").toLowerCase();
  if (text.includes("within") || text === "normal") return "within";
  if (text.includes("below") || text.includes("low")) return "below";
  if (text.includes("above") || text.includes("high") || text.includes("critical")) return "above";
  return "unknown";
}

export function bioTone(classification?: string | null, name?: string | null): BioTone {
  if (/metabolic age/i.test(name || "")) return "unknown";
  const text = (classification || "").toLowerCase();
  if (text.includes("very high")) return "very_high";
  if (text.includes("increased")) return "increased";
  if (/\bhigh\b/.test(text)) return "high";
  if (text.includes("healthy") || text.includes("low risk")) return "healthy";
  return "unknown";
}

export function toneArrow(tone: MeasuredTone): string {
  if (tone === "above") return "↑";
  if (tone === "below") return "↓";
  return "";
}
