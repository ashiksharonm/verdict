import Link from "next/link";
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

export default function Home() {
  const grounded = featured.checks!.grounded!;
  const lat = featured.latency_batch1!;
  return (
    <div className="space-y-14">
      <section className="space-y-5 pt-4">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">Calibrated guardrails for LLM apps from one small, self-hostable model.</h1>
        <p className="max-w-2xl text-lg text-muted">
          Verdict fine-tunes Laya, a ModernBERT-large decision model, into a single multi-check classifier. One request returns a probability and a verdict for PII, toxicity, prompt injection and groundedness.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link href="/playground" className="rounded-md bg-accent px-4 py-2 font-medium text-accent-fg">Try the playground</Link>
          <Link href="/docs" className="rounded-md border border-border px-4 py-2 font-medium">Read the docs</Link>
        </div>
      </section>

      <section aria-labelledby="results" className="space-y-3">
        <h2 id="results" className="text-2xl font-semibold">Headline results</h2>
        <p className="text-muted">
          Held-out test sets, benchmark run {resultsDir} on {results.environment.machine}. Verdict is the highlighted ONNX int8 build; the others are baselines run under the same harness.
        </p>
        <ResultsTable compact />
      </section>

      <section aria-labelledby="how" className="space-y-4">
        <h2 id="how" className="text-2xl font-semibold">How it works</h2>
        <ol className="grid gap-3 sm:grid-cols-4">
          {steps.map(([t, d], i) => (
            <li key={t} className="relative rounded-lg border border-border bg-card p-3">
              <span className="text-xs text-muted">Step {i + 1}</span>
              <p className="font-semibold">{t}</p>
              <p className="text-sm text-muted">{d}</p>
            </li>
          ))}
        </ol>
        <ul className="grid gap-3 sm:grid-cols-2">
          {CHECKS.map((c) => (
            <li key={c} className="rounded-lg border border-border bg-card p-3">
              <code>{c}</code>
              <p className="text-sm text-muted">{CHECK_INFO[c].question}</p>
            </li>
          ))}
        </ul>
        <p className="text-muted">
          Each check is a typed question. Scores are temperature-calibrated and each check has its own threshold, fitted on a validation split that is never used for the benchmark.
        </p>
      </section>

      <section aria-labelledby="quickstart" className="space-y-3">
        <h2 id="quickstart" className="text-2xl font-semibold">Quickstart</h2>
        <p className="text-muted">Create a key in the <Link className="underline" href="/dashboard">dashboard</Link>, then:</p>
        <Code label="curl example">{curlCheck()}</Code>
        <h3 className="font-semibold">Python SDK (coming soon)</h3>
        <p className="text-sm text-muted">The SDK is not published to PyPI yet. Until then install it from GitHub.</p>
        <Code label="SDK install">{SDK_INSTALL}</Code>
        <Code label="Python example">{pythonCheck}</Code>
      </section>

      <section aria-labelledby="limits" className="space-y-3">
        <h2 id="limits" className="text-2xl font-semibold">Honest limitations</h2>
        <ul className="prose-v">
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
      </section>
    </div>
  );
}
