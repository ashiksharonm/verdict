// Copies the committed benchmark artefacts into web/src/data so the site never hand-types a number.
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const web = resolve(here, "..");
const repo = resolve(web, "..");
const out = join(web, "src", "data");
mkdirSync(out, { recursive: true });

const resultsRoot = join(repo, "evals", "results");
if (!existsSync(resultsRoot)) {
  console.error(`prebuild: ${resultsRoot} not found. On Vercel enable "Include source files outside of the Root Directory".`);
  process.exit(1);
}
const dirs = readdirSync(resultsRoot, { withFileTypes: true })
  .filter((d) => d.isDirectory() && existsSync(join(resultsRoot, d.name, "results.json")))
  .map((d) => d.name)
  .sort();
if (dirs.length === 0) {
  console.error("prebuild: no evals/results/<date>/results.json found");
  process.exit(1);
}
const latest = dirs[dirs.length - 1];
cpSync(join(resultsRoot, latest, "results.json"), join(out, "results.json"));
const datasets = [];
for (const line of readFileSync(join(repo, "evals", "DATASETS.md"), "utf8").split("\n")) {
  if (!line.startsWith("| `")) continue;
  const c = line.split("|").slice(1, -1).map((x) => x.trim().replace(/`/g, ""));
  if (c.length === 4 && !/^\d/.test(c[1])) datasets.push({ check: c[0], source: c[1], licence: c[2], usedFor: c[3] });
}
if (datasets.length === 0) {
  console.error("prebuild: could not parse the dataset table in evals/DATASETS.md");
  process.exit(1);
}
writeFileSync(join(out, "datasets.json"), JSON.stringify(datasets, null, 2));

// pricing.yaml is a flat list of references; parse it without a YAML dependency.
const refs = [];
let cur = null;
for (const line of readFileSync(join(repo, "evals", "configs", "pricing.yaml"), "utf8").split("\n")) {
  const item = line.match(/^\s*-\s+name:\s*(.+)$/);
  if (item) {
    cur = { name: item[1].trim() };
    refs.push(cur);
    continue;
  }
  const kv = line.match(/^\s+(\w+):\s*(.+)$/);
  if (kv && cur) {
    const v = kv[2].trim();
    cur[kv[1]] = /^[\d.]+$/.test(v) ? Number(v) : v;
  }
}
writeFileSync(join(out, "pricing.json"), JSON.stringify({ references: refs }, null, 2));
// Live API measurements and x86 parity runs (newest *-live dir wins).
const liveDirs = readdirSync(resultsRoot, { withFileTypes: true })
  .filter((d) => d.isDirectory() && d.name.endsWith("-live") && existsSync(join(resultsRoot, d.name, "live.json")))
  .map((d) => d.name)
  .sort();
const need = (name, from) => {
  if (!from || !existsSync(from)) {
    console.error(`prebuild: missing ${name} under evals/results`);
    process.exit(1);
  }
};
const liveSrc = liveDirs.length ? join(resultsRoot, liveDirs[liveDirs.length - 1], "live.json") : null;
const fp32Src = join(resultsRoot, "2026-10-18-x86-fp32", "x86_metrics.json");
const int8Src = join(resultsRoot, "2026-10-18-x86-int8-reduce-range", "x86_metrics.json");
need("*-live/live.json", liveSrc);
need("2026-10-18-x86-fp32/x86_metrics.json", fp32Src);
need("2026-10-18-x86-int8-reduce-range/x86_metrics.json", int8Src);
cpSync(liveSrc, join(out, "live.json"));
cpSync(fp32Src, join(out, "x86_fp32.json"));
cpSync(int8Src, join(out, "x86_int8_rr.json"));
writeFileSync(join(out, "meta.json"), JSON.stringify({ resultsDir: latest }));
console.log(`prebuild: copied results from evals/results/${latest}`);
