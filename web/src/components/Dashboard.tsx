"use client";
import { ChartColumn, KeyRound, LogOut, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import ConfirmDialog from "./ConfirmDialog";
import CopyButton from "./CopyButton";
import { useToast } from "./Toast";
import type { Session } from "@supabase/supabase-js";
import { useCallback, useEffect, useRef, useState } from "react";
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
    <div className="space-y-14">
      <p className="text-sm text-muted">
        Signed in as {email || "your account"}.{" "}
        <button type="button" onClick={onSignOut} className="link inline-flex items-center gap-1"><LogOut aria-hidden className="inline size-3.5" />Sign out</button>
      </p>
      {error && <p role="alert" className="rounded-xl border border-bad p-4">{error}</p>}

      <section aria-labelledby="usage" className="space-y-3">
        <h2 id="usage" className="h2 flex items-center gap-2 !text-2xl"><ChartColumn aria-hidden className="size-5 text-accent" />Usage</h2>
        {usage ? (
          <>
            <p>
              {usage.month_total.toLocaleString("en-US")} of {usage.monthly_quota.toLocaleString("en-US")} checks this month
            </p>
            <div role="progressbar" aria-label="Monthly quota used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} className="h-2.5 overflow-hidden rounded-full bg-tint">
              <div className="h-2.5 rounded-full" style={{ width: `${pct}%`, background: pct > 90 ? "var(--bad)" : "var(--accent)" }} />
            </div>
            {usage.days.length > 0 ? (
              <figure className="card p-5">
                <figcaption className="mb-3 text-sm font-medium">Checks per day</figcaption>
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
