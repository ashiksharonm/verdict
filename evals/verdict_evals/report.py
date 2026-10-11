"""Render `report.md` from `results.json`, and the README results table.

    python -m verdict_evals.report evals/results/2026-10-11 [--readme README.md]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml
from verdict_train.checks import CHECK_NAMES

README_START, README_END = "<!-- results:start -->", "<!-- results:end -->"


def _f(x: float | None, nd: int = 3) -> str:
    return "–" if x is None or x != x else f"{x:.{nd}f}"


def _ci(m: dict, key: str) -> str:
    lo, hi = m["ci95"].get(key, [None, None])
    return f"{_f(m[key])} [{_f(lo)}, {_f(hi)}]"


def headline_table(res: dict) -> list[str]:
    lines = ["| system | " + " | ".join(f"`{c}`" for c in CHECK_NAMES) + " |",
             "|---|" + "---|" * len(CHECK_NAMES)]
    for entry in res["systems"].values():
        if entry.get("latency_only"):
            continue
        cells = []
        for c in CHECK_NAMES:
            m = entry["checks"].get(c)
            if not m:
                cells.append("–")
                continue
            star = "*" if m.get("subsample") else ""
            cells.append(f"{_f(m['macro_f1'])} / {_f(m['auroc'])}{star}")
        lines.append(f"| {entry['name']} | " + " | ".join(cells) + " |")
    return lines


def check_tables(res: dict) -> list[str]:
    out = []
    for c in CHECK_NAMES:
        out += [f"### `{c}` (test n = {res['test_sizes'][c]})", "",
                "| system | thr | macro-F1 [95% CI] | precision | recall | AUROC [95% CI] | ECE | Brier "
                "| recall@1%FPR | recall@5%FPR |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for entry in res["systems"].values():
            m = entry.get("checks", {}).get(c)
            if not m:
                continue
            name = entry["name"] + (f" (n={m['n']} subsample)" if m.get("subsample") else "")
            hard = "" if entry.get("probabilistic", True) else " (0/1 output)"
            out.append(f"| {name}{hard} | {_f(m['threshold'], 2)} | {_ci(m, 'macro_f1')} | {_f(m['precision'])} "
                       f"| {_f(m['recall'])} | {_ci(m, 'auroc')} | {_f(m['ece'])} | {_f(m['brier'])} "
                       f"| {_f(m['recall_at_fpr_1'])} | {_f(m['recall_at_fpr_5'])} |")
        out.append("")
    return out


def source_tables(res: dict) -> list[str]:
    out = []
    for c in ("prompt_injection", "grounded"):
        rows = [(e["name"], e["checks"][c]["by_source"]) for e in res["systems"].values()
                if c in e.get("checks", {}) and "by_source" in e["checks"][c]]
        if not rows:
            continue
        sources = sorted({s for _, b in rows for s in b})
        out += [f"**`{c}` macro-F1 by source**", "", "| system | " + " | ".join(
            f"{s} (n={rows[0][1].get(s, {}).get('n', '?')})" for s in sources) + " |",
            "|---|" + "---|" * len(sources)]
        for name, b in rows:
            out.append(f"| {name} | " + " | ".join(_f(b.get(s, {}).get("macro_f1")) for s in sources) + " |")
        out.append("")
    return out


def latency_table(res: dict) -> list[str]:
    out = ["| system | device | batch-1 p50 ms | batch-1 p95 ms | throughput (items/s) at batch |",
           "|---|---|---|---|---|"]
    for entry in res["systems"].values():
        lat = entry.get("latency_batch1")
        if not lat:
            continue
        thr = entry.get("throughput")
        if thr is None:
            # aggregate over checks: total items / total time
            items = sum(m["throughput"]["calls"] * m["throughput"]["batch_size"] for m in entry["checks"].values())
            secs = sum(m["throughput"]["calls"] * m["throughput"]["batch_size"] / m["throughput"]["throughput_per_s"]
                       for m in entry["checks"].values())
            bs = max(m["throughput"]["batch_size"] for m in entry["checks"].values())
            tp = items / secs if secs else float("nan")
        else:
            tp, bs = thr["throughput_per_s"], thr["batch_size"]
        out.append(f"| {entry['name']} | {entry['device']} | {_f(lat['p50_ms'], 1)} | {_f(lat['p95_ms'], 1)} "
                   f"| {_f(tp, 1)} @ {bs} |")
    return out


def robustness_table(res: dict) -> list[str]:
    rows = [(e["name"], e["robustness"]) for e in res["systems"].values() if e.get("robustness")]
    if not rows:
        return []
    names = list(rows[0][1])
    out = ["| system | original recall | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for name, rb in rows:
        orig = next(iter(rb.values()))["original_recall"]
        out.append(f"| {name} | {_f(orig)} | " + " | ".join(_f(rb[n]["recall"]) for n in names) + " |")
    return out


def judge_table(res: dict) -> list[str]:
    comp = res.get("laya_ft_vs_llm_judge")
    if not comp:
        return []
    judge = res["systems"]["llm_judge"]
    out = ["| check | n | Verdict macro-F1 | judge macro-F1 | Verdict − judge AUROC [95% CI] | Cohen's κ |",
           "|---|---|---|---|---|---|"]
    for c, v in comp.items():
        d = v["auroc_delta_laya_minus_judge"]
        out.append(f"| `{c}` | {v['n']} | {_f(v['laya_ft_on_subsample']['macro_f1'])} "
                   f"| {_f(judge['checks'][c]['macro_f1'])} | {_f(d['delta'])} [{_f(d['ci'][0])}, {_f(d['ci'][1])}] "
                   f"| {_f(v['kappa'])} |")
    return out


def cost_section(res: dict, pricing_path: Path) -> list[str]:
    if not pricing_path.exists():
        return []
    pricing = yaml.safe_load(pricing_path.read_text())
    out = []
    sys_ = res["systems"]
    int8 = sys_.get("laya_ft_int8")
    if int8:
        items = secs = 0.0
        for m in int8["checks"].values():
            t = m["throughput"]
            n = t["calls"] * t["batch_size"]
            items += n
            secs += n / t["throughput_per_s"]
        rate = items / secs
        hours = 1e6 / rate / 3600
        out.append(f"- **Self-hosted Verdict (ONNX int8, CPU)**: {_f(rate, 1)} checks/s measured on the M5 CPU over "
                   f"the full test set at batch 16 → {_f(hours, 1)} CPU-machine-hours per 1M checks. On a free "
                   "Hugging Face CPU Space the marginal cost is $0 (throughput there is not yet measured).")
    judge = sys_.get("llm_judge")
    if judge and "prompt_tokens_mean" in judge:
        tok = judge["prompt_tokens_mean"]
        for ref in pricing.get("references", []):
            cost = 1e6 * (tok * ref["input_per_mtok"] + ref.get("output_tokens", 1) * ref["output_per_mtok"]) / 1e6
            out.append(f"- **Reference only — {ref['name']} as judge**: {_f(tok, 0)} prompt tokens/check (mean of the "
                       f"judge prompts above, Qwen tokenizer) × ${ref['input_per_mtok']}/M input + "
                       f"{ref.get('output_tokens', 1)} output token × ${ref['output_per_mtok']}/M ≈ "
                       f"**${_f(cost, 0)} per 1M checks** (list price from {ref['source']}, read {ref['as_of']}).")
    return out


def render(res: dict, pricing_path: Path) -> str:
    env = res["environment"]
    lines = [f"# Verdict benchmark — {env['date']}", "",
             f"Hardware: {env['machine']} ({env['platform']}); torch {env.get('torch')}, transformers "
             f"{env.get('transformers')}, onnxruntime {env.get('onnxruntime')}, laya {env.get('laya')}.",
             f"Bootstrap: {res['n_boot']} resamples, 95% percentile intervals. Scores are the probability "
             "that the check fires; Verdict uses per-check thresholds fitted on val, every other system "
             "its natural rule (0.5, or a hard 0/1 output).", ""]
    if res.get("fixture"):
        lines += ["**Fixture smoke run (32 hand-written items) — not a benchmark.**", ""]
    lines += ["## Summary (macro-F1 / AUROC)", "", *headline_table(res), "",
              f"\\* LLM judge scored on a fixed stratified subsample of {res['llm_judge_n_per_check']} items per check.",
              "", "## Per-check metrics", "", *check_tables(res), *source_tables(res),
              "## Latency and throughput", "", *latency_table(res), ""]
    notes = res.get("notes", [])
    if notes:
        lines += ["Notes:", *[f"- {n}" for n in notes], ""]
    rob = robustness_table(res)
    if rob:
        lines += ["## Prompt-injection robustness (recall on obfuscated attacks)", "",
                  "Every positive in the injection test set, rewritten five ways (`evals/verdict_evals/obfuscate.py`).",
                  "", *rob, ""]
    jt = judge_table(res)
    if jt:
        lines += ["## Verdict vs LLM judge on the same subsample", "", *jt, ""]
    cost = cost_section(res, pricing_path)
    if cost:
        lines += ["## Cost per 1M checks", "", *cost, ""]
    return "\n".join(lines)


def readme_block(res: dict, rel: str) -> str:
    return "\n".join([README_START, "", f"Held-out test sets, macro-F1 / AUROC ([full report]({rel}/report.md), "
                      f"generated from [`results.json`]({rel}/results.json)):", "", *headline_table(res), "",
                      f"\\* LLM judge on a fixed stratified subsample of {res['llm_judge_n_per_check']} items per check.",
                      "", README_END])


def write_report(out_dir: Path, readme: Path | None = None) -> None:
    res: dict[str, Any] = json.loads((out_dir / "results.json").read_text())
    pricing = Path(__file__).resolve().parents[1] / "configs" / "pricing.yaml"
    (out_dir / "report.md").write_text(render(res, pricing) + "\n")
    if readme and readme.exists():
        text = readme.read_text()
        rel = out_dir.resolve().relative_to(readme.resolve().parent).as_posix()
        block = readme_block(res, rel)
        pat = re.compile(re.escape(README_START) + ".*?" + re.escape(README_END), re.S)
        text = pat.sub(block, text) if pat.search(text) else text + "\n" + block + "\n"
        readme.write_text(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results_dir")
    ap.add_argument("--readme", default=None)
    args = ap.parse_args()
    write_report(Path(args.results_dir), Path(args.readme) if args.readme else None)


if __name__ == "__main__":
    main()
