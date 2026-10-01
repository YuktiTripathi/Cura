import { fmt, formatBounds, rangeGeometry, type RangeRelation } from "../../lib/range";

const RELATION_TEXT: Record<Exclude<RangeRelation, "unknown">, { icon: string; label: string }> = {
  below: { icon: "▼", label: "Below range" },
  within: { icon: "✓", label: "Within range" },
  above: { icon: "▲", label: "Above range" },
};

/**
 * A lab value against its report's reference interval. The band is the reference range; the dot
 * is the value. Status is always spelled out in text next to the icon, never colour alone.
 */
export function RangeBar({
  label,
  value,
  unit,
  low,
  high,
}: {
  label: string;
  value: number | null;
  unit?: string | null;
  low?: number | null;
  high?: number | null;
}) {
  const g = rangeGeometry(value, low, high);
  if (!g || value == null) return null;
  const relation = RELATION_TEXT[g.relation as Exclude<RangeRelation, "unknown">];
  const bounds = formatBounds(low, high, unit);
  const description = `${label} ${fmt(value)}${unit ? ` ${unit}` : ""}: ${relation.label.toLowerCase()} (reference ${bounds}).`;
  return (
    <div className="range" data-relation={g.relation}>
      <div className="range-track" role="img" aria-label={description} title={description}>
        <span className="range-band" style={{ left: `${g.bandStart}%`, width: `${g.bandEnd - g.bandStart}%` }} />
        <span className="range-dot" style={{ left: `${g.position}%` }} />
      </div>
      <div className="range-meta">
        <span className="range-status">
          <span aria-hidden="true">{relation.icon}</span> {relation.label}
        </span>
        <span className="range-bounds">Ref {bounds}</span>
      </div>
    </div>
  );
}
