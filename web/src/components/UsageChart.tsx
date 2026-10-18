"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { niceTicks, shortDay, type DayCount } from "@/lib/usage";

const H = 200;
const M = { top: 10, right: 14, bottom: 26, left: 40 };

/** Bar chart over a fixed window of days (oldest first, zero-filled). Today is the last bar. */
export default function UsageChart({ days }: { days: DayCount[] }) {
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(640);
  const [active, setActive] = useState<number | null>(null);
  const [focusIdx, setFocusIdx] = useState(days.length - 1);
  const bars = useRef<(SVGRectElement | null)[]>([]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(260, Math.round(el.clientWidth))));
    ro.observe(el);
    setW(Math.max(260, Math.round(el.clientWidth)));
    return () => ro.disconnect();
  }, []);

  const n = days.length;
  const peak = Math.max(0, ...days.map((d) => d.count));
  const ticks = useMemo(() => niceTicks(peak), [peak]);
  const top = ticks[ticks.length - 1];
  const pw = w - M.left - M.right;
  const ph = H - M.top - M.bottom;
  const slot = pw / n;
  const bw = Math.max(3, Math.min(14, slot * 0.6));
  const y = (v: number) => M.top + ph - (v / top) * ph;
  const cx = (i: number) => M.left + slot * i + slot / 2;
  const empty = peak === 0;

  const tipI = active;
  const tip = tipI != null ? days[tipI] : null;
  const tipX = tipI != null ? cx(tipI) : 0;

  return (
    <div ref={box} className="relative" onPointerLeave={() => setActive(null)}>
      <svg width={w} height={H} role="group" aria-label={`Checks per day, last ${n} days, peak ${peak}. Use left and right arrow keys to read each day.`} className="block overflow-visible">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={w - M.right} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth={1} strokeDasharray={t === 0 ? undefined : "2 3"} />
            <text x={M.left - 8} y={y(t)} textAnchor="end" dominantBaseline="central" fontSize={11} fill="var(--muted)" className="tabular-nums">{t.toLocaleString("en-US")}</text>
          </g>
        ))}
        <line x1={M.left} x2={w - M.right} y1={y(0)} y2={y(0)} stroke="var(--muted)" strokeWidth={1} />
        {days.map((d, i) => {
          const isToday = i === n - 1;
          const h = d.count > 0 ? Math.max(2, y(0) - y(d.count)) : 0;
          const hot = active === i;
          return (
            <g key={d.day}>
              {h > 0 && (
                <rect
                  x={cx(i) - bw / 2}
                  y={y(0) - h}
                  width={bw}
                  height={h}
                  rx={Math.min(3, bw / 2)}
                  fill="var(--accent)"
                  opacity={isToday || hot ? 1 : 0.55}
                />
              )}
              <rect
                ref={(el) => {
                  bars.current[i] = el;
                }}
                x={M.left + slot * i}
                y={M.top}
                width={slot}
                height={ph}
                fill="transparent"
                tabIndex={i === focusIdx ? 0 : -1}
                role="img"
                aria-label={`${shortDay(d.day)}${isToday ? " (today)" : ""}: ${d.count} checks`}
                className="outline-none focus-visible:[stroke:var(--accent)] focus-visible:[stroke-width:2]"
                onPointerEnter={() => setActive(i)}
                onFocus={() => {
                  setActive(i);
                  setFocusIdx(i);
                }}
                onBlur={() => setActive(null)}
                onKeyDown={(e) => {
                  const next = e.key === "ArrowRight" ? Math.min(n - 1, i + 1) : e.key === "ArrowLeft" ? Math.max(0, i - 1) : e.key === "Home" ? 0 : e.key === "End" ? n - 1 : null;
                  if (next == null) return;
                  e.preventDefault();
                  setFocusIdx(next);
                  bars.current[next]?.focus();
                }}
              />
            </g>
          );
        })}
        {days.map((d, i) =>
          (n - 1 - i) % 7 === 0 ? (
            <text key={d.day} x={cx(i)} y={H - 6} textAnchor="middle" fontSize={11} fill={i === n - 1 ? "var(--ink)" : "var(--muted)"} fontWeight={i === n - 1 ? 600 : 400}>
              {i === n - 1 ? "Today" : shortDay(d.day)}
            </text>
          ) : null,
        )}
        {empty && (
          <text x={M.left + pw / 2} y={M.top + ph / 2 - 6} textAnchor="middle" fontSize={13} fill="var(--muted)">No checks in the last {n} days yet</text>
        )}
      </svg>
      {tip && (
        <div
          role="status"
          className="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs shadow-lg"
          style={{ left: Math.min(Math.max(tipX, 70), w - 70), top: M.top - 4, transform: "translate(-50%, -100%)" }}
        >
          {shortDay(tip.day)} <span aria-hidden>·</span> <strong className="font-semibold">{tip.count.toLocaleString("en-US")} {tip.count === 1 ? "check" : "checks"}</strong>
        </div>
      )}
    </div>
  );
}
