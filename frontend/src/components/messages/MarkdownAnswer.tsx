import type { ReactNode } from "react";
import { displayAssistantText } from "../../types/chat";
import { debugMode } from "./debug";

/**
 * Renders the model's Markdown answer as written (plain response mode).
 *
 * Supports what a chat answer needs: paragraphs, **bold**, *italic*, short headings,
 * bullet and numbered lists, and small tables. Builds React elements only (no HTML
 * injection), and never restructures the answer.
 */
export function MarkdownAnswer({ content }: { content: string }) {
  const text = displayAssistantText(content, debugMode());
  return <div className="markdown-answer">{renderBlocks(text)}</div>;
}

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[]; start: number }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "p"; lines: string[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING = /^\s*(#{1,4})\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

export function parseMarkdown(text: string): Block[] {
  const normalized = (text || "").replace(/\r\n/g, "\n").replace(/([^\n])[ \t]+([-*•])[ \t]+/g, "$1\n$2 ");
  const lines = normalized.split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }
    const heading = line.match(HEADING);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2].trim() });
      i += 1;
      continue;
    }
    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1])) {
      const header = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW.test(lines[i])) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }
    if (BULLET.test(line)) {
      const items: string[] = [];
      while (i < lines.length && (BULLET.test(lines[i]) || isContinuation(lines[i], items))) {
        const match = lines[i].match(BULLET);
        if (match) items.push(match[1]);
        else items[items.length - 1] += ` ${lines[i].trim()}`;
        i += 1;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }
    if (NUMBERED.test(line)) {
      const items: string[] = [];
      const start = Number(line.match(NUMBERED)?.[1] || 1);
      while (i < lines.length && (NUMBERED.test(lines[i]) || isContinuation(lines[i], items))) {
        const match = lines[i].match(NUMBERED);
        if (match) items.push(match[2]);
        else items[items.length - 1] += `\n${lines[i].trim()}`;
        i += 1;
      }
      blocks.push({ kind: "ol", items, start });
      continue;
    }
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !HEADING.test(lines[i]) &&
      !BULLET.test(lines[i]) &&
      !NUMBERED.test(lines[i]) &&
      !(TABLE_ROW.test(lines[i]) && i + 1 < lines.length && TABLE_RULE.test(lines[i + 1]))
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push({ kind: "p", lines: para });
  }
  return blocks;
}

function isContinuation(line: string, items: string[]): boolean {
  // An indented line under a list item belongs to that item ("1. **Blood sugar**\n   Your HbA1c ...").
  return items.length > 0 && /^\s{2,}\S/.test(line);
}

function cells(row: string): string[] {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function renderBlocks(text: string): ReactNode {
  return parseMarkdown(text).map((block, index) => {
    switch (block.kind) {
      case "heading": {
        const Tag = (block.level <= 2 ? "h3" : "h4") as "h3" | "h4";
        return <Tag key={index}>{inline(block.text)}</Tag>;
      }
      case "ul":
        return (
          <ul key={index}>
            {block.items.map((item, k) => (
              <li key={k}>{withBreaks(item)}</li>
            ))}
          </ul>
        );
      case "ol":
        return (
          <ol key={index} start={block.start}>
            {block.items.map((item, k) => (
              <li key={k}>{withBreaks(item)}</li>
            ))}
          </ol>
        );
      case "table":
        return (
          <table key={index}>
            <thead>
              <tr>
                {block.header.map((cell, k) => (
                  <th key={k}>{inline(cell)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, k) => (
                    <td key={k}>{inline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        );
      default:
        return <p key={index}>{withBreaks(block.lines.join("\n"))}</p>;
    }
  });
}

function withBreaks(text: string): ReactNode {
  return text.split("\n").map((line, k) => (
    <span key={k}>
      {k > 0 ? <br /> : null}
      {inline(line.trim())}
    </span>
  ));
}

/** **bold** and *italic* only; everything else is literal text. */
export function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).filter((part) => part.length > 0);
  return parts.map((part, k) => {
    const bold = part.match(/^\*\*([^*]+)\*\*$/);
    if (bold) return <strong key={k}>{bold[1]}</strong>;
    const italic = part.match(/^\*([^*]+)\*$/);
    if (italic) return <em key={k}>{italic[1]}</em>;
    return <span key={k}>{part}</span>;
  });
}
