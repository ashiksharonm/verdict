import raw from "@/data/results.json";
import pricing from "@/data/pricing.json";
import meta from "@/data/meta.json";
import { CHECKS, type CheckName } from "./config";

export type Metrics = {
  threshold: number;
  n: number;
  positives: number;
  precision: number;
  recall: number;
  macro_f1: number;
  auroc: number;
  ece: number;
  brier: number;
  recall_at_fpr_1: number;
  recall_at_fpr_5: number;
  subsample: boolean;
  ci95: { macro_f1: [number, number]; auroc: [number, number] } & Record<string, [number, number]>;
  throughput: { calls: number; batch_size: number; p50_ms: number; p95_ms: number; throughput_per_s: number };
  by_source?: Record<string, { n: number; macro_f1: number }>;
};
export type Latency = { calls: number; batch_size: number; p50_ms: number; p95_ms: number; throughput_per_s: number };
export type System = {
  name: string;
  family: string;
  device: string;
  batch_size: number;
  checks?: Partial<Record<CheckName, Metrics>>;
  robustness?: Record<string, { recall: number; original_recall: number }> | null;
  latency_batch1?: Latency | null;
  throughput?: Latency;
  prompt_tokens_mean?: number;
  latency_only?: boolean;
};
type Judge = Record<string, { n: number; kappa: number; laya_ft_on_subsample: { macro_f1: number }; auroc_delta_laya_minus_judge: { delta: number; ci: [number, number] } }>;
type Results = {
  environment: Record<string, string>;
  test_sizes: Record<CheckName, number>;
  llm_judge_n_per_check: number;
  n_boot: number;
  systems: Record<string, System>;
  laya_ft_vs_llm_judge: Judge;
};

export const results = raw as unknown as Results;
export const resultsDir: string = meta.resultsDir;
export const FEATURED = "laya_ft_int8";
export const featured = results.systems[FEATURED];
export const scoredSystems = Object.entries(results.systems).filter(([, s]) => s.checks && !s.latency_only);

export const f3 = (x: number) => x.toFixed(3);
export const f1 = (x: number) => x.toFixed(1);

/** Aggregate throughput of one system over all checks (items / seconds), as in the report generator. */
export function aggregateThroughput(s: System): { rate: number; batch: number } | null {
  if (s.throughput) return { rate: s.throughput.throughput_per_s, batch: s.throughput.batch_size };
  const ms = Object.values(s.checks ?? {});
  if (!ms.length) return null;
  let items = 0;
  let secs = 0;
  for (const m of ms) {
    const n = m.throughput.calls * m.throughput.batch_size;
    items += n;
    secs += n / m.throughput.throughput_per_s;
  }
  return { rate: items / secs, batch: Math.max(...ms.map((m) => m.throughput.batch_size)) };
}

export function costPerMillion() {
  const t = aggregateThroughput(featured);
  const selfHostedHours = t ? 1e6 / t.rate / 3600 : null;
  const judgeTokens = results.systems.llm_judge?.prompt_tokens_mean;
  const refs = judgeTokens
    ? (pricing.references as { name: string; input_per_mtok: number; output_per_mtok: number; output_tokens?: number; source: string; as_of: string }[]).map((r) => ({
        ...r,
        usd: (judgeTokens * r.input_per_mtok + (r.output_tokens ?? 1) * r.output_per_mtok),
      }))
    : [];
  return { rate: t?.rate ?? null, selfHostedHours, judgeTokens, refs };
}

export { CHECKS };
