import data from "@/data/datasets.json";

export type DatasetRow = { check: string; source: string; licence: string; usedFor: string };

/** Rows of the licence table in evals/DATASETS.md, extracted by scripts/prebuild.mjs. */
export function parseDatasetTable(): DatasetRow[] {
  return data as DatasetRow[];
}
