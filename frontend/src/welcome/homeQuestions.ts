import type { Finding } from "../types/unifiedHealth";
import { QUESTIONS_WITH_REPORTS, QUESTIONS_WITHOUT_REPORTS } from "./greetings";

function findingQuestion(findings: Finding[]): string | null {
  const finding = findings.find((item) => item.name && item.name.trim().split(/\s+/).length <= 5);
  if (!finding) return null;
  const name = finding.name.trim();
  return `What does my ${name.charAt(0).toLowerCase()}${name.slice(1)} result mean?`;
}

export function homeQuestions(reportsKnown: boolean, hasReports: boolean, findings: Finding[]): string[] {
  if (!reportsKnown || !hasReports) return QUESTIONS_WITHOUT_REPORTS.slice(0, 4);
  const personal = findingQuestion(findings);
  return [...QUESTIONS_WITH_REPORTS, ...(personal ? [personal] : [])].slice(0, 4);
}
