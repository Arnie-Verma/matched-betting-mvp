# matched-betting-mvp

Monorepo for an Outmatched.com-style matched betting SaaS.

## Structure
- apps/web      -> Next.js + Tailwind + shadcn
- apps/api      -> FastAPI (Python)
- apps/worker   -> Python workers (odds scraping, queue jobs)
- packages/shared -> Shared types/schemas/utils
- infra         -> Docker compose, env templates, deployment bits
- .github/workflows -> CI pipelines (lint, type-check, test, build)

## Step 0 status
0.1: Monorepo scaffold ✅
0.2: Initialize web (Next.js) ⏳
0.3: Initialize api (FastAPI) ⏳
0.4: Dev Docker compose (pg, redis, services) ⏳
0.5: CI: lint/type-check/test/build ⏳
