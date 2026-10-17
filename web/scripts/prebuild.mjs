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
cpSync(join(repo, "evals", "DATASETS.md"), join(out, "DATASETS.md"));

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
writeFileSync(join(out, "meta.json"), JSON.stringify({ resultsDir: latest }));
console.log(`prebuild: copied results from evals/results/${latest}`);
