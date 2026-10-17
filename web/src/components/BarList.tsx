type Row = { label: string; value: number; lo?: number; hi?: number; highlight?: boolean };

/** Horizontal bar chart in plain HTML: values are always printed, so it works without colour or a mouse. */
export default function BarList({ title, rows, max = 1 }: { title: string; rows: Row[]; max?: number }) {
  return (
    <figure className="rounded-lg border border-border bg-card p-4">
      <figcaption className="mb-3 text-sm font-semibold">{title}</figcaption>
      <ul className="space-y-2" aria-label={title}>
        {rows.map((r) => (
          <li key={r.label} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-2 text-xs sm:grid-cols-[minmax(0,14rem)_1fr_auto] sm:text-sm">
            <span className={`truncate ${r.highlight ? "font-semibold" : "text-muted"}`} title={r.label}>
              {r.label}
            </span>
            <span className="relative block h-3 rounded bg-code" aria-hidden="true">
              <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${Math.max(0, Math.min(1, r.value / max)) * 100}%`, background: r.highlight ? "var(--accent)" : "var(--bar-other)" }} />
              {r.lo !== undefined && r.hi !== undefined && (
                <span className="absolute top-1/2 h-px bg-fg" style={{ left: `${(r.lo / max) * 100}%`, width: `${((r.hi - r.lo) / max) * 100}%` }} />
              )}
            </span>
            <span className="tabular-nums">
              {r.value.toFixed(3)}
              {r.lo !== undefined && r.hi !== undefined && <span className="hidden text-muted sm:inline"> [{r.lo.toFixed(3)}, {r.hi.toFixed(3)}]</span>}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
