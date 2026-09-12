# WHAT_CHANGED — P-004 LLM cost dashboard

| Field | Value |
| --- | --- |
| Task ID | `p004-llm-cost-dashboard` |
| Record schema | `v2` |
| Status | Validated, uncommitted |
| Date | `2026-08-28` |
| Lead | Codex |
| Agents / lanes | `Codex: dashboard/report writer; Antigravity: read-only test design and independent validation` |
| Base SHA | `6bcb41af5ab8b41ec0b7bdebcbd3c8be6addab4e` |
| Head / merge SHA | uncommitted by explicit brief |
| PR / issue / ADR | `BRIEF.md`; `docs/projects/product/prd.md`; `docs/ADR/domain_split.md` §6.9 |

## Intent and acceptance criteria

- Intent: add one provisioned Grafana dashboard that answers supported token, cost, latency, system-health and measurement-quality questions using production-confirmed Prometheus metrics.
- Observable acceptance criteria: every target uses an exact metric/label from `BRIEF.md`; no unsupported LLM-latency panel; JSON parses and matches the existing Grafana dashboard shape; `user_hash` is never joined to identity.
- Non-goals: Python/metric changes, edits to the three existing dashboards, VM/Grafana configuration, commit, push or deploy.

## Bug-fix generalization

- Change kind: not a bug fix.
- Bug class and violated invariant: not applicable.
- Root cause and shared fix boundary: not applicable.
- Dossier: not applicable.
- Sibling cases and counterexample: an attractive panel backed only by a source metric absent from the production-confirmed list must be omitted, not shipped empty.

## Changes

- Observable behavior: 11 panels answer cumulative token usage, attributed user cost, HTTP/tool-loop quantiles, worker health, measurement gaps and product state using only the production-confirmed metric list.
- Components/files: `observability/grafana/dashboards/p004-llm-cost.json`, `BAOCAO.md`, this evidence record.
- Config/migration/API compatibility: static dashboard only; no provisioning, schema or API change.

## Agent handoffs and integration

- Ownership boundaries: Codex is the sole writer; Antigravity is read-only.
- Integration order/conflicts: no overlapping writer; preserve untracked user-provided `BRIEF.md`.
- Independent review: Antigravity PASS on exact dashboard SHA256 `7976726e8bfbfc8a33513c7d3b533e26442a3a50c9264e852709c7c909aea6d0` and report SHA256 `c9a62866c405e39dbaecdc0b3dbdac8be230695b8589d705e3765b8e70661e87`; no Blocker/High/Medium finding.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `python3 -c 'import json; json.load(open("observability/grafana/dashboards/p004-llm-cost.json"))'` | pass | 2026-08-28 |
| Ad-hoc static matrix: schema/IDs/grid/datasource/allowlist/quantiles/Gauge semantics/privacy | `STATIC_DASHBOARD_OK`; 11 panels, 19 targets, 10 allowed metrics | 2026-08-28 |
| Same validator with intentional invalid mutations | 6/6 local and 7/7 independent negative probes rejected for the intended reason | 2026-08-28 |
| `PYTHONDONTWRITEBYTECODE=1 rtk pytest -q -p no:cacheprovider tests/test_services/v1/test_llm_observability.py tests/test_observability_agent_metrics.py` | `9 passed` | 2026-08-28 |
| `docker compose -f docker-compose.prod.yml config --no-interpolate --quiet` | pass | 2026-08-28 |
| `wc -l BAOCAO.md` plus section validator | 20 lines, exactly A/B/C | 2026-08-28 |
| Antigravity exact-content final gate | PASS; hashes stable before/after; no Blocker/High/Medium | 2026-08-28 |

Proof level / claim ceiling: local static/config plus independent exact-content review — dashboard JSON, PromQL shape, metric/label authority and privacy contract are validated; production rendering/data are not claimed.

Tests not run and reason: no live Grafana import/render or Prometheus query because the brief denies production Grafana access. Full repository suite was not run because the change is an isolated static dashboard; focused metric-source tests passed. Normal Compose interpolation was not validated because required production secrets such as `MINIO_ACCESS_KEY` are intentionally absent; `--no-interpolate` syntax/model validation passed without loading secrets.

## Risk, rollback and follow-up

- Risks: a correctly named LLM metric can legitimately show no data before its first observation; static validation cannot prove Grafana rendering without production access. Source currently contains four extra LLM metrics and a narrower HTTP-duration label set than `BRIEF.md`; the dashboard deliberately follows the production-confirmed brief instead of inferring deployment state from source.
- Rollback: remove the new dashboard and restore the prior `BAOCAO.md`; no runtime or data rollback.
- Follow-up: confirm/expose the LLM latency histogram, total-cost/call denominators and worker tick denominator in production before adding LLM latency, full cost or percentage panels; optionally promote the ad-hoc validator into a persistent regression test.

## Merge and deployment

- Merge status: not committed per brief.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: base SHA above.

| Item | Value |
| --- | --- |
| Batch / date | `p004-llm-cost-dashboard` / `2026-08-28` |
| User-visible update | New Grafana dashboard for production-confirmed LLM/system metrics. |
| Scope | Grafana dashboard only; no deploy |
| Source | uncommitted worktree based on `6bcb41a` |
| Validation | JSON/static matrix; negative probes; focused `9 passed`; Compose no-interpolate; Antigravity PASS |
| Status | Planned (validated locally; not integrated) |
| Rollback | remove new dashboard and restore report |
