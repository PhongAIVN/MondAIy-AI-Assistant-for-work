# WHAT_CHANGED — observability storytelling

## Intent and acceptance

Make the three P-004 Grafana dashboards answer, in presentation order: whether
the product is used, whether conversations are useful, whether the system is
healthy and responsive, and whether measurements are fresh and trustworthy.
Missing series remain visible as Grafana **No data**, never as a favorable zero.

Acceptance covers the hierarchy, numerator/denominator ratios, dynamic HTTP
rate interval and tail latency, LLM pricing gaps, worker and coverage freshness,
and presentation-safe LangSmith quota/staleness guidance. Contract tests cover
the JSON shape and semantic guardrails.

## Research and scope

- Authority: `AGENTS.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`.
- Metric source: `src/observability.py`; existing dashboard and observability
  tests are the executable contract.
- Scope: dashboard JSON and observability dashboard contract coverage only; no
  production code, runtime emitter, provisioning, Compose, secret or
  production-data change.
- Branch/base: `feat/observability-storytelling-20260831`, behavior SHA
  `2608736dcfb04cdca8136b6b683b53aa5acbd1e7`.
- Ownership: Codex sole writer; independent review and metric-semantic checks
  were read-only.

## Result

The reviewed behavior is integrated on `origin/main` by exact fast-forward at
`2608736d` (PR #128). The overview presents adoption, conversation quality,
HTTP tail latency/error ratio, worker health, and evidence freshness. The LLM
dashboard exposes pricing/metadata gaps and keeps `user_hash` tables in a
collapsed privacy-safe drilldown. LangSmith explains quota and staleness
limits without adding a network request.

No visual browser verification was performed. Grafana API verification did
confirm that all three dashboards loaded with UIDs:
`p004-production-overview`, `p004-llm-cost`, `p004-langsmith-traces`.

## Notification

| Audience / surface | Notification | Evidence |
| --- | --- | --- |
| P-004 operators | Dashboards are deployed and interpretation limits remain visible in-panel. | Grafana API loaded all three UIDs; health and log checks below |
| Observability reviewers | Reviewed behavior is at exact `2608736d`; local equivalent gates passed. | PR #128; validation below |
| Frontend owners | No frontend change. | Frontend unchanged |

## Merge and deploy

- Integration inventory covered all branches and worktrees. The only valid
  unintegrated batch was this observability branch; other refs were
  merged-by-squash/subsumed, superseded, stale/duplicate, or blocked by an
  already-decided architecture decision. No additional work was harvested.
- Local integration validation: 46 targeted observability tests passed; three
  dashboard JSON files parsed with `jq`; `git diff --check` passed; gitleaks
  directory scan covered 142.97 MB with no leaks.
- GitHub CI Detect affected checks were pending before merge, with no failed
  check; local equivalents ran under policy.
- Canonical dry-run passed. Before deploy, backend/worker image was `a6904181`
  and healthy. Rollback tag created: `p004-backend:rollback-2608736d`.
- Canonical deploy completed; migration upgrade ran before recreate. Backend
  and worker now use `p004-backend:2608736d`; backend is healthy.
- Public health returned `status ok` / `env production`. Grafana health
  database was `ok`, version `v12.1.1`.
- VM checksums for all three dashboards match local. Grafana API confirmed
  loaded dashboards; `grafana_error_hits=0` and backend/worker
  `log_error_hits=0` during the five-minute check.
- Frontend was unchanged. Grafana receives JSON through the bind mount and
  polls the provider every 30 seconds. The deploy script recreates only
  backend/worker per canonical policy.

## Validation

- `46 targeted observability tests` → passed.
- `jq` parse of three dashboard JSON files → passed.
- `git diff --check` → passed.
- `gitleaks` directory scan, 142.97 MB → no leaks.
- Production health, Grafana API load, dashboard checksums and five-minute
  error-hit checks → passed as recorded above.

## Rollback

Rollback target is `p004-backend:rollback-2608736d`, corresponding to the
healthy pre-deploy backend/worker image `a6904181`. Revert the integrated
observability change to restore the prior dashboard behavior; do not alter
secrets or production data.

## Residual risks

- Snapshot Gauges cannot truthfully provide selected-range worker throughput or
  error rate; affected panels label values as cumulative.
- LangSmith depends on external quota and may become stale; the static notice
  makes that limitation visible.
- Production disk usage is 86%, with approximately 22.7 GB remaining; this is
  an operational risk requiring follow-up monitoring.
- Visual layout and browser rendering remain unverified; API loading does not
  prove visual correctness.

## Record status

| Item | Value |
| --- | --- |
| Batch / date | observability-storytelling / 2026-08-31 |
| User-visible update | Presentation-oriented dashboard wording and panels |
| Integrated behavior | `2608736dcfb04cdca8136b6b683b53aa5acbd1e7` / PR #128 |
| Documentation change | This post-deploy record only |
| Deploy status | Deployed; backend and worker healthy |
| Documentation | Docs-only follow-up after deployed behavior SHA |
| Rollback | `p004-backend:rollback-2608736d` |
