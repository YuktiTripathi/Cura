import { useState, type ReactNode } from "react";
import type { BlockItem, ResolvedValue, ResponseBlock, ResponseSource, SemanticResponse } from "../../types/semantic";
import { MarkdownAnswer } from "./MarkdownAnswer";
import { RangeBar } from "./RangeBar";

/**
 * Generic renderer for CURA's semantic response: summary first, then 0..n optional blocks.
 * Presentation only: no medical decisions, no values that the backend did not send, and
 * unknown block types render nothing (the summary always stands alone).
 */
export function SemanticAnswer({ response }: { response: SemanticResponse }) {
  return (
    <div className="semantic-answer">
      <MarkdownAnswer content={response.summary} />
      {response.blocks.map((block, index) => (
        <Block key={index} block={block} />
      ))}
      <Sources sources={response.sources} />
    </div>
  );
}

export function Block({ block }: { block: ResponseBlock }) {
  switch (block.type) {
    case "text":
      return <Section block={block}>{block.text ? <MarkdownAnswer content={block.text} /> : null}</Section>;
    case "metric":
    case "metric_group":
      return <MetricGroup block={block} />;
    case "risk":
      return (
        <Section block={block} tone="risk">
          <ul className="sem-risks">
            {(block.values || []).map((v) => (
              <li key={v.key}>
                <span className="sem-label">{v.label}</span>
                <StatusPill status={v.status} />
                {v.value != null ? <span className="sem-muted">score {String(v.value)}</span> : null}
              </li>
            ))}
          </ul>
          {block.text ? <MarkdownAnswer content={block.text} /> : null}
        </Section>
      );
    case "comparison":
      return (
        <Section block={block}>
          <ul className="sem-compare">
            {(block.values || []).map((v) => (
              <li key={v.key}>
                <span className="sem-label">{v.label}</span>
                <span>
                  {fmtValue(v.previous, v.unit)} <span aria-hidden="true">→</span>
                  <span className="sr-only"> to </span> <strong>{fmtValue(v.value, v.unit)}</strong>
                </span>
                {v.direction ? <span className="sem-muted">{v.direction}</span> : null}
              </li>
            ))}
          </ul>
          {block.text ? <MarkdownAnswer content={block.text} /> : null}
        </Section>
      );
    case "insight":
    case "reassurance":
    case "warning":
      return (
        <Section block={block} tone={block.type}>
          {block.text ? <MarkdownAnswer content={block.text} /> : null}
          <ValueChips values={block.values} />
        </Section>
      );
    case "priority_list":
    case "action_list":
      return (
        <Section block={block}>
          {block.text ? <MarkdownAnswer content={block.text} /> : null}
          <List items={block.items || []} ordered={block.type === "priority_list"} />
        </Section>
      );
    case "nutrition":
      return (
        <Section block={block}>
          <div className="sem-nutrition">
            {block.increase?.length ? <FoodList label="More of" items={block.increase} /> : null}
            {block.reduce?.length ? <FoodList label="Less of" items={block.reduce} /> : null}
          </div>
          {block.text ? <MarkdownAnswer content={block.text} /> : null}
        </Section>
      );
    default:
      return null;
  }
}

function Section({ block, tone, children }: { block: ResponseBlock; tone?: string; children: ReactNode }) {
  return (
    <section className={`sem-block sem-${block.type}${tone ? ` sem-tone-${tone}` : ""}`} aria-label={block.title || undefined}>
      {block.title ? <h4 className="sem-title">{block.title}</h4> : null}
      {children}
    </section>
  );
}

function MetricGroup({ block }: { block: ResponseBlock }) {
  const [open, setOpen] = useState(!block.collapsed);
  const values = block.values || [];
  if (block.collapsed) {
    return (
      <section className="sem-block sem-metric_group">
        <button type="button" className="sem-toggle" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          {open ? "Hide" : "Show"} {block.title || `all ${values.length} results`}
        </button>
        {open ? <Metrics values={values} /> : null}
      </section>
    );
  }
  return (
    <Section block={block}>
      <Metrics values={values} />
      {block.text ? <MarkdownAnswer content={block.text} /> : null}
    </Section>
  );
}

function Metrics({ values }: { values: ResolvedValue[] }) {
  return (
    <ul className="sem-metrics">
      {values.map((v) => (
        <li key={v.key} className="sem-metric">
          <div className="sem-metric-head">
            <span className="sem-label">{v.label}</span>
            <strong>{fmtValue(v.value, v.unit)}</strong>
            <StatusPill status={v.status} />
          </div>
          {typeof v.value === "number" && (v.reference_low != null || v.reference_high != null) ? (
            <RangeBar label={v.label} value={v.value} unit={v.unit} low={v.reference_low} high={v.reference_high} />
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function List({ items, ordered }: { items: BlockItem[]; ordered: boolean }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className="sem-list">
      {items.map((item, i) => (
        <li key={i}>
          {item.title ? <strong>{item.title}</strong> : null}
          {item.text ? <MarkdownAnswer content={item.text} /> : null}
          <ValueChips values={item.values} />
        </li>
      ))}
    </Tag>
  );
}

function ValueChips({ values }: { values?: ResolvedValue[] }) {
  if (!values?.length) return null;
  return (
    <ul className="sem-chips" aria-label="Values">
      {values.map((v) => (
        <li key={v.key} className={`sem-chip sem-status-${(v.status || "unknown").toLowerCase()}`}>
          {v.label} {v.kind === "bio_ai" ? (v.status ?? "") : fmtValue(v.value, v.unit)}
          {v.kind === "blood" && v.status && v.status !== "normal" ? ` (${v.status})` : ""}
        </li>
      ))}
    </ul>
  );
}

function FoodList({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="sem-muted">{label}</p>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function StatusPill({ status }: { status?: string | null }) {
  if (!status) return null;
  return <span className={`sem-pill sem-status-${status.toLowerCase().replace(/\s+/g, "-")}`}>{status}</span>;
}

const SOURCE_LABEL: Record<ResponseSource["type"], string> = {
  blood_report: "Blood report",
  bio_ai: "Bio-AI assessment",
  questionnaire: "Health questionnaire",
  uploaded_document: "Uploaded document",
  medical_reference: "Medical reference",
};

function Sources({ sources }: { sources: ResponseSource[] }) {
  if (!sources?.length) return null;
  return (
    <details className="sem-sources">
      <summary>Sources ({sources.length})</summary>
      <ul>
        {sources.map((s, i) => (
          <li key={i}>
            {s.label || SOURCE_LABEL[s.type] || s.type}
            {s.date ? <span className="sem-muted"> · {s.date}</span> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

function fmtValue(value: number | string | null | undefined, unit?: string | null): string {
  if (value == null || value === "") return "—";
  const u = unit ? (unit.trim() === "%" ? "%" : ` ${unit}`) : "";
  return `${value}${u}`;
}
