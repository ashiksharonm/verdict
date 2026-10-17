"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { playgroundCheck, type CheckResponse, type PlaygroundOutcome } from "@/lib/api";
import { CHECKS, CHECK_INFO, TURNSTILE_SITE_KEY, type CheckName } from "@/lib/config";
import { PRESETS, type Preset } from "@/lib/presets";

type TurnstileApi = {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id?: string) => void;
  remove: (id?: string) => void;
};
declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const MAX_TEXT = 4000;

function ScoreBar({ name, r }: { name: string; r: { flagged: boolean; score: number; threshold: number } }) {
  const pct = Math.round(r.score * 1000) / 10;
  return (
    <li className="rounded-lg border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">{CHECK_INFO[name as CheckName]?.label ?? name}</span>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${r.flagged ? "bg-bad text-bg" : "bg-ok text-bg"}`}>{r.flagged ? "Flagged" : "Clear"}</span>
      </div>
      <div
        role="meter"
        aria-label={`${name} score`}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={r.score}
        aria-valuetext={`score ${r.score.toFixed(3)}, threshold ${r.threshold.toFixed(2)}`}
        className="relative mt-2 h-3 rounded bg-code"
      >
        <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${pct}%`, background: r.flagged ? "var(--bad)" : "var(--ok)" }} />
        <span className="absolute -inset-y-1 w-0.5 bg-fg" style={{ left: `${r.threshold * 100}%` }} title={`threshold ${r.threshold.toFixed(2)}`} />
      </div>
      <p className="mt-1 text-xs text-muted tabular-nums">
        score {r.score.toFixed(3)} · threshold {r.threshold.toFixed(2)} (the marker on the bar)
      </p>
    </li>
  );
}

export default function Playground() {
  const uid = useId();
  const [text, setText] = useState(PRESETS[0].text);
  const [context, setContext] = useState(PRESETS[0].context ?? "");
  const [checks, setChecks] = useState<Set<CheckName>>(new Set(PRESETS[0].checks));
  const [activePreset, setActivePreset] = useState<string | null>(PRESETS[0].id);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [outcome, setOutcome] = useState<PlaygroundOutcome | null>(null);
  const [token, setToken] = useState("");
  const widgetEl = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;
    const mount = () => {
      if (!window.turnstile || !widgetEl.current || widgetId.current) return;
      widgetId.current = window.turnstile.render(widgetEl.current, {
        sitekey: TURNSTILE_SITE_KEY,
        callback: (t: string) => setToken(t),
        "expired-callback": () => setToken(""),
        "error-callback": () => setToken(""),
      });
    };
    if (window.turnstile) mount();
    else {
      let s = document.querySelector<HTMLScriptElement>("script[data-turnstile]");
      if (!s) {
        s = document.createElement("script");
        s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
        s.async = true;
        s.dataset.turnstile = "1";
        document.head.appendChild(s);
      }
      s.addEventListener("load", mount);
    }
    return () => {
      if (widgetId.current && window.turnstile) window.turnstile.remove(widgetId.current);
      widgetId.current = undefined;
    };
  }, []);

  const applyPreset = (p: Preset) => {
    setText(p.text);
    setContext(p.context ?? "");
    setChecks(new Set(p.checks));
    setActivePreset(p.id);
    setOutcome(null);
  };

  const toggle = (c: CheckName) =>
    setChecks((prev) => {
      const n = new Set(prev);
      if (n.has(c)) n.delete(c);
      else n.add(c);
      return n;
    });

  const run = useCallback(async () => {
    setBusy(true);
    setOutcome(null);
    setStatus("Checking...");
    const out = await playgroundCheck(
      { text, checks: CHECKS.filter((c) => checks.has(c)), context: checks.has("grounded") ? context : undefined },
      {
        token,
        onWarming: ({ attempt, waitMs, elapsedMs }) =>
          setStatus(`The API is warming up, retrying (attempt ${attempt + 1}, next try in ${Math.round(waitMs / 1000)} s, ${Math.round(elapsedMs / 1000)} s elapsed of about 60)...`),
      },
    );
    setOutcome(out);
    setStatus("");
    setBusy(false);
    if (TURNSTILE_SITE_KEY && window.turnstile) {
      // Tokens are single use.
      setToken("");
      window.turnstile.reset(widgetId.current);
    }
  }, [text, context, checks, token]);

  const needsToken = Boolean(TURNSTILE_SITE_KEY) && !token;
  const canRun = !busy && text.trim().length > 0 && checks.size > 0 && !needsToken && (!checks.has("grounded") || context.trim().length > 0);

  return (
    <div className="space-y-6">
      <section aria-labelledby={`${uid}-presets`}>
        <h2 id={`${uid}-presets`} className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">Use-case presets</h2>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              aria-pressed={activePreset === p.id}
              onClick={() => applyPreset(p)}
              className={`rounded-lg border p-3 text-left ${activePreset === p.id ? "border-accent bg-card" : "border-border hover:bg-card"}`}
            >
              <span className="block font-semibold">{p.title}</span>
              <span className="block text-sm text-muted">{p.story}</span>
            </button>
          ))}
        </div>
        {activePreset && <p className="mt-2 text-sm text-muted">App decision: {PRESETS.find((p) => p.id === activePreset)?.decision}</p>}
      </section>

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (canRun) void run();
        }}
      >
        <div>
          <label htmlFor={`${uid}-text`} className="mb-1 block font-medium">Text to check</label>
          <textarea
            id={`${uid}-text`}
            value={text}
            maxLength={MAX_TEXT}
            rows={5}
            onChange={(e) => {
              setText(e.target.value);
              setActivePreset(null);
            }}
            className="w-full rounded-md border border-border bg-card p-2 font-mono text-sm"
          />
          <p className="text-xs text-muted">{text.length}/{MAX_TEXT} characters</p>
        </div>
        <div>
          <label htmlFor={`${uid}-ctx`} className="mb-1 block font-medium">
            Context <span className="font-normal text-muted">(required for the grounded check: the retrieved documents)</span>
          </label>
          <textarea id={`${uid}-ctx`} value={context} maxLength={MAX_TEXT} rows={3} onChange={(e) => setContext(e.target.value)} className="w-full rounded-md border border-border bg-card p-2 font-mono text-sm" />
        </div>
        <fieldset>
          <legend className="mb-1 font-medium">Checks</legend>
          <div className="flex flex-wrap gap-4">
            {CHECKS.map((c) => (
              <label key={c} className="flex items-center gap-2">
                <input type="checkbox" checked={checks.has(c)} onChange={() => toggle(c)} className="h-4 w-4 accent-[var(--accent)]" />
                {CHECK_INFO[c].label}
              </label>
            ))}
          </div>
        </fieldset>

        {TURNSTILE_SITE_KEY ? (
          <div ref={widgetEl} aria-label="Cloudflare Turnstile challenge" />
        ) : (
          <p className="text-sm text-warn">Turnstile is not configured (NEXT_PUBLIC_TURNSTILE_SITE_KEY is empty); requests are sent without a token and the API may reject them.</p>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={!canRun} className="rounded-md bg-accent px-4 py-2 font-medium text-accent-fg disabled:opacity-50">
            {busy ? "Checking..." : "Run checks"}
          </button>
          {needsToken && <span className="text-sm text-muted">Complete the challenge to enable the button.</span>}
          {checks.has("grounded") && !context.trim() && <span className="text-sm text-muted">Add context for the grounded check.</span>}
        </div>
      </form>

      <div aria-live="polite" role="status" className="min-h-6 text-sm text-muted">{status}</div>

      {outcome?.kind === "ok" && <Results data={outcome.data} />}
      {outcome?.kind === "rate_limited" && (
        <div role="alert" className="rounded-lg border border-warn p-3">
          <p className="font-semibold">Rate limited</p>
          <p className="text-sm">{outcome.message} Create an API key in the dashboard for higher limits.</p>
        </div>
      )}
      {outcome?.kind === "error" && (
        <div role="alert" className="rounded-lg border border-bad p-3">
          <p className="font-semibold">Request failed{outcome.status ? ` (HTTP ${outcome.status})` : ""}</p>
          <p className="text-sm">{outcome.message}</p>
        </div>
      )}
    </div>
  );
}

function Results({ data }: { data: CheckResponse }) {
  return (
    <section aria-label="Results" className="space-y-3">
      <ul className="grid gap-3 sm:grid-cols-2">
        {Object.entries(data.results).map(([name, r]) => (
          <ScoreBar key={name} name={name} r={r} />
        ))}
      </ul>
      <p className="text-sm text-muted tabular-nums">
        latency {data.latency_ms.toFixed(1)} ms · model <code>{data.model_version}</code> · id <code>{data.id}</code>
      </p>
    </section>
  );
}
