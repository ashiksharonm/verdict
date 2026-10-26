import Link from "next/link";
import { CHECKS, CHECK_INFO } from "@/lib/config";
import { FEATURED, f3, results, scoredSystems } from "@/lib/results";

export default function ResultsTable({ compact = false }: { compact?: boolean }) {
  const rows = compact
    ? scoredSystems.filter(([k]) => ["laya_ft_int8", "laya_zeroshot", "presidio", "keyword", "nli", "protectai", "llm_judge"].includes(k))
    : scoredSystems;
  return (
    <div className="tbl-wrap" role="region" tabIndex={0} aria-label="Results">
      <table className="tbl">
        <caption>
          Macro-F1 / AUROC on held-out test sets (n = {CHECKS.map((c) => `${results.test_sizes[c].toLocaleString("en-US")} ${c}`).join(", ")}). Dashes: system does not cover that check. LLM judge scored on a {results.llm_judge_n_per_check}-item subsample per check.{" "}
          {compact && <Link href="/benchmarks" className="link">Full tables</Link>}
        </caption>
        <thead>
          <tr>
            <th scope="col">System</th>
            {CHECKS.map((c) => (
              <th key={c} scope="col" className="num">
                {CHECK_INFO[c].label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, s]) => (
            <tr key={key} className={key === FEATURED ? "hl" : ""}>
              <th scope="row" className="font-normal">
                {s.name}
                {s.checks?.pii?.subsample ? "*" : ""}
              </th>
              {CHECKS.map((c) => {
                const m = s.checks?.[c];
                return (
                  <td key={c} className="num">
                    {m ? `${f3(m.macro_f1)} / ${f3(m.auroc)}` : "–"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
