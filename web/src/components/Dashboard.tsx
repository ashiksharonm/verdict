"use client";
import { Activity, CalendarDays, ChartColumn, FileText, FlaskConical, Gauge, KeyRound, Layers, LogOut, Plus, Terminal, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import CopyButton from "./CopyButton";
import { useToast } from "./Toast";
import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, createKey, getUsage, listKeys, revokeKey, type ApiKey, type NewApiKey, type Usage } from "@/lib/api";
import { API_URL, supabaseConfigured } from "@/lib/config";
import { lastNDays, projectMonthEnd, sumCounts } from "@/lib/usage";
import { previewEnabled } from "@/lib/useAuth";
import UsageChart from "./UsageChart";
import { getSupabase } from "@/lib/supabase";

type State = { status: "loading" } | { status: "anon" } | { status: "ready"; token: string; email: string };

export default function Dashboard() {
  const [state, setState] = useState<State>({ status: "loading" });
  const supabase = getSupabase();

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" && previewEnabled()) {
      setState({ status: "ready", token: "preview", email: "ashik.sharon@example.com" });
      return;
    }
    if (!supabase) return;
    const apply = (s: Session | null) =>
      setState(s ? { status: "ready", token: s.access_token, email: s.user?.email ?? "" } : { status: "anon" });
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => apply(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e: string, session: Session | null) => apply(session));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  if (state.status === "ready" && state.token === "preview") return <Authed token="preview" email={state.email} onSignOut={() => {}} />;
  if (!supabaseConfigured || !supabase) {
    return <p role="alert" className="rounded-xl border border-signal p-4">The dashboard is not configured: set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.</p>;
  }
  if (state.status === "loading")
    return (
      <div role="status" aria-label="Loading" className="space-y-4">
        <div className="skeleton h-5 w-48" />
        <div className="skeleton h-40 w-full" />
      </div>
    );
  if (state.status === "anon") {
    return (
      <div className="card mx-auto max-w-lg p-8 text-center">
        <KeyRound aria-hidden className="mx-auto size-6 text-accent" />
        <p className="mt-3 text-lg font-light">Sign in to create API keys and see your usage.</p>
        <Link href="/login" className="btn btn-primary mt-5">Sign in</Link>
      </div>
    );
  }
  return (
    <Authed
      token={state.token}
      email={state.email}
      onSignOut={async () => {
        await supabase.auth.signOut();
      }}
    />
  );
}

function Authed({ token, email, onSignOut }: { token: string; email: string; onSignOut: () => void }) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<NewApiKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingRevoke, setPendingRevoke] = useState<ApiKey | null>(null);
  const toast = useToast();
  const freshRef = useRef<HTMLElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (fresh) freshRef.current?.focus();
  }, [fresh]);

  const refresh = useCallback(async () => {
    if (process.env.NODE_ENV !== "production" && token === "preview" && previewEnabled()) {
      const { previewData } = await import("@/lib/previewFixtures");
      const p = previewData(new URLSearchParams(window.location.search).get("fixture"));
      setKeys(p.keys);
      setUsage(p.usage);
      return;
    }
    try {
      const [k, u] = await Promise.all([listKeys(token), getUsage(token)]);
      setKeys(k);
      setUsage(u);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError && e.status === 401 ? "Your session expired. Sign in again." : e instanceof Error ? `Could not reach the API: ${e.message}. It may be waking up; try again in a moment.` : "Request failed.");
    }
  }, [token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const now = useMemo(() => new Date(), [usage]); // eslint-disable-line react-hooks/exhaustive-deps
  const series = useMemo(() => lastNDays(usage?.days ?? [], now, 30), [usage, now]);
  const activeKeys = keys.filter((k) => !k.revoked_at);
  const newest = [...activeKeys].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];

  return (
    <div className="min-w-0 space-y-14">
      <p className="text-sm text-muted">
        Signed in as {email || "your account"}.{" "}
        <button type="button" onClick={onSignOut} className="link inline-flex items-center gap-1"><LogOut aria-hidden className="inline size-3.5" />Sign out</button>
      </p>
      {error && <p role="alert" className="rounded-xl border border-bad p-4">{error}</p>}

      <section aria-labelledby="usage" className="space-y-5">
        <h2 id="usage" className="h2 flex items-center gap-2 !text-2xl"><ChartColumn aria-hidden className="size-5 text-accent" />Usage</h2>
        {usage ? <UsageSection usage={usage} series={series} now={now} activeKeys={activeKeys.length} /> : !error && <p className="text-muted">Loading...</p>}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Quickstart prefix={newest?.prefix} />
        <Limits />
      </div>

      <section aria-labelledby="keys" className="space-y-3">
        <h2 id="keys" className="h2 flex items-center gap-2 !text-2xl"><KeyRound aria-hidden className="size-5 text-accent" />API keys</h2>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const k = await createKey(token, name.trim() || "default");
              setFresh(k);
              toast("API key created");
              setName("");
              await refresh();
            } catch (err) {
              const m = err instanceof Error ? err.message : "Could not create the key.";
              setError(m);
              toast(m, "error");
            }
            setBusy(false);
          }}
        >
          <div>
            <label htmlFor="key-name" className="block text-sm font-medium">Key name</label>
            <input id="key-name" ref={nameRef} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="ci" className="field !w-auto" />
          </div>
          <button type="submit" disabled={busy} className="btn btn-primary"><Plus aria-hidden className="size-4" />Create key</button>
        </form>

        {fresh && (
          <section ref={freshRef} tabIndex={-1} aria-label="New API key" className="rise space-y-3 rounded-xl border border-ok bg-surface p-4 outline-none focus-visible:ring-2 focus-visible:ring-accent">
            <p className="font-medium">Copy your key now. It will not be shown again.</p>
            <code className="block break-all">{fresh.key}</code>
            <div className="flex gap-3">
              <CopyButton label="API key" text={fresh.key}>Copy key</CopyButton>
              <button
                type="button"
                className="link text-sm"
                onClick={() => {
                  setFresh(null);
                  nameRef.current?.focus();
                }}
              >
                Hide
              </button>
            </div>
          </section>
        )}

        {keys.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center">
            <KeyRound aria-hidden className="mx-auto size-5 text-muted" />
            <p className="mt-2 font-medium">Create your first key</p>
            <p className="mt-1 text-sm text-muted">Name it after where it will run, for example <code>ci</code>, then use it as a Bearer token with <code>/v1/check</code>.</p>
            <button type="button" className="btn btn-primary mt-4" onClick={() => nameRef.current?.focus()}>Name your key</button>
          </div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Name</th><th>Prefix</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id}>
                    <td>{k.name}</td>
                    <td><code>{k.prefix}...</code></td>
                    <td>{new Date(k.created_at).toLocaleDateString("en-GB")}</td>
                    <td>
                      {k.revoked_at ? (
                        <span className="text-muted">Revoked</span>
                      ) : (
                        <button
                          type="button"
                          aria-label={`Revoke key ${k.name}`}
                          className="link inline-flex items-center gap-1 text-bad"
                          onClick={() => setPendingRevoke(k)}
                        >
                          <Trash2 aria-hidden className="size-3.5" />Revoke
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <ConfirmDialog
        open={pendingRevoke !== null}
        title={`Revoke "${pendingRevoke?.name ?? ""}"?`}
        body="Apps using this key will stop working. This cannot be undone."
        confirmLabel="Revoke key"
        onCancel={() => setPendingRevoke(null)}
        onConfirm={async () => {
          const k = pendingRevoke;
          setPendingRevoke(null);
          if (!k) return;
          try {
            await revokeKey(token, k.id);
            await refresh();
            toast(`Revoked "${k.name}"`);
          } catch (err) {
            const m = err instanceof Error ? err.message : "Could not revoke the key.";
            setError(m);
            toast(m, "error");
          }
        }}
      />
    </div>
  );
}

const nf = (n: number) => n.toLocaleString("en-US");

function Tile({ label, value, sub, warn }: { label: string; value: string; sub?: React.ReactNode; warn?: boolean }) {
  return (
    <div className="card p-4">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={`mt-1 text-2xl font-light tabular-nums ${warn ? "text-signal" : ""}`}>{value}</dd>
      {sub && <dd className={`mt-1 text-xs ${warn ? "text-signal" : "text-muted"}`}>{sub}</dd>}
    </div>
  );
}

function UsageSection({ usage, series, now, activeKeys }: { usage: Usage; series: { day: string; count: number }[]; now: Date; activeKeys: number }) {
  const quota = usage.monthly_quota;
  const today = series[series.length - 1]?.count ?? 0;
  const week = sumCounts(series.slice(-7));
  const projected = projectMonthEnd(usage.month_total, now);
  const over = quota > 0 && projected > quota;
  const pct = quota > 0 ? Math.min(100, (usage.month_total / quota) * 100) : 0;
  return (
    <>
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile label="Checks today" value={nf(today)} />
        <Tile label="Last 7 days" value={nf(week)} />
        <Tile label="This month" value={nf(usage.month_total)} sub={quota > 0 ? `of ${nf(quota)} · ${nf(Math.max(0, quota - usage.month_total))} left` : undefined} />
        <Tile
          label="Projected month-end (estimate)"
          value={`~${nf(projected)}`}
          warn={over}
          sub={over ? <span className="inline-flex items-center gap-1"><TriangleAlert aria-hidden className="size-3" />May exceed quota at this pace</span> : "Linear, at the current pace"}
        />
        <Tile label="Active keys" value={nf(activeKeys)} />
      </dl>
      <div role="progressbar" aria-label="Monthly quota used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} className="h-2 overflow-hidden rounded-full bg-tint">
        <div className="h-2 rounded-full" style={{ width: `${pct}%`, background: pct > 90 ? "var(--bad)" : "var(--accent)" }} />
      </div>

      <figure className="card min-w-0 p-5">
        <figcaption className="mb-3 text-sm font-medium">Checks per day <span className="font-normal text-muted">· last 30 days</span></figcaption>
        <UsageChart days={series} />
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer">Data table</summary>
          <div className="tbl-wrap mt-2 max-h-72 overflow-y-auto">
            <table className="tbl">
              <thead><tr><th>Day</th><th className="num">Checks</th></tr></thead>
              <tbody>{[...series].reverse().map((d) => <tr key={d.day}><td>{d.day}</td><td className="num">{nf(d.count)}</td></tr>)}</tbody>
            </table>
          </div>
        </details>
      </figure>

      {usage.keys.length > 0 && (
        <div className="tbl-wrap">
          <table className="tbl">
            <caption className="sr-only">Usage per key this month</caption>
            <thead><tr><th>Key</th><th>Prefix</th><th className="num">This month</th><th>% of quota</th></tr></thead>
            <tbody>
              {usage.keys.map((k) => {
                const q = k.quota || quota;
                const p = q > 0 ? Math.min(100, (k.month_count / q) * 100) : 0;
                return (
                  <tr key={k.id}>
                    <td>{k.name}</td>
                    <td><code>{k.prefix}...</code></td>
                    <td className="num">{nf(k.month_count)}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div aria-hidden className="h-1.5 w-24 overflow-hidden rounded-full bg-tint"><div className="h-1.5 rounded-full bg-accent" style={{ width: `${p}%`, minWidth: k.month_count ? 2 : 0 }} /></div>
                        <span className="tabular-nums text-muted">{p < 1 && k.month_count ? "<1" : Math.round(p)}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Quickstart({ prefix }: { prefix?: string }) {
  const cmd = `curl -s ${API_URL}/v1/check \\
  -H "Authorization: Bearer ${prefix ? `${prefix}...` : "<your-key>"}" \\
  -H "Content-Type: application/json" \\
  -d '{"text": "Call me on +44 7700 900123", "checks": ["pii", "toxicity"]}'`;
  return (
    <section aria-labelledby="quickstart" className="card min-w-0 space-y-3 p-5">
      <h2 id="quickstart" className="flex items-center gap-2 text-base font-medium"><Terminal aria-hidden className="size-4 text-accent" />Quickstart</h2>
      <div className="relative">
        <pre tabIndex={0} aria-label="curl example" className="overflow-x-auto pr-12 text-xs"><code>{cmd}</code></pre>
        <CopyButton label="curl example" text={cmd} className="btn btn-ghost absolute right-2 top-2 !p-1.5" />
      </div>
      <p className="text-xs text-muted">
        {prefix ? "Shows your newest key's prefix only. Replace it with the full secret you copied when you created the key." : "Create a key below, then swap it in."}
      </p>
    </section>
  );
}

const LIMITS = [
  [Gauge, "Per key", "60 requests / minute"],
  [CalendarDays, "Monthly", "10,000 checks / key"],
  [FlaskConical, "Playground", "10 / minute per IP"],
  [Layers, "Batch", "up to 32 items, each counts"],
  [FileText, "Text", "up to 20k characters"],
  [Activity, "Context", "up to 50k characters"],
] as const;

function Limits() {
  return (
    <section aria-labelledby="limits" className="card min-w-0 p-5">
      <h2 id="limits" className="mb-3 flex items-center gap-2 text-base font-medium"><Gauge aria-hidden className="size-4 text-accent" />Limits</h2>
      <ul className="grid gap-x-6 gap-y-2.5 text-sm sm:grid-cols-2">
        {LIMITS.map(([Icon, label, value]) => (
          <li key={label} className="flex items-start gap-2">
            <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-muted" />
            <span><span className="text-muted">{label}</span><br />{value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
