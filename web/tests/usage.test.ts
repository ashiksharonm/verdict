import { describe, expect, it } from "vitest";
import { normaliseUsage } from "../src/lib/api";

describe("normaliseUsage", () => {
  it("reads the API's `quota` field as the monthly quota", () => {
    const u = normaliseUsage({ days: [{ day: "2026-10-18", count: 3 }], month_total: 3, quota: 10000 });
    expect(u).toEqual({ days: [{ day: "2026-10-18", count: 3 }], month_total: 3, monthly_quota: 10000 });
  });

  it("never leaves fields undefined", () => {
    expect(normaliseUsage({})).toEqual({ days: [], month_total: 0, monthly_quota: 0 });
  });
});
