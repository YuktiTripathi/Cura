export type RangeRelation = "below" | "within" | "above" | "unknown";

export type RangeGeometry = {
  /** Value position along the track, 0–100. */
  position: number;
  /** Reference band along the track, 0–100. */
  bandStart: number;
  bandEnd: number;
  relation: RangeRelation;
};

/**
 * Lay a value out against its reference interval. Either bound may be missing ("< 100" or "> 40").
 * The track spans the band plus a margin, widened to include out-of-range values.
 */
export function rangeGeometry(
  value: number | null | undefined,
  low: number | null | undefined,
  high: number | null | undefined
): RangeGeometry | null {
  const hasLow = typeof low === "number" && Number.isFinite(low);
  const hasHigh = typeof high === "number" && Number.isFinite(high);
  if (typeof value !== "number" || !Number.isFinite(value) || (!hasLow && !hasHigh)) return null;
  if (hasLow && hasHigh && (low as number) > (high as number)) return null;

  let bandLo: number;
  let bandHi: number;
  if (hasLow && hasHigh) {
    bandLo = low as number;
    bandHi = high as number;
  } else if (hasHigh) {
    bandLo = Math.min(0, value);
    bandHi = high as number;
  } else {
    bandLo = low as number;
    bandHi = Math.max((low as number) * 2, value);
  }
  const span = Math.max(bandHi - bandLo, Math.abs(bandHi) * 0.1, 1e-9);
  const pad = span * 0.35;
  let min = Math.min(hasLow ? bandLo - pad : bandLo, value - span * 0.05);
  // Lab values are not negative: never draw track below zero when nothing on it is negative.
  if (bandLo >= 0 && value >= 0) min = Math.max(0, min);
  const max = Math.max(hasHigh ? bandHi + pad : bandHi, value + span * 0.05);
  const scale = (x: number) => Math.min(100, Math.max(0, ((x - min) / (max - min)) * 100));

  let relation: RangeRelation = "within";
  if (hasLow && value < (low as number)) relation = "below";
  else if (hasHigh && value > (high as number)) relation = "above";

  return {
    position: scale(value),
    bandStart: hasLow ? scale(bandLo) : 0,
    bandEnd: hasHigh ? scale(bandHi) : 100,
    relation,
  };
}

export function formatBounds(low: number | null | undefined, high: number | null | undefined, unit?: string | null): string {
  const u = unit ? ` ${unit}` : "";
  const hasLow = typeof low === "number";
  const hasHigh = typeof high === "number";
  if (hasLow && hasHigh) return `${fmt(low as number)}–${fmt(high as number)}${u}`;
  if (hasHigh) return `below ${fmt(high as number)}${u}`;
  if (hasLow) return `above ${fmt(low as number)}${u}`;
  return "";
}

export function fmt(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Number(n.toFixed(2)));
}

/** A numeric value for a finding: the backend's numeric_value, else a plain number in the value text. */
export function numericValue(finding: { numeric_value?: number | null; value?: string | null }): number | null {
  if (typeof finding.numeric_value === "number") return finding.numeric_value;
  const parsed = Number(finding.value);
  return finding.value != null && finding.value.trim() !== "" && Number.isFinite(parsed) ? parsed : null;
}
