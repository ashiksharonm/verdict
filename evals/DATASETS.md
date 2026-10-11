# Datasets

All data is pulled from the Hugging Face Hub by `python -m verdict_train.prepare` (seed 13,
`training/configs/data.yaml`). Processed splits are not committed; their counts, class balance,
source mix and sha256 are in [`training/manifests/splits.json`](../training/manifests/splits.json).
Licences below are the ones declared on each dataset card when the splits were built (2026-10-11).

| check | source (HF id) | licence | used for |
|---|---|---|---|
| `pii` | `gretelai/gretel-pii-masking-en-v1` | Apache-2.0 | positives; redacted copies as negatives (train / validation / test splits used as-is) |
| `pii` | `databricks/databricks-dolly-15k` | CC BY-SA 3.0 | negatives (open-ended responses without source context); seeded 80/5/15 split |
| `toxicity` | `google/civil_comments` | CC0-1.0 | train/val from `train`, test from `test` |
| `prompt_injection` | `deepset/prompt-injections` | Apache-2.0 | train/val from `train`, test = `test` |
| `prompt_injection` | `jackhhao/jailbreak-classification` | Apache-2.0 | train/val from `train`, test = `test` |
| `prompt_injection` | `reshabhs/SPML_Chatbot_Prompt_Injection` | MIT | user prompts only; seeded 75/10/15 split |
| `grounded` | `wandb/RAGTruth-processed` (processed RAGTruth, Niu et al. 2024) | no licence on the card; upstream RAGTruth repo is MIT | train/val from `train` (grouped by context), test from `test` |

## Split sizes (positives = check fires)

| check | train | val | test | test composition |
|---|---|---|---|---|
| `pii` | 8,000 (4,000 pos) | 600 (300) | 2,000 (1,000) | 1,000 Gretel docs with PII; 631 redacted Gretel docs, 357 Dolly, 12 Gretel docs with only non-PII entities |
| `toxicity` | 8,000 (4,000) | 600 (300) | 2,000 (1,000) | balanced sample of civil_comments `test` |
| `prompt_injection` | 5,774 (4,044) | 827 (578) | 1,249 (891) | 116 deepset, 236 jackhhao, 897 SPML |
| `grounded` | 8,000 (3,571 not grounded) | 800 (379) | 1,200 (429) | natural RAGTruth label rate; 432 data-to-text, 382 QA, 386 summary |

Training uses a subsample of the train split (see `training/configs/train.yaml`); val is used only
for temperature scaling and threshold selection; test is used only by `make bench`.

## Leakage controls

- Text is NFKC-normalised, case-folded and whitespace-collapsed before hashing. Exact duplicates
  are removed within each split, and any train/val item whose hash or group occurs in a
  held-out split is dropped (`verdict_train.data.common.finalize_splits`).
- RAGTruth responses are grouped by their context, so the several model responses written for one
  context never straddle train and val. RAGTruth's own train and test share no contexts.
- Each Gretel document is used either as a positive or as a redacted negative, never both.
- Benchmarked third-party models may have seen some of these public test sets during their own
  training (for example, ProtectAI's injection classifier lists several public injection datasets
  in its training data). Their numbers here are therefore not guaranteed to be out-of-sample.

## Label definitions and caveats

- **toxicity**: civil_comments `toxicity >= 0.5` (fraction of raters who marked the comment toxic).
  The test set is class-balanced; real traffic is far less toxic, so precision in production will
  be lower than the balanced-test precision.
- **pii**: personal data about an individual: names, usernames, contact details, addresses,
  postcodes, dates of birth, government/medical/customer/employee IDs, account/card numbers,
  credentials, IP/MAC addresses, coordinates. Dates, cities, countries, companies and URLs alone
  are not PII. Negatives are partly synthetic (redacted Gretel documents, with `[EMAIL]`-style
  placeholders or generic phrases) and partly Dolly text, which may name public figures; those are
  labelled non-PII by this definition, which a name-based detector such as Presidio will disagree
  with. Gretel documents are themselves synthetic.
- **prompt_injection**: the union of "injection" (deepset, SPML) and "jailbreak" (jackhhao) labels.
  Prompts longer than 4,000 characters are dropped (this removes 26 of the 262 jackhhao test
  prompts: 23 jailbreak, 3 benign). deepset includes German prompts.
- **grounded**: a response is not grounded if annotators marked any `evident_conflict` or
  `baseless_info` span. The query/instruction is prepended to the context.
