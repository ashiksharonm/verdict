import type { ApiKey, Usage } from "./api";
import { localDateKey } from "./usage";

/** Dev-only fixtures for `?preview=1`; see previewEnabled(). */
export function previewData(kind: string | null, now = new Date()): { keys: ApiKey[]; usage: Usage } {
  const day = (back: number) => localDateKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - back));
  const days =
    kind === "one"
      ? [{ day: day(0), count: 187 }]
      : [
          23, 41, 0, 0, 58, 92, 130, 76, 0, 12, 64, 88, 143, 210, 175, 0, 31, 97, 154, 188, 236, 202, 0, 45, 118, 160, 221, 194, 149, 187,
        ].map((count, i, a) => ({ day: day(a.length - 1 - i), count }));
  const monthKey = day(0).slice(0, 7);
  const month_total = days.filter((d) => d.day.startsWith(monthKey)).reduce((s, d) => s + d.count, 0);
  const keys: ApiKey[] = [
    { id: "k1", name: "production", prefix: "vk_7fQ2", created_at: day(20) + "T10:00:00Z", last_used_at: null },
    { id: "k2", name: "ci", prefix: "vk_Hx9d", created_at: day(6) + "T10:00:00Z", last_used_at: null },
    { id: "k3", name: "old-laptop", prefix: "vk_0aBc", created_at: day(40) + "T10:00:00Z", revoked_at: day(12) + "T10:00:00Z" },
  ];
  const split = [0.7, 0.3];
  return {
    keys,
    usage: {
      month: monthKey,
      days,
      month_total,
      monthly_quota: 10000,
      keys: keys.slice(0, 2).map((k, i) => ({ id: k.id, name: k.name, prefix: k.prefix, month_count: Math.round(month_total * split[i]), quota: 10000 })),
    },
  };
}
