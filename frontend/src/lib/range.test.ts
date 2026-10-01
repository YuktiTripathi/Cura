import { describe, expect, it } from "vitest";
import { formatBounds, numericValue, rangeGeometry } from "./range";

describe("rangeGeometry", () => {
  it("places an in-range value inside the band", () => {
    const g = rangeGeometry(5.2, 4, 5.6)!;
    expect(g.relation).toBe("within");
    expect(g.position).toBeGreaterThan(g.bandStart);
    expect(g.position).toBeLessThan(g.bandEnd);
  });

  it("flags values above and below a two-sided range", () => {
    expect(rangeGeometry(142, 0, 100)!.relation).toBe("above");
    expect(rangeGeometry(18, 30, 100)!.relation).toBe("below");
    const above = rangeGeometry(142, 0, 100)!;
    expect(above.position).toBeGreaterThan(above.bandEnd);
  });

  it("handles one-sided ranges", () => {
    const upper = rangeGeometry(142, null, 100)!;
    expect(upper.relation).toBe("above");
    expect(upper.bandStart).toBe(0);
    const lower = rangeGeometry(38, 40, null)!;
    expect(lower.relation).toBe("below");
    expect(lower.bandEnd).toBe(100);
  });

  it("starts the track at zero for a range that starts at zero", () => {
    expect(rangeGeometry(138, 0, 100)!.bandStart).toBe(0);
    expect(rangeGeometry(41, 40, 60)!.bandStart).toBeGreaterThan(0);
  });

  it("keeps every coordinate on the track", () => {
    for (const g of [rangeGeometry(1000, 0, 1), rangeGeometry(-5, 0, 1), rangeGeometry(0.4, null, 1)]) {
      for (const n of [g!.position, g!.bandStart, g!.bandEnd]) {
        expect(n).toBeGreaterThanOrEqual(0);
        expect(n).toBeLessThanOrEqual(100);
      }
    }
  });

  it("returns null without a value or any bound, or with an inverted range", () => {
    expect(rangeGeometry(null, 0, 100)).toBeNull();
    expect(rangeGeometry(5, null, null)).toBeNull();
    expect(rangeGeometry(5, 10, 1)).toBeNull();
  });
});

describe("formatting", () => {
  it("formats bounds and parses values", () => {
    expect(formatBounds(4, 5.6, "%")).toBe("4–5.6 %");
    expect(formatBounds(null, 100, "mg/dL")).toBe("below 100 mg/dL");
    expect(formatBounds(40, null)).toBe("above 40");
    expect(numericValue({ value: "138.0" })).toBe(138);
    expect(numericValue({ value: "positive" })).toBeNull();
    expect(numericValue({ numeric_value: 5.6, value: "5.6" })).toBe(5.6);
  });
});
