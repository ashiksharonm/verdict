import raw from "@/data/live.json";
import fp32Raw from "@/data/x86_fp32.json";
import int8Raw from "@/data/x86_int8_rr.json";
import { CHECKS, type CheckName } from "./config";

type Live = {
  date: string;
  host: string;
  client: string;
  model_version: string;
  e2e: { passed: number; failed: number };
  latency_ms: { n: number; server_p50: number; server_p95: number; round_trip_p50: number; round_trip_p95: number };
  cold_start: { model_load_s: number; note: string };
  rate_limit: { parallel_requests: number; ok: number; rate_limited_429: number };
  x86_accuracy: Record<CheckName, { macro_f1: number; decisions_equal_benchmark: number }>;
};
type X86 = { checks: Record<string, Record<string, { macro_f1: number }>> };

export const live = raw as unknown as Live;

/** Macro-F1 of the system whose label starts with `prefix`, per check. */
function f1Of(src: X86, check: CheckName, prefix: string): number | null {
  const entry = Object.entries(src.checks[check] ?? {}).find(([k]) => k.startsWith(prefix));
  return entry ? entry[1].macro_f1 : null;
}

export const parity = CHECKS.map((c) => ({
  check: c,
  m5Fp32: f1Of(fp32Raw as unknown as X86, c, "fp32 (M5)"),
  x86Fp32: live.x86_accuracy[c].macro_f1,
  equal: live.x86_accuracy[c].decisions_equal_benchmark,
  int8Rr: f1Of(int8Raw as unknown as X86, c, "int8 reduce_range"),
}));

export const liveMs = {
  p50: Math.round(live.latency_ms.server_p50),
  p95: Math.round(live.latency_ms.server_p95),
  rtP50: Math.round(live.latency_ms.round_trip_p50),
  rtP95: Math.round(live.latency_ms.round_trip_p95),
  loadS: Math.round(live.cold_start.model_load_s),
};
