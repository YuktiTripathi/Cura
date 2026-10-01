export type TrendPoint = { date: string; value: number; status?: string };

export type TrendLayout = {
  width: number;
  height: number;
  plot: { left: number; right: number; top: number; bottom: number };
  points: Array<TrendPoint & { x: number; y: number; outOfRange: boolean }>;
  /** Reference band in plot pixels; null when the marker has no range. */
  band: { top: number; bottom: number } | null;
  yTicks: Array<{ value: number; y: number }>;
};

const W = 340;
const H = 170;
const PLOT = { left: 40, right: 12, top: 12, bottom: 26 };

/** Pixel layout for a single-series trend with an optional reference band. Dates are spaced by time. */
export function trendLayout(points: TrendPoint[], low?: number | null, high?: number | null): TrendLayout | null {
  const sorted = [...points].sort((a, b) => a.date.localeCompare(b.date));
  if (sorted.length < 2) return null;
  const values = sorted.map((p) => p.value);
  const hasLow = typeof low === "number";
  const hasHigh = typeof high === "number";
  let min = Math.min(...values, ...(hasLow ? [low as number] : []), ...(hasHigh && !hasLow ? [0] : []));
  let max = Math.max(...values, ...(hasHigh ? [high as number] : []));
  if (max === min) {
    max += 1;
    min -= 1;
  }
  const pad = (max - min) * 0.12;
  min = min >= 0 && min - pad < 0 ? 0 : min - pad;
  max += pad;

  const times = sorted.map((p) => Date.parse(`${p.date.slice(0, 10)}T00:00:00Z`));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const x = (t: number, index: number) =>
    PLOT.left +
    (t1 > t0 ? (t - t0) / (t1 - t0) : index / (sorted.length - 1)) * (W - PLOT.left - PLOT.right);
  const y = (v: number) => PLOT.top + (1 - (v - min) / (max - min)) * (H - PLOT.top - PLOT.bottom);

  const outside = (v: number) => (hasLow && v < (low as number)) || (hasHigh && v > (high as number));
  const ticks = [min, (min + max) / 2, max].map((value) => ({ value, y: y(value) }));
  return {
    width: W,
    height: H,
    plot: PLOT,
    points: sorted.map((p, i) => ({ ...p, x: x(times[i], i), y: y(p.value), outOfRange: outside(p.value) })),
    band:
      hasLow || hasHigh
        ? { top: y(hasHigh ? (high as number) : max), bottom: y(hasLow ? (low as number) : min) }
        : null,
    yTicks: ticks,
  };
}

export function niceNumber(n: number): string {
  const abs = Math.abs(n);
  const digits = abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return String(Number(n.toFixed(digits)));
}
