import type { Metadata } from "next";
import BarList from "@/components/BarList";
import DocLayout from "@/components/DocLayout";
import ResultsTable from "@/components/ResultsTable";
import { CHECKS, CHECK_INFO } from "@/lib/config";
import { parseDatasetTable } from "@/lib/datasets";
import { live, liveMs, parity } from "@/lib/live";
import { FEATURED, aggregateThroughput, costPerMillion, f1, f3, resultsDir, results, scoredSystems } from "@/lib/results";

export const metadata: Metadata = { title: "Benchmarks" };

const TOC = [
  { id: "summary", label: "Summary" },
  { id: "per-check", label: "Per-check metrics" },
  ...CHECKS.map((c) => ({ id: `h-${c}`, label: c, sub: true })),
  { id: "robustness", label: "Injection robustness" },
  { id: "latency", label: "Latency and throughput" },
  { id: "parity", label: "Production (x86) parity" },
  { id: "judge", label: "Verdict vs an LLM judge" },
  { id: "cost", label: "Cost per 1M checks" },
  { id: "methodology", label: "Methodology and licences" },
];

const ROBUST = ["leetspeak", "homoglyphs", "zero_width", "random_case", "base64"];

export default function Page() {
  const cost = costPerMillion();
  const datasets = parseDatasetTable();
  const robust = Object.entries(results.systems).filter(([, s]) => s.robustness && Object.keys(s.robustness).length > 0);
  const lat = Object.entries(results.systems).filter(([, s]) => s.latency_batch1);
  const env = results.environment;
  return (
    <DocLayout
      eyebrow="Benchmarks"
      title="Held-out results, every number from the committed run"
      toc={TOC}
      intro={
        <>
          Every number on this page is read from the committed <code>evals/results/{resultsDir}/results.json</code> at build time. Hardware: {env.machine} ({env.platform}); the device column shows where each system ran. Intervals are {results.n_boot}-resample bootstrap 95% CIs. Verdict uses per-check thresholds fitted on a validation split; other systems use their natural rule.
        </>
      }
    >
      <h2 id="summary">Summary (macro-F1 / AUROC)</h2>
      <ResultsTable />

      <h2 id="per-check">Per-check metrics</h2>
      {CHECKS.map((c) => {
        const rows = scoredSystems.filter(([, s]) => s.checks?.[c]);
        return (
          <section key={c} aria-labelledby={`h-${c}`} className="space-y-3">
            <h3 id={`h-${c}`}><code>{c}</code> <span className="text-sm font-normal text-muted">{CHECK_INFO[c].question} Test n = {results.test_sizes[c].toLocaleString("en-US")}</span></h3>
            <BarList
              title={`Macro-F1 with 95% CI, ${c}`}
              rows={rows.map(([k, s]) => {
                const m = s.checks![c]!;
                return { label: s.name, value: m.macro_f1, lo: m.ci95.macro_f1[0], hi: m.ci95.macro_f1[1], highlight: k === FEATURED };
              })}
            />
            <div className="tbl-wrap" role="region" tabIndex={0} aria-label={`Scores, `}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>System</th><th className="num">Thr</th><th className="num">Macro-F1 [95% CI]</th><th className="num">Prec</th><th className="num">Recall</th><th className="num">AUROC [95% CI]</th><th className="num">ECE</th><th className="num">Brier</th><th className="num">Rec@1%FPR</th><th className="num">Rec@5%FPR</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([k, s]) => {
                    const m = s.checks![c]!;
                    return (
                      <tr key={k} className={k === FEATURED ? "hl" : ""}>
                        <th scope="row" className="font-normal">{s.name}{m.subsample ? ` (n=${m.n})` : ""}</th>
                        <td className="num">{m.threshold.toFixed(2)}</td>
                        <td className="num">{f3(m.macro_f1)} [{f3(m.ci95.macro_f1[0])}, {f3(m.ci95.macro_f1[1])}]</td>
                        <td className="num">{f3(m.precision)}</td>
                        <td className="num">{f3(m.recall)}</td>
                        <td className="num">{f3(m.auroc)} [{f3(m.ci95.auroc[0])}, {f3(m.ci95.auroc[1])}]</td>
                        <td className="num">{f3(m.ece)}</td>
                        <td className="num">{f3(m.brier)}</td>
                        <td className="num">{f3(m.recall_at_fpr_1)}</td>
                        <td className="num">{f3(m.recall_at_fpr_5)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {(c === "prompt_injection" || c === "grounded") && <BySource check={c} />}
          </section>
        );
      })}

      <h2 id="robustness">Prompt-injection robustness</h2>
      <p>Recall on every positive in the injection test set after rewriting it five ways. Higher is better.</p>
      <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Prompt-injection robustness">
        <table className="tbl">
          <thead><tr><th>System</th><th className="num">Original</th>{ROBUST.map((r) => <th key={r} className="num">{r}</th>)}</tr></thead>
          <tbody>
            {robust.map(([k, s]) => (
              <tr key={k} className={k === FEATURED ? "hl" : ""}>
                <th scope="row" className="font-normal">{s.name}</th>
                <td className="num">{f3(Object.values(s.robustness!)[0].original_recall)}</td>
                {ROBUST.map((r) => <td key={r} className="num">{s.robustness![r] ? f3(s.robustness![r].recall) : "–"}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 id="latency">Latency and throughput (M5 benchmark)</h2>
      <p>Batch-1 latency is per request. Throughput is items per second over the benchmark run at the stated batch size. Measured on the benchmark machine above (Apple M5), not on the hosted API. Live API numbers: about {liveMs.p50} ms server-side p50 for 3 checks, see the next section.</p>
      <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Latency and throughput">
        <table className="tbl">
          <thead><tr><th>System</th><th>Device</th><th className="num">p50 ms</th><th className="num">p95 ms</th><th className="num">Items/s</th></tr></thead>
          <tbody>
            {lat.map(([k, s]) => {
              const t = aggregateThroughput(s);
              return (
                <tr key={k} className={k === FEATURED ? "hl" : ""}>
                  <th scope="row" className="font-normal">{s.name}</th>
                  <td>{s.device}</td>
                  <td className="num">{f1(s.latency_batch1!.p50_ms)}</td>
                  <td className="num">{f1(s.latency_batch1!.p95_ms)}</td>
                  <td className="num">{t ? `${f1(t.rate)} @ ${t.batch}` : "–"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <BarList
        title="Batch-1 p50 latency (ms, lower is better; bars scaled to the slowest system)"
        max={Math.max(...lat.map(([, s]) => s.latency_batch1!.p50_ms))}
        rows={lat.map(([k, s]) => ({ label: s.name, value: s.latency_batch1!.p50_ms, highlight: k === FEATURED }))}
      />

      <h2 id="parity">Production (x86) parity</h2>
      <p>
        The live API runs on {live.host}. The same test sets were re-scored there ({live.date}) with the fp32 model: macro-F1 is unchanged from the M5 benchmark and every decision matches it. Live API: {liveMs.p50} ms server-side p50 ({liveMs.p95} ms p95) and ~{liveMs.rtP50} ms round trip from {live.client}, {live.latency_ms.n} warm uncached 3-check requests; cold start is a model load of about {liveMs.loadS} s plus container start.
      </p>
      <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Production parity">
        <table className="tbl">
          <thead><tr><th>Check</th><th className="num">fp32 on M5 macro-F1</th><th className="num">fp32 on x86 macro-F1</th><th className="num">% decisions equal to benchmark</th><th className="num">int8 reduce_range on x86 macro-F1</th></tr></thead>
          <tbody>
            {parity.map((r) => (
              <tr key={r.check}>
                <th scope="row" className="font-normal"><code>{r.check}</code></th>
                <td className="num">{r.m5Fp32 === null ? "–" : f3(r.m5Fp32)}</td>
                <td className="num">{f3(r.x86Fp32)}</td>
                <td className="num">{f1(r.equal * 100)}%</td>
                <td className="num">{r.int8Rr === null ? "–" : `${f3(r.int8Rr)} (${r.int8Rr - r.x86Fp32 >= 0 ? "+" : "−"}${f1(Math.abs(r.int8Rr - r.x86Fp32) * 100)} pts)`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        Why the API serves fp32: the int8 file is built for CPUs with VNNI-style int8 instructions, such as Apple silicon. On x86 CPUs without VNNI it saturates and scores collapse to about 0.5. The <code>reduce_range</code> workaround avoids that but costs macro-F1 as shown in the last column, so production serves fp32 and int8 is for Apple silicon.
      </p>

      <h2 id="judge">Verdict vs a small LLM judge</h2>
      <p>Same {results.llm_judge_n_per_check}-item subsample per check, judge is Qwen3-1.7B.</p>
      <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Verdict vs LLM judge">
        <table className="tbl">
          <thead><tr><th>Check</th><th className="num">n</th><th className="num">Verdict macro-F1</th><th className="num">AUROC gain over judge [95% CI]</th><th className="num">Cohen&apos;s kappa</th></tr></thead>
          <tbody>
            {CHECKS.map((c) => {
              const j = results.laya_ft_vs_llm_judge[c];
              return (
                <tr key={c}>
                  <th scope="row" className="font-normal"><code>{c}</code></th>
                  <td className="num">{j.n}</td>
                  <td className="num">{f3(j.laya_ft_on_subsample.macro_f1)}</td>
                  <td className="num">{f3(j.auroc_delta_laya_minus_judge.delta)} [{f3(j.auroc_delta_laya_minus_judge.ci[0])}, {f3(j.auroc_delta_laya_minus_judge.ci[1])}]</td>
                  <td className="num">{f3(j.kappa)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2 id="cost">Cost per 1M checks</h2>
      <ul>
        {cost.selfHostedHours !== null && cost.rate !== null && (
          <li><strong>Self-hosted Verdict (ONNX int8, CPU)</strong>: {f1(cost.rate)} checks/s measured on the benchmark machine&apos;s CPU, which is {f1(cost.selfHostedHours)} CPU-hours per 1M checks. On a free hosted CPU tier the marginal cost is $0; throughput there is not measured here.</li>
        )}
        {cost.refs.map((r) => (
          <li key={r.name}><strong>Reference only, {r.name} as judge</strong>: {Math.round(cost.judgeTokens!)} prompt tokens per check, ${r.input_per_mtok}/M input and ${r.output_per_mtok}/M output, about <strong>${Math.round(r.usd)} per 1M checks</strong> (list price from {r.source}, read {r.as_of}).</li>
        ))}
      </ul>

      <h2 id="methodology">Methodology and dataset licences</h2>
      <ul>
        <li>Test sets are held out: they are never used for training, calibration or threshold selection. Splits are deduplicated and leakage-checked (details in <code>evals/DATASETS.md</code>).</li>
        <li>Baselines were run under the same harness. Third-party models may have seen some public test sets in their own training, so their numbers are not guaranteed to be out-of-sample.</li>
        <li>Toxicity test set is class-balanced; PII data is partly synthetic; <code>grounded</code> uses RAGTruth with the natural label rate.</li>
        <li>Calibration quality is reported as ECE and Brier score (lower is better).</li>
      </ul>
      <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Datasets">
        <table className="tbl">
          <thead><tr><th>Check</th><th>Source</th><th>Licence</th><th>Used for</th></tr></thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.source + d.check}><td><code>{d.check}</code></td><td><code>{d.source}</code></td><td className="whitespace-normal!">{d.licence}</td><td className="whitespace-normal!">{d.usedFor}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </DocLayout>
  );
}

function BySource({ check }: { check: "prompt_injection" | "grounded" }) {
  const rows = scoredSystems.filter(([, s]) => s.checks?.[check]?.by_source);
  const cols = Object.keys(rows[0][1].checks![check]!.by_source!);
  return (
    <div className="tbl-wrap" role="region" tabIndex={0} aria-label={`By source, `}>
      <table className="tbl">
        <caption>Macro-F1 by source dataset, {check}</caption>
        <thead><tr><th>System</th>{cols.map((c) => <th key={c} className="num">{c} (n={rows[0][1].checks![check]!.by_source![c].n})</th>)}</tr></thead>
        <tbody>
          {rows.map(([k, s]) => (
            <tr key={k} className={k === FEATURED ? "hl" : ""}>
              <th scope="row" className="font-normal">{s.name}</th>
              {cols.map((c) => <td key={c} className="num">{f3(s.checks![check]!.by_source![c].macro_f1)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
