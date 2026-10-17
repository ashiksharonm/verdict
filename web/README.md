# web

Next.js 15 (App Router, TypeScript, Tailwind) site: landing, playground, docs, benchmarks and a Supabase-backed dashboard for API keys and usage.

```
cd web
cp .env.example .env.local   # public values only
npm ci
npm run dev                  # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

`scripts/prebuild.mjs` runs before dev, build, test and typecheck. It copies the newest `evals/results/<date>/results.json`, the licence table from `evals/DATASETS.md` and `evals/configs/pricing.yaml` into `src/data/` (git-ignored), so the benchmark numbers on the site are never typed by hand.

Environment (all public): `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`. Never put a service-role key in this directory.

Deploy on Vercel Hobby: Root Directory `web`, framework Next.js, and keep "Include source files outside of the Root Directory" enabled so the prebuild can read `evals/`.
