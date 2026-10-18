import { describe, expect, it } from "vitest";
import { lastNDays, localDateKey, niceTicks, projectMonthEnd, shortDay, sumCounts } from "../src/lib/usage";

const today = new Date(2026, 9, 18, 15, 30); // Oct 18, local

describe("lastNDays", () => {
  it("returns 30 consecutive days ending today, oldest first", () => {
    const out = lastNDays([], today);
    expect(out).toHaveLength(30);
    expect(out[29].day).toBe("2026-10-18");
    expect(out[0].day).toBe("2026-09-19");
    expect(out.every((d) => d.count === 0)).toBe(true);
  });
  it("fills missing days with zero and keeps known counts", () => {
    const out = lastNDays([{ day: "2026-10-18", count: 187 }, { day: "2026-08-01", count: 9 }], today);
    expect(out[29].count).toBe(187);
    expect(sumCounts(out)).toBe(187); // out-of-window day ignored
  });
  it("crosses month and year boundaries", () => {
    const out = lastNDays([], new Date(2027, 0, 2), 5);
    expect(out.map((d) => d.day)).toEqual(["2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02"]);
  });
});

describe("helpers", () => {
  it("formats keys and labels", () => {
    expect(localDateKey(new Date(2026, 0, 5))).toBe("2026-01-05");
    expect(shortDay("2026-10-04")).toBe("Oct 4");
  });
  it("niceTicks starts at 0 and covers max", () => {
    for (const max of [1, 7, 187, 940, 12345]) {
      const t = niceTicks(max);
      expect(t[0]).toBe(0);
      expect(t[t.length - 1]).toBeGreaterThanOrEqual(max);
      expect(t.length).toBeLessThanOrEqual(6);
    }
    expect(niceTicks(187)).toEqual([0, 100, 200]);
  });
  it("projects the month end linearly", () => {
    expect(projectMonthEnd(180, today)).toBe(310); // 10/day * 31
  });
});
