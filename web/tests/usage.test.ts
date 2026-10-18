import { describe, expect, it } from "vitest";
import { normaliseUsage } from "../src/lib/api";

describe("normaliseUsage", () => {
  it("reads the API's `quota` field as the monthly quota", () => {
    const u = normaliseUsage({ days: [{ day: "2026-10-18", count: 3 }], month_total: 3, quota: 10000 });
    expect(u).toEqual({ days: [{ day: "2026-10-18", count: 3 }], month_total: 3, monthly_quota: 10000, month: "", keys: [] });
  });

  it("never leaves fields undefined", () => {
    expect(normaliseUsage({})).toEqual({ days: [], month_total: 0, monthly_quota: 0, month: "", keys: [] });
  });

  it("keeps month and per-key usage", () => {
    const keys = [{ id: "k1", name: "ci", prefix: "vk_ab", month_count: 12, quota: 10000 }];
    const u = normaliseUsage({ month: "2026-10", keys, quota: 10000 });
    expect(u.month).toBe("2026-10");
    expect(u.keys).toEqual(keys);
  });
});
