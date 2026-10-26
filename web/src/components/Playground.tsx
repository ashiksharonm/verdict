"use client";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { CircleAlert, CircleCheck, Eraser, Info, Loader2 } from "lucide-react";
import { playgroundCheck, type CheckResponse, type PlaygroundOutcome } from "@/lib/api";
import { CHECKS, CHECK_INFO, TURNSTILE_SITE_KEY, type CheckName } from "@/lib/config";
import { PRESETS, type Preset } from "@/lib/presets";
import { API_URL } from "@/lib/config";
import { CHECK_ICONS, PRESET_ICONS } from "@/lib/checkIcons";
import CopyButton from "./CopyButton";
import { useToast } from "./Toast";

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

// Same limits as the API schema (CheckRequest.text / .context).
const MAX_TEXT = 20_000;
const MAX_CONTEXT = 50_000;
const STORE_KEY = "verdict-playground-v1";

const shq = (v: string) => `'${v.replace(/'/g, `'\\''`)}'`;
function asCurl(text: string, checks: string[], context?: string) {
  const body = JSON.stringify({ text, checks, ...(context ? { context } : {}) });
  return `curl -s ${API_URL}/v1/check \\\n  -H "Authorization: Bearer $VERDICT_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d ${shq(body)}`;
}
function asPython(text: string, checks: string[], context?: string) {
  const ctx = context ? `, context=${JSON.stringify(context)}` : "";
  return `from verdict_guardrails import Client\n\nclient = Client(api_key="vk_...")  # or set VERDICT_API_KEY\nres = client.check(${JSON.stringify(text)}, checks=${JSON.stringify(checks)}${ctx})\nprint(res.results)`;
}

function Tip({ name }: { name: CheckName }) {
  const info = CHECK_INFO[name];
  return (
    <span className="tipwrap relative inline-flex">
      <button type="button" aria-label={`About the ${info.label} check`} aria-describedby={`tip-${name}`} className="rounded-full p-0.5 text-muted hover:text-ink">
        <Info aria-hidden className="size-3.5" />
      </button>
      <span role="tooltip" id={`tip-${name}`} className="tip">
        {info.question} A score at or above the threshold (the tick on the bar) is flagged.
      </span>
    </span>
  );
}

function ScoreBar({ name, r, i }: { name: string; r: { flagged: boolean; score: number; threshold: number }; i: number }) {
  const pct = Math.round(r.score * 1000) / 10;
  const known = name in CHECK_INFO;
  const Icon = known ? CHECK_ICONS[name as CheckName] : null;
  const State = r.flagged ? CircleAlert : CircleCheck;
  return (
    <li className="card rise p-5" style={{ animationDelay: `${i * 70}ms` }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium">
          {Icon && <Icon aria-hidden className="size-4 text-accent" />}
          {CHECK_INFO[name as CheckName]?.label ?? name}
          {known && <Tip name={name as CheckName} />}
        </span>
        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-xs uppercase tracking-wider ${r.flagged ? "border-bad text-bad" : "border-ok text-ok"}`}>
          <State aria-hidden className="size-3.5" />
          {r.flagged ? "Flagged" : "Clear"}
        </span>
      </div>
      <p className="mt-3 text-4xl font-light tracking-tight tabular-nums">{r.score.toFixed(3)}</p>
      <div
        role="meter"
        aria-label={`${name} score`}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={r.score}
        aria-valuetext={`score ${r.score.toFixed(3)}, threshold ${r.threshold.toFixed(2)}`}
        className="relative mt-3 h-2 rounded-full bg-tint"
      >
        <span className="grow absolute inset-y-0 left-0 rounded-full" style={{ width: `${pct}%`, background: r.flagged ? "var(--bad)" : "var(--ok)", animationDelay: `${i * 70 + 120}ms` }} />
        <span className="fadein absolute -inset-y-1.5 w-px bg-ink" style={{ left: `${r.threshold * 100}%` }} title={`threshold ${r.threshold.toFixed(2)}`} />
      </div>
      <p className="mt-2 font-mono text-xs text-muted tabular-nums">
        score {r.score.toFixed(3)} / threshold {r.threshold.toFixed(2)} (tick)
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
  const [warmPct, setWarmPct] = useState<number | null>(null);
  const [touched, setTouched] = useState(false);
  const toast = useToast();
  const widgetEl = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | undefined>(undefined);

  // Restore the last input once mounted (not during render, to avoid a hydration mismatch).
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORE_KEY);
      if (!raw) return;
      const v = JSON.parse(raw) as { text?: string; context?: string; checks?: string[]; preset?: string | null };
      if (typeof v.text === "string") setText(v.text.slice(0, MAX_TEXT));
      if (typeof v.context === "string") setContext(v.context.slice(0, MAX_CONTEXT));
      if (Array.isArray(v.checks)) setChecks(new Set(CHECKS.filter((c) => v.checks!.includes(c))));
      setActivePreset(v.preset ?? null);
    } catch {}
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({ text, context, checks: [...checks], preset: activePreset }));
    } catch {}
  }, [text, context, checks, activePreset]);

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
    setWarmPct(null);
    const out = await playgroundCheck(
      { text, checks: CHECKS.filter((c) => checks.has(c)), context: checks.has("grounded") ? context : undefined },
      {
        token,
        onWarming: ({ attempt, waitMs, elapsedMs }) => {
          setWarmPct(Math.min(100, (elapsedMs / 60000) * 100));
          setStatus(`The API is warming up, retrying (attempt ${attempt + 1}, next try in ${Math.round(waitMs / 1000)} s, ${Math.round(elapsedMs / 1000)} s elapsed of about 60)...`);
        },
      },
    );
    setOutcome(out);
    if (out.kind === "error") toast(out.message, "error");
    setStatus("");
    setWarmPct(null);
    setBusy(false);
    if (TURNSTILE_SITE_KEY && window.turnstile) {
      // Tokens are single use.
      setToken("");
      window.turnstile.reset(widgetId.current);
    }
  }, [text, context, checks, token, toast]);

  const needsToken = Boolean(TURNSTILE_SITE_KEY) && !token;
  const grounded = checks.has("grounded");
  const problem = !text.trim() ? "Enter some text to check." : checks.size === 0 ? "Select at least one check." : grounded && !context.trim() ? "The grounded check needs context: paste the retrieved documents." : "";
  const canRun = !busy && !problem && !needsToken;
  const picked = CHECKS.filter((c) => checks.has(c));
  const clear = () => {
    setText("");
    setContext("");
    setActivePreset(null);
    setOutcome(null);
    setTouched(false);
  };

  const preset = PRESETS.find((p) => p.id === activePreset);
  const ctxOver = context.length >= MAX_CONTEXT * 0.9;
  const textOver = text.length >= MAX_TEXT * 0.9;
  return (
    <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="card min-w-0 space-y-6 p-5 sm:p-8">
        <section aria-labelledby={`${uid}-presets`}>
          <h2 id={`${uid}-presets`} className="eyebrow mb-3 !text-muted">Use-case presets</h2>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => {
              const I = PRESET_ICONS[p.id];
              return (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={activePreset === p.id}
                  onClick={() => applyPreset(p)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm transition-colors ${activePreset === p.id ? "border-accent bg-tint font-medium text-accent" : "border-border text-muted hover:border-muted hover:text-ink"}`}
                >
                  {I && <I aria-hidden className="size-3.5" />}
                  {p.title}
                </button>
              );
            })}
          </div>
          {preset && (
            <p className="mt-3 text-sm text-muted">
              {preset.story} <span className="text-ink">App decision:</span> {preset.decision}
            </p>
          )}
        </section>

        <form
          className="space-y-5"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setTouched(true);
            if (canRun) void run();
          }}
        >
          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <label htmlFor={`${uid}-text`} className="text-sm font-medium">Text to check</label>
              <button type="button" onClick={clear} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
                <Eraser aria-hidden className="size-3.5" />Clear
              </button>
            </div>
            <textarea
              id={`${uid}-text`}
              value={text}
              maxLength={MAX_TEXT}
              rows={6}
              aria-describedby={`${uid}-text-count`}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  setTouched(true);
                  if (canRun) void run();
                }
              }}
              onChange={(e) => {
                setText(e.target.value);
                setActivePreset(null);
              }}
              className="field font-mono"
            />
            <p id={`${uid}-text-count`} className={`mt-1 font-mono text-xs ${textOver ? "text-signal" : "text-muted"}`}>
              {text.length.toLocaleString("en-US")}/{MAX_TEXT.toLocaleString("en-US")} characters
            </p>
          </div>
          {grounded && (
            <div className="rise">
              <label htmlFor={`${uid}-ctx`} className="mb-1.5 block text-sm font-medium">
                Context <span className="font-normal text-muted">(required for grounded: the retrieved documents)</span>
              </label>
              <textarea
                id={`${uid}-ctx`}
                value={context}
                maxLength={MAX_CONTEXT}
                rows={4}
                required
                aria-invalid={touched && !context.trim()}
                aria-describedby={`${uid}-ctx-count`}
                onChange={(e) => setContext(e.target.value)}
                className="field font-mono"
              />
              <p id={`${uid}-ctx-count`} className={`mt-1 font-mono text-xs ${ctxOver ? "text-signal" : "text-muted"}`}>
                {context.length.toLocaleString("en-US")}/{MAX_CONTEXT.toLocaleString("en-US")} characters
              </p>
            </div>
          )}
          <fieldset>
            <legend className="mb-2 text-sm font-medium">Checks</legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
              {CHECKS.map((c) => {
                const I = CHECK_ICONS[c];
                return (
                  <label key={c} className="flex items-center gap-2">
                    <input type="checkbox" checked={checks.has(c)} onChange={() => toggle(c)} className="h-4 w-4 accent-[var(--accent)]" />
                    <I aria-hidden className="size-3.5 text-muted" />
                    {CHECK_INFO[c].label}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {TURNSTILE_SITE_KEY ? (
            <div ref={widgetEl} role="group" aria-label="Cloudflare Turnstile challenge" />
          ) : (
            <p className="text-sm text-signal">Turnstile is not configured (NEXT_PUBLIC_TURNSTILE_SITE_KEY is empty); requests are sent without a token and the API may reject them.</p>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={busy || needsToken} className="btn btn-primary">
              {busy && <Loader2 aria-hidden className="spin size-4" />}
              {busy ? "Checking..." : "Run checks"}
              {!busy && <kbd className="hidden font-mono text-xs opacity-80 sm:inline">Ctrl/Cmd+Enter</kbd>}
            </button>
            <CopyButton label="curl command" text={() => asCurl(text, picked, grounded ? context : undefined)}>Copy as curl</CopyButton>
            <CopyButton label="Python snippet" text={() => asPython(text, picked, grounded ? context : undefined)}>Copy as Python</CopyButton>
          </div>
          <p role={touched && problem ? "alert" : undefined} className="min-h-5 text-sm text-bad">{touched && problem ? problem : ""}</p>
          {needsToken && <p className="text-sm text-muted">Complete the challenge to enable the button.</p>}
        </form>
      </div>

      <div className="min-w-0 space-y-4 lg:sticky lg:top-24">
        <p className="eyebrow !text-muted">Results</p>
        <div aria-live="polite" role="status" className="text-sm text-muted">{status}</div>
        {busy && (
          <div aria-hidden className="space-y-3">
            {warmPct !== null && (
              <div className="h-1.5 overflow-hidden rounded-full bg-tint">
                <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${warmPct}%` }} />
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              {picked.slice(0, 4).map((c) => <div key={c} className="skeleton h-44" />)}
            </div>
          </div>
        )}
        {!outcome && !busy && <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted">Run the checks to see a score, a verdict and the threshold for each. Tip: Ctrl/Cmd+Enter runs from the text box.</p>}
        {outcome?.kind === "ok" && <Results data={outcome.data} />}
        {outcome?.kind === "rate_limited" && (
          <div role="alert" className="rounded-xl border border-signal bg-surface p-4">
            <p className="font-medium">Rate limited</p>
            <p className="text-sm">{outcome.message} Create an API key in the dashboard for higher limits.</p>
          </div>
        )}
        {outcome?.kind === "error" && (
          <div role="alert" className="rounded-xl border border-bad bg-surface p-4">
            <p className="font-medium">Request failed{outcome.status ? ` (HTTP ${outcome.status})` : ""}</p>
            <p className="text-sm">{outcome.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function Results({ data }: { data: CheckResponse }) {
  const entries = Object.entries(data.results);
  const flagged = entries.filter(([, r]) => r.flagged).length;
  return (
    <section aria-label="Results" className="space-y-4">
      <p className="rise text-lg font-light">
        <strong className="font-medium">{flagged} of {entries.length}</strong> {entries.length === 1 ? "check" : "checks"} flagged
      </p>
      <ul className="grid gap-4 sm:grid-cols-2">
        {entries.map(([name, r], i) => (
          <ScoreBar key={name} name={name} r={r} i={i} />
        ))}
      </ul>
      <p className="font-mono text-xs text-muted tabular-nums [overflow-wrap:anywhere]">
        latency {data.latency_ms.toFixed(1)} ms · model <code>{data.model_version}</code> · id <code>{data.id}</code>
      </p>
    </section>
  );
}
