import { describe, expect, it } from "vitest";
import { trendLayout } from "./trend";

describe("trendLayout", () => {
  it("needs at least two points", () => {
    expect(trendLayout([{ date: "2026-08-18", value: 1 }])).toBeNull();
  });

  it("spaces points by date and keeps them inside the plot", () => {
    const layout = trendLayout(
      [
        { date: "2026-08-18", value: 138 },
        { date: "2026-01-10", value: 150 },
        { date: "2026-07-09", value: 142 },
      ],
      0,
      100
    )!;
    expect(layout.points.map((p) => p.date)).toEqual(["2026-01-10", "2026-07-09", "2026-08-18"]);
    const [a, b, c] = layout.points.map((p) => p.x);
    expect(b - a).toBeGreaterThan(c - b); // Jan→Jul is a longer gap than Jul→Aug
    for (const p of layout.points) {
      expect(p.x).toBeGreaterThanOrEqual(layout.plot.left);
      expect(p.x).toBeLessThanOrEqual(layout.width - layout.plot.right);
      expect(p.y).toBeGreaterThanOrEqual(layout.plot.top);
      expect(p.y).toBeLessThanOrEqual(layout.height - layout.plot.bottom);
    }
  });

  it("marks out-of-range points and draws the reference band", () => {
    const layout = trendLayout(
      [
        { date: "2026-07-09", value: 18 },
        { date: "2026-08-18", value: 42 },
      ],
      30,
      100
    )!;
    expect(layout.points.map((p) => p.outOfRange)).toEqual([true, false]);
    expect(layout.band).not.toBeNull();
    expect(layout.band!.top).toBeLessThan(layout.band!.bottom);
    // The higher value sits higher on screen.
    expect(layout.points[1].y).toBeLessThan(layout.points[0].y);
  });

  it("has no band without a range", () => {
    expect(
      trendLayout([
        { date: "2026-07-09", value: 2 },
        { date: "2026-08-18", value: 2.4 },
      ])!.band
    ).toBeNull();
  });
});
