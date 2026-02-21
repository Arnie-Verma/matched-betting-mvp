# Bookmaker Operating System

## Purpose
Provide one repeatable system to discover, implement, validate, roll out, and operate bookmakers at scale.

## Scope
This is the primary operating guide for scaling to 100+ bookmakers and 1,000+ users.
Use this with:
- `DISCOVERY_SUMMARY.md` (what is known per platform)
- `BOOKMAKER_IMPLEMENTATION_GUIDE.md` (how to implement)
- `VALIDATION_FRAMEWORK.md` (quality gates and scoring)
- `Unibet.md` (bookmaker runbook example)

## Product Performance Targets
1. Full refresh for core non-proxy books: P95 <= 12s.
2. Filter response from cached/current data: P95 <= 2s.
3. Proxy/anti-bot books (for example TAB): P95 <= 25s with explicit UI notice.
4. Partial results must always render while slow books continue in background.

## Local Pre-Production Mode (Current Reality)
This methodology is designed to be executed locally first to get as close to production-ready as possible.
1. Local canary replaces always-on canary:
   - Run repeated refresh/validation cycles for 30-60 minutes minimum.
2. Local ramp replaces traffic ramp:
   - Ramp by scope: one competition -> all target competitions -> all target sports.
3. Cloud/always-on canary is optional later:
   - Run a 24h canary only when staging/cloud is available.

## Environment Profiles
1. Local/dev profile:
   - Use conservative concurrency (for example `SCRAPER_BATCH_SIZE=1`) for Docker stability.
2. Staging profile:
   - Production-like behavior with reduced caps.
3. Production profile:
   - Higher per-platform concurrency caps, with SLO alerts and rollback thresholds.
4. Concurrency is an environment concern, not an architecture limitation.

## Non-Negotiable Guardrails
1. Bookmaker isolation:
   - Each bookmaker is an independent job with its own timeout/retry/circuit-breaker state.
   - One bookmaker failure must not block refresh completion for others.
2. Platform separation:
   - Build platform adapters (Entain, Kindred, Punterstech, BetMakers, Generation Web, BetCloud).
   - Keep bookmaker-specific code to config and narrow edge-case transforms.
3. Strict scraper contract:
   - Canonical constructor, canonical scraper interface, canonical output schema.
4. Freshness over history:
   - Keep current odds as primary truth.
   - Keep short diagnostic history only.
5. Fast read path:
   - Matcher reads from current-state/read-optimized data structures.
   - Avoid API hot-path N+1/in-memory heavy grouping.
6. Observable by default:
   - Mandatory per-bookmaker metrics: success rate, latency, count deltas, validation score, last success.

## Lifecycle (Required)
1. `backlog`
2. `discovery_complete`
3. `adapter_ready`
4. `config_ready`
5. `validation_passed`
6. `canary_active`
7. `active`
8. `degraded` or `disabled`

## Mandatory Artifacts Per Bookmaker
1. Metadata record in seed/config (`platform`, `scraper_class`, `requires_proxy`, `priority_tier`).
2. Discovery evidence (endpoint/auth/anti-bot profile).
3. Validation evidence (latest pass/fail report).
4. Runbook notes (known failure signatures, rollback procedure).

## Quality Gates (Go/No-Go)
1. Parse gate:
   - Non-zero expected event/odds counts for target sports.
2. Normalization gate:
   - Grouping alignment with reference books.
3. Validation gate:
   - Meets minimum threshold and no hard FAIL in priority competitions.
   - Scope policy is explicit per bookmaker x competition:
     - out-of-scope => `SKIP`
     - in-scope zero-event => `FAIL`
4. Performance gate:
   - Bookmaker scrape latency inside platform SLO band.
5. Reliability gate:
   - Success rate above threshold across repeated runs.

## Runtime Architecture
1. Queue execution:
   - Enqueue per-bookmaker jobs with bounded global and per-platform concurrency.
   - Separate queues for `standard_books` and `proxy_books`.
   - Active bookmaker set is derived from DB active rows plus freeze policy at runtime.
   - Emit scheduler discipline metrics (`observed_max_in_flight_global`, per-platform max in-flight).
2. Adapter pipeline:
   - `fetch -> parse -> normalize -> validate -> persist -> publish_status`.
3. Failure control:
   - Circuit breaker states: `closed`, `open`, `half_open`.
   - Open on repeated failures/timeouts/validation collapse.
4. Degrade behavior:
   - Keep partial results available and mark bookmaker degraded.

## Data Strategy (No Bloat)
1. Primary odds tables represent current truth.
2. Retention policy:
   - Current odds: keep.
   - Previous versions: short TTL only (for diagnostics).
   - Past events: purge quickly after completion.
3. Add partitioning when odds volume grows.
4. Keep indexes aligned to matcher keys and `is_current` hot paths.

## Frontend/UX Rules
1. Initial load shows refreshing state and accepts partial bookmaker completion.
2. Filtering must operate on current cached/read-model data.
3. Manual refresh enqueues async jobs and surfaces per-bookmaker status.
4. Show explicit performance notice for slow/proxy books.

## Ownership Model
1. Platform owner:
   - Owns adapter behavior across all platform bookmakers.
2. Bookmaker owner:
   - Owns config correctness and bookmaker-specific mapping issues.
3. On-call owner:
   - Owns health alerts, breaker handling, and recovery workflow.

## Operating Cadence
1. Weekly planning:
   - Prioritize by business value and platform leverage.
2. Daily execution:
   - Move bookmakers through lifecycle states with WIP limits.
3. Weekly review:
   - Review promotions/demotions, failure rates, and SLO drift.

## WIP and Rollout Rules
1. WIP limits:
   - Max 1 new platform adapter in progress.
   - Max 5 bookmakers in canary at one time.
2. Rollout:
   - Cohort by platform.
   - Local: canary -> scope ramp (1 competition -> all target competitions -> full target sports) -> active.
   - Cloud (optional later): traffic ramp (10% -> 50% -> 100%).
3. Freeze rule:
   - Pause onboarding if active reliability drops below threshold.
   - During Phase A hardening, Unibet freeze is code-enforced via `BOOKMAKER_FREEZE_UNIBET=true` until explicit GO.

## Metrics Dashboard (Per Bookmaker)
1. Last successful scrape time.
2. Success rate (local: 15m/60m windows; cloud: 1h/24h).
3. P50/P95 scrape latency.
4. Event/odds count deltas.
5. Validation score trend.
6. Breaker state and open duration.
7. Scheduler max in-flight (global and per-platform).

## Security Access Policy (Current)
1. Refresh status endpoint (`GET /odds/refresh/status`):
   - allow owner (`payload.requested_by`) and explicitly shared merged readers (`payload.shared_user_ids`)
   - deny cross-user access with `403`
2. Scraper health endpoints:
   - `/health/scrapers`, `/health/detailed`, and `/health/telemetry` require ops-role or internal-token access
   - broad authenticated-by-default access is denied
   - telemetry default response path is aggregate-only (no raw sample events)

## Unibet Scale-Proof Method (Repeatable Template)
Use Unibet as the proof case for scaling from Entain/Punterstech to any new bookmaker.

### Step 1: Define target scope before coding
1. Choose target sports and competitions explicitly.
2. Choose target market types explicitly (for example match winner and moneyline only).
3. Define expected output contract:
   - event coverage
   - market coverage
   - selection key correctness
   - odds sanity

### Step 2: Build or reuse platform adapter
1. Reuse existing platform adapter if possible.
2. If new adapter is required, implement only canonical scraper interface.
3. Keep bookmaker-specific details in config and mapping tables.

### Step 3: Add bookmaker config only
1. Add `platform`, `scraper_class`, `base_url`, `requires_proxy`, `priority_tier`.
2. Keep bookmaker disabled until gates pass.
3. Record known anti-bot behavior in runbook notes.

### Step 4: Add normalization before activation
1. Add competition name mappings.
2. Add participant/team name mapping edge cases.
3. Confirm deterministic `selection_key` mapping (`home`, `away`, `draw`).
4. Enforce matcher market hygiene:
   - exclude futures/outrights/partials from matcher path
   - keep expected market shape only (3-way soccer; 2-way where applicable)
   - do not allow `selection_key=other` in current matcher markets

### Step 5: Run proof validation on priority competitions
1. Validate each target competition separately (not one global check only).
2. Require:
   - event coverage at or above threshold vs reference
   - no critical odds anomalies beyond threshold
   - correct market shape (expected selections present)
3. Validation semantics rule:
   - If reference has no eligible fixtures for that competition window, do not treat as hard FAIL.
   - Use `N_A` for reference and `SKIP` for non-reference books, then re-run on next eligible window before GO.
   - If bookmaker is explicitly out-of-scope for a competition, classify as `SKIP` (not `FAIL`) for that competition.
4. Save validation output as onboarding evidence.

### Step 6: Run performance proof
1. Measure scrape duration for this bookmaker in isolation.
2. Measure scrape duration during full multi-bookmaker refresh.
3. Verify this bookmaker does not degrade fast-tier latency targets.

### Step 7: Canary release
1. Enable bookmaker in canary mode only.
2. Local required canary:
   - Run 30-60 minutes minimum with repeated refreshes.
   - Target at least 10-20 refresh cycles covering all target competitions.
3. Optional cloud canary later:
   - Run 24h when an always-on environment exists.
4. Monitor:
   - success rate
   - breaker opens
   - validation status trend
   - event/odds count drift

### Step 8: Promote or rollback
1. Promote to `active` only if canary passes all gates.
2. If failed, set `degraded` or `disabled`, capture failure signature, fix, and retry canary.

### Step 9: Convert proof to reusable platform recipe
1. Document the exact adapter + mapping pattern used for Unibet.
2. Reuse the same rollout checklist for next bookmakers on same or similar platform.
3. Avoid custom rollout logic per bookmaker.

### Step 10: Post-promotion watch window
1. Keep elevated monitoring for 7 days.
2. Freeze new bookmaker onboarding if failure rate rises materially.

## Engineer Brief (Copy/Paste)
Use this brief when assigning bookmaker onboarding work:

1. Implement bookmaker onboarding using the "Unibet Scale-Proof Method" in this document.
2. Do not enable bookmaker until all gates pass.
3. Validate each target competition independently (not just one default competition).
4. Confirm selection key stability and market-type hygiene before activation.
5. Run local canary (30-60 min, repeated cycles) with metrics and validation evidence.
6. If cloud staging exists, run optional 24h canary before broad activation.
7. Provide a final go/no-go report with:
   - validation summary
   - latency summary
   - breaker/health summary
   - rollback plan

## Activation Gates (Operational)
Bookmaker cannot move to `active` unless all are true:
1. Structural and event coverage checks pass for target competitions.
2. Probability anomaly thresholds are within limits.
3. Golden fixture checks pass for relevant competitions.
4. Local canary SLOs pass (30-60 min, repeated cycles); cloud 24h canary is optional later.
5. No unresolved breaker flapping.

## Immediate Backlog (Repo)
1. Standardize scraper constructor/interface contract.
2. Move per-bookmaker runtime policy into config.
3. Add lifecycle status storage for bookmaker state.
4. Add canary/ramp selection controls in refresh orchestration.
5. Add alert rules on latency, stale-success age, and breaker state.

## Outstanding Build Items For Reliable Scale
These are still required to make onboarding low-risk at 100+ bookmakers:
1. Enforce lifecycle states in code (not doc-only), including transition guards.
2. Enforce activation gates in code (block promotion when gates fail).
3. Validate all target competitions for a bookmaker during onboarding, not just one mapped default.
4. Add per-bookmaker policy config (timeouts, retries, concurrency class, proxy class).
5. Add canary controls and exposure ramp controls in refresh selection.
6. Add first-class bookmaker health dashboard with alerting hooks.
7. Add automated onboarding report generation (go/no-go artifact).
8. Evolve matcher from in-request set-based preloading to dedicated read-model/materialized serving for sustained high load.

## Phase A Sync Status (Post PR-R2/PR-R3/PR-S1)
Implemented now:
1. Bounded concurrency scheduler with global and per-platform caps.
2. Runtime active-bookmaker derivation from DB + freeze policy (no static active-list control path).
3. Matcher hot-path N+1 reduction through set-based bulk preloading.
4. Ownership/shared-reader authorization on refresh status endpoint.
5. Auth/internal access policy on scraper health endpoints.

Known constraints still open:
1. Lifecycle transitions and activation gates are still partially doc-driven.
2. Refresh ACL metadata is Redis payload-based (durable ACL/audit model not yet implemented).
3. Health visibility exists via endpoints but not a dedicated operational dashboard.

Planned follow-up work:
1. Tighten canary thresholds after longer-run telemetry under bounded scheduler.
2. Add durable refresh-job ACL/audit logging.
3. Build matcher read model for sustained 100+ bookmaker load.

## Definition Of Scaled
1. New bookmaker onboarding is mostly config + validation.
2. Single-bookmaker outages do not degrade overall product behavior.
3. Health issues are visible and actionable within minutes.
4. Database growth stays bounded and query latency remains stable.
