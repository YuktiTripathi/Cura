import type { EvidenceItem } from "../types/chat";

export type SourceItem = {
  label: string;
  value: number | null;
  unit: string | null;
  referenceRange: string | null;
  excerpt: string | null;
};

export type SourceGroup = {
  key: string;
  kind: "report" | "document";
  title: string;
  /** Uploaded documents only. */
  documentId?: string;
  page?: number;
  items: SourceItem[];
};

const REPORT_TITLES: Record<string, string> = {
  blood_report: "Blood report",
  bio_ai_report: "Bio-AI assessment",
  questionnaire: "Health questionnaire",
};

/**
 * Group an answer's evidence by where it came from: one group per record (report + date) or per
 * uploaded document page. Titles never contain internal ids. Evidence with nothing to show
 * (no measured item and no document page) is left out.
 */
export function groupEvidence(evidence: EvidenceItem[] | undefined): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const item of evidence || []) {
    const isDocument = item.source === "user_uploaded" && item.document_id && item.page_start;
    const key = isDocument ? `doc:${item.document_id}:${item.page_start}` : `report:${item.report_type}:${item.report_date}`;
    if (!isDocument && !item.marker) continue;
    let group = groups.get(key);
    if (!group) {
      group = isDocument
        ? {
            key,
            kind: "document",
            title: `${item.filename || "Uploaded report"} · page ${item.page_start}`,
            documentId: item.document_id!,
            page: item.page_start!,
            items: [],
          }
        : { key, kind: "report", title: reportTitle(item), items: [] };
      groups.set(key, group);
    }
    if (item.marker || item.excerpt) {
      group.items.push({
        label: item.marker || "Quoted text",
        value: item.value ?? null,
        unit: item.unit ?? null,
        referenceRange: item.reference_range ?? null,
        excerpt: isDocument ? item.excerpt ?? null : null,
      });
    }
  }
  return Array.from(groups.values());
}

function reportTitle(item: EvidenceItem): string {
  const name = REPORT_TITLES[item.report_type] || "Health record";
  const date = new Date(`${(item.report_date || "").slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return name;
  return `${name} · ${date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`;
}

/** Lines of a page that quote one of the excerpts (whole-line match, then containment). */
export function highlightedLines(pageText: string, excerpts: string[]): Set<number> {
  const wanted = excerpts.map((e) => e.trim()).filter(Boolean);
  const out = new Set<number>();
  pageText.split("\n").forEach((line, index) => {
    const text = line.trim();
    if (text && wanted.some((excerpt) => text === excerpt || (excerpt.length >= 6 && text.includes(excerpt)))) out.add(index);
  });
  return out;
}
