import Link from "next/link";
import CountUp from "@/components/CountUp";
import Reveal from "@/components/Reveal";
import { CHECK_ICONS } from "@/lib/checkIcons";
import { ArrowRight } from "lucide-react";
import Code from "@/components/Code";
import ResultsTable from "@/components/ResultsTable";
import { CHECKS, CHECK_INFO } from "@/lib/config";
import { SDK_INSTALL, curlCheck, pythonCheck } from "@/lib/snippets";
import { f3, featured, resultsDir, results } from "@/lib/results";

const steps = [
  ["Your app", "text, optional context, list of checks"],
  ["POST /v1/check", "API key or playground token"],
  ["One small model", "ONNX int8, one forward pass"],
  ["Calibrated scores", "per check: flagged, score, threshold"],
];

const sys = (k: string) => results.systems[k];

export default function Home() {
  const grounded = featured.checks!.grounded!;
  const lat = featured.latency_batch1!;
  const inj = featured.checks!.prompt_injection!;
  const pii = featured.checks!.pii!;
  const tox = featured.checks!.toxicity!;
  const protect = sys("protectai")?.checks?.prompt_injection;
  const presidio = sys("presidio")?.checks?.pii;
  const judge = results.laya_ft_vs_llm_judge;
  return (
    <div className="space-y-24 sm:space-y-28">
      <section className="max-w-3xl">
        <p className="eyebrow">Guardrails for LLM apps</p>
        <h1 className="display mt-4">Calibrated guardrails from one small, self-hostable model.</h1>
        <p className="lede mt-6 max-w-2xl">
          One request returns a calibrated probability and a verdict for PII, toxicity, prompt injection and groundedness.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/playground" className="btn btn-primary">Try the playground<ArrowRight aria-hidden className="size-4" /></Link>
          <Link href="/benchmarks" className="btn btn-ghost">Read the benchmark</Link>
        </div>
      </section>

      <Reveal as="section" aria-labelledby="highlights" className="callout max-w-4xl">
        <h2 id="highlights" className="eyebrow">Highlights</h2>
        <ul className="mt-3">
          <li>
            <strong>PII macro-F1 <CountUp value={pii.macro_f1} decimals={3} /></strong>
            {presidio ? ` against ${f3(presidio.macro_f1)} for Presidio` : ""}, and <strong>prompt-injection macro-F1 <CountUp value={inj.macro_f1} decimals={3} /></strong>
            {protect ? ` against ${f3(protect.macro_f1)} for ProtectAI deberta-v3` : ""}, on held-out test sets.
          </li>
          <li>
            <strong>Toxicity macro-F1 <CountUp value={tox.macro_f1} decimals={3} /></strong> from the same single model, scored per check with its own fitted threshold.
          </li>
          <li>
            <strong>About <CountUp value={Math.round(lat.p50_ms)} /> ms per request</strong> at p50 (p95 {Math.round(lat.p95_ms)} ms), batch 1, ONNX int8 on {results.environment.machine}.
          </li>
          {Object.values(judge).every((j) => j.auroc_delta_laya_minus_judge.ci[0] > 0) && (
            <li>
              <strong>Ahead of a Qwen3-1.7B judge</strong> on every check (AUROC gain, 95% CI above zero) on the same {results.llm_judge_n_per_check}-item subsamples.
            </li>
          )}
          <li>
            <strong>Weakest check is grounded:</strong> macro-F1 {f3(grounded.macro_f1)}, AUROC {f3(grounded.auroc)} on RAGTruth. Treat it as a soft signal.
          </li>
        </ul>
      </Reveal>

      <Reveal as="section" aria-labelledby="results" className="max-w-4xl">
        <p className="eyebrow">Results</p>
        <h2 id="results" className="h2 mt-3">Headline results</h2>
        <p className="mb-6 mt-3 text-muted">
          Held-out test sets, benchmark run {resultsDir} on {results.environment.machine}. Verdict is the highlighted ONNX int8 build; the others are baselines run under the same harness.
        </p>
        <ResultsTable compact />
      </Reveal>

      <Reveal as="section" aria-labelledby="how" className="max-w-4xl">
        <p className="eyebrow">How it works</p>
        <h2 id="how" className="h2 mt-3">One forward pass, four typed questions</h2>
        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(([t, d], i) => (
            <li key={t} className="rounded-xl border border-border bg-surface p-4">
              <span className="eyebrow !text-muted">Step {i + 1}</span>
              <p className="mt-2 font-medium">{t}</p>
              <p className="mt-1 text-sm text-muted">{d}</p>
            </li>
          ))}
        </ol>
        <ul className="mt-4 grid gap-4 sm:grid-cols-2">
          {CHECKS.map((c) => (
            <li key={c} className="rounded-xl border border-border bg-surface p-4">
              <span className="flex items-center gap-2">
                {(() => { const I = CHECK_ICONS[c]; return <I aria-hidden className="size-4 text-accent" />; })()}
                <code>{c}</code>
              </span>
              <p className="mt-2 text-sm text-muted">{CHECK_INFO[c].question}</p>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-muted">
          Each check is a typed question. Scores are temperature-calibrated and each check has its own threshold, fitted on a validation split that is never used for the benchmark.
        </p>
      </Reveal>

      <Reveal as="section" aria-labelledby="quickstart" className="max-w-3xl">
        <p className="eyebrow">Quickstart</p>
        <h2 id="quickstart" className="h2 mt-3">Call it with curl</h2>
        <p className="mb-4 mt-3 text-muted">Create a key in the <Link className="link" href="/dashboard">dashboard</Link>, then:</p>
        <Code label="curl example">{curlCheck()}</Code>
        <h3 className="mt-8 font-medium">Python SDK (coming soon)</h3>
        <p className="mb-3 mt-1 text-sm text-muted">The SDK is not published to PyPI yet. Until then install it from GitHub.</p>
        <div className="space-y-3">
          <Code label="SDK install">{SDK_INSTALL}</Code>
          <Code label="Python example">{pythonCheck}</Code>
        </div>
      </Reveal>

      <Reveal as="section" aria-labelledby="limits" className="max-w-3xl">
        <p className="eyebrow">Limitations</p>
        <h2 id="limits" className="h2 mt-3">Honest limitations</h2>
        <ul className="prose-v mt-4">
          <li>
            <code>grounded</code> is the weakest check: macro-F1 {f3(grounded.macro_f1)}, AUROC {f3(grounded.auroc)} on RAGTruth. Treat it as a soft signal, not a gate, and see the per-source breakdown on the{" "}
            <Link href="/benchmarks">benchmarks page</Link>.
          </li>
          <li>
            Latency is around {Math.round(lat.p50_ms)} ms per request (p50, batch 1, ONNX int8 on the benchmark machine&apos;s CPU; p95 {Math.round(lat.p95_ms)} ms). The hosted free CPU tier has not been measured by this benchmark.
          </li>
          <li>The toxicity test set is class-balanced; real traffic is far less toxic, so production precision will be lower than the table suggests.</li>
          <li>Some PII negatives and the PII positives are synthetic text, so real-world PII performance may differ. See <Link href="/benchmarks#methodology">methodology</Link>.</li>
          <li>The hosted API runs on a free tier that sleeps when idle: the first request can take up to about a minute. Rate limits apply.</li>
        </ul>
      </Reveal>
    </div>
  );
}
