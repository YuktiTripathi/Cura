import { useState } from "react";
import { niceNumber, trendLayout, type TrendPoint } from "../../lib/trend";
import { t } from "../../i18n";

/** One marker over time against its reference band. Hover or focus a point for its value. */
export function TrendChart({
  label,
  unit,
  points,
  low,
  high,
}: {
  label: string;
  unit?: string | null;
  points: TrendPoint[];
  low?: number | null;
  high?: number | null;
}) {
  const layout = trendLayout(points, low, high);
  const [active, setActive] = useState<number | null>(null);
  if (!layout) return null;
  const { plot, width, height } = layout;
  const first = layout.points[0];
  const last = layout.points[layout.points.length - 1];
  const path = layout.points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const summary = `${label} from ${niceNumber(first.value)} on ${shortDate(first.date)} to ${niceNumber(last.value)}${
    unit ? ` ${unit}` : ""
  } on ${shortDate(last.date)}, ${layout.points.length} results.`;
  const hover = active != null ? layout.points[active] : null;

  return (
    <figure className="trend" data-testid="trend-chart">
      <div className="trend-plot">
        <svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={summary} onMouseLeave={() => setActive(null)}>
          {layout.yTicks.map((tick) => (
            <g key={tick.value} className="trend-grid" aria-hidden="true">
              <line x1={plot.left} x2={width - plot.right} y1={tick.y} y2={tick.y} />
              <text x={plot.left - 6} y={tick.y} dy="0.32em" textAnchor="end">
                {niceNumber(tick.value)}
              </text>
            </g>
          ))}
          {layout.band ? (
            <rect
              className="trend-band"
              x={plot.left}
              width={width - plot.left - plot.right}
              y={layout.band.top}
              height={Math.max(0, layout.band.bottom - layout.band.top)}
              rx={4}
            />
          ) : null}
          {hover ? <line className="trend-crosshair" x1={hover.x} x2={hover.x} y1={plot.top} y2={height - plot.bottom} /> : null}
          <path className="trend-line" d={path} />
          {layout.points.map((p, i) => (
            <g key={p.date}>
              <circle
                className={`trend-point${p.outOfRange ? " out" : ""}${i === active ? " active" : ""}`}
                cx={p.x}
                cy={p.y}
                r={i === active ? 6 : 4.5}
              />
              <rect
                className="trend-hit"
                x={p.x - 16}
                y={plot.top}
                width={32}
                height={height - plot.top - plot.bottom}
                tabIndex={0}
                role="img"
                aria-label={`${shortDate(p.date)}: ${niceNumber(p.value)}${unit ? ` ${unit}` : ""}${p.outOfRange ? ", outside range" : ""}`}
                onMouseEnter={() => setActive(i)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
              />
            </g>
          ))}
          <text className="trend-axis" x={first.x} y={height - 6} textAnchor="start" aria-hidden="true">
            {shortDate(first.date)}
          </text>
          <text className="trend-axis" x={last.x} y={height - 6} textAnchor="end" aria-hidden="true">
            {shortDate(last.date)}
          </text>
        </svg>
        {hover ? (
          <div
            className="trend-tooltip"
            role="status"
            data-align={hover.x < width * 0.3 ? "start" : hover.x > width * 0.7 ? "end" : "center"}
            style={{ left: `${(hover.x / width) * 100}%`, top: `${(hover.y / height) * 100}%` }}
          >
            <strong>
              {niceNumber(hover.value)}
              {unit ? ` ${unit}` : ""}
            </strong>
            <span>{shortDate(hover.date)}</span>
            {hover.outOfRange ? <span>{t("ui.TrendChart.outside_reference_range", "Outside reference range")}</span> : null}
          </div>
        ) : null}
      </div>
      {layout.band ? (
        <figcaption className="trend-legend">
          <span className="trend-legend-band" aria-hidden="true" /> Reference range
        </figcaption>
      ) : null}
    </figure>
  );
}

export function shortDate(iso: string): string {
  const date = new Date(`${iso.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
