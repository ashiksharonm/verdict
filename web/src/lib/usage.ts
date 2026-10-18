/** Pure helpers for the dashboard usage chart and stat tiles. */

export type DayCount = { day: string; count: number };

const pad = (n: number) => String(n).padStart(2, "0");

/** YYYY-MM-DD in the viewer's local time zone. */
export function localDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** The last `n` calendar days ending at `today` (local), oldest first. Missing days are filled with 0. */
export function lastNDays(days: DayCount[], today: Date, n = 30): DayCount[] {
  const byDay = new Map<string, number>();
  for (const d of days) byDay.set(d.day, (byDay.get(d.day) ?? 0) + Number(d.count || 0));
  const out: DayCount[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
    const key = localDateKey(d);
    out.push({ day: key, count: byDay.get(key) ?? 0 });
  }
  return out;
}

/** "Oct 18" for a YYYY-MM-DD key. */
export function shortDay(key: string): string {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Up to ~`count` round tick values from 0 to a nice maximum >= max. */
export function niceTicks(max: number, count = 3): number[] {
  if (!(max > 0)) return [0, 1, 2, 3].slice(0, count);
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((s) => s >= raw) ?? 10 * mag;
  const ticks: number[] = [];
  for (let v = 0; v <= max + step - 1e-9; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  return ticks;
}

/** Linear month-end estimate from the month-to-date total and the local day-of-month. */
export function projectMonthEnd(monthTotal: number, today: Date): number {
  const daysInMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  return Math.round((monthTotal / Math.max(1, today.getDate())) * daysInMonth);
}

export const sumCounts = (days: DayCount[]) => days.reduce((a, d) => a + d.count, 0);
