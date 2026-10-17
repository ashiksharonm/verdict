"use client";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useState } from "react";
import { ApiError, createKey, getUsage, listKeys, revokeKey, type ApiKey, type NewApiKey, type Usage } from "@/lib/api";
import { supabaseConfigured } from "@/lib/config";
import { getSupabase } from "@/lib/supabase";

type State = { status: "loading" } | { status: "anon" } | { status: "ready"; token: string; email: string };

export default function Dashboard() {
  const [state, setState] = useState<State>({ status: "loading" });
  const supabase = getSupabase();

  useEffect(() => {
    if (!supabase) return;
    const apply = (s: Session | null) =>
      setState(s ? { status: "ready", token: s.access_token, email: s.user?.email ?? "" } : { status: "anon" });
    supabase.auth.getSession().then(({ data }: { data: { session: Session | null } }) => apply(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e: string, session: Session | null) => apply(session));
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  if (!supabaseConfigured || !supabase) {
    return <p role="alert" className="rounded-lg border border-warn p-3">The dashboard is not configured: set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.</p>;
  }
  if (state.status === "loading") return <p className="text-muted">Loading...</p>;
  if (state.status === "anon") {
    return (
      <p>
        <Link href="/login" className="underline">Sign in</Link> to create API keys and see your usage.
      </p>
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
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
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

  const max = Math.max(1, ...(usage?.days.map((d) => d.count) ?? [0]));
  const pct = usage && usage.monthly_quota > 0 ? Math.min(100, (usage.month_total / usage.monthly_quota) * 100) : 0;

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted">
        Signed in as {email || "your account"}.{" "}
        <button type="button" onClick={onSignOut} className="underline">Sign out</button>
      </p>
      {error && <p role="alert" className="rounded-lg border border-bad p-3">{error}</p>}

      <section aria-labelledby="usage" className="space-y-3">
        <h2 id="usage" className="text-xl font-semibold">Usage</h2>
        {usage ? (
          <>
            <p>
              {usage.month_total.toLocaleString("en-US")} of {usage.monthly_quota.toLocaleString("en-US")} checks this month
            </p>
            <div role="progressbar" aria-label="Monthly quota used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} className="h-3 rounded bg-code">
              <div className="h-3 rounded" style={{ width: `${pct}%`, background: pct > 90 ? "var(--bad)" : "var(--accent)" }} />
            </div>
            {usage.days.length > 0 ? (
              <figure className="rounded-lg border border-border bg-card p-4">
                <figcaption className="mb-2 text-sm font-semibold">Checks per day</figcaption>
                <div className="flex h-32 items-end gap-1" role="img" aria-label={`Checks per day, peak ${max}`}>
                  {usage.days.map((d) => (
                    <div key={d.day} className="flex-1 rounded-t bg-accent" style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count ? 2 : 0 }} title={`${d.day}: ${d.count}`} />
                  ))}
                </div>
                <details className="mt-2 text-sm">
                  <summary className="cursor-pointer">Data table</summary>
                  <table className="tbl mt-2">
                    <thead><tr><th>Day</th><th className="num">Checks</th></tr></thead>
                    <tbody>{usage.days.map((d) => <tr key={d.day}><td>{d.day}</td><td className="num">{d.count}</td></tr>)}</tbody>
                  </table>
                </details>
              </figure>
            ) : (
              <p className="text-muted">No usage yet.</p>
            )}
          </>
        ) : (
          !error && <p className="text-muted">Loading...</p>
        )}
      </section>

      <section aria-labelledby="keys" className="space-y-3">
        <h2 id="keys" className="text-xl font-semibold">API keys</h2>
        <form
          className="flex flex-wrap items-end gap-3"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              const k = await createKey(token, name.trim() || "default");
              setFresh(k);
              setCopied(false);
              setName("");
              await refresh();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Could not create the key.");
            }
            setBusy(false);
          }}
        >
          <div>
            <label htmlFor="key-name" className="block text-sm font-medium">Key name</label>
            <input id="key-name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="ci" className="rounded-md border border-border bg-card p-2" />
          </div>
          <button type="submit" disabled={busy} className="rounded-md bg-accent px-4 py-2 font-medium text-accent-fg disabled:opacity-50">Create key</button>
        </form>

        {fresh && (
          <div role="status" className="space-y-2 rounded-lg border border-ok p-3">
            <p className="font-semibold">Copy your key now. It will not be shown again.</p>
            <code className="block break-all">{fresh.key}</code>
            <div className="flex gap-3">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1 text-sm"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(fresh.key);
                    setCopied(true);
                  } catch {
                    setCopied(false);
                  }
                }}
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <button type="button" className="text-sm underline" onClick={() => setFresh(null)}>Hide</button>
            </div>
          </div>
        )}

        {keys.length === 0 ? (
          <p className="text-muted">No keys yet.</p>
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
                          className="text-bad underline"
                          onClick={async () => {
                            if (!window.confirm(`Revoke "${k.name}"? Apps using it will stop working.`)) return;
                            try {
                              await revokeKey(token, k.id);
                              await refresh();
                            } catch (err) {
                              setError(err instanceof Error ? err.message : "Could not revoke the key.");
                            }
                          }}
                        >
                          Revoke
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
    </div>
  );
}
