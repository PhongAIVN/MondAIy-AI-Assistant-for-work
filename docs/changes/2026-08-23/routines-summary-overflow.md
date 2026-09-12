# WHAT_CHANGED — Bound Routine recent-summary preview

| Field | Value |
| --- | --- |
| Task ID | `p004-routines-summary-overflow-20260823` |
| Record schema | `v2` |
| Status | Deployed |
| Date | `2026-08-23` |
| Lead | `Tatejo / Codex` |
| Agents / lanes | `Antigravity: independent test matrix and final review` |
| Base SHA | `c28fe6a` |
| Head / merge SHA | `2ae1914` |
| PR / issue / ADR | `not applicable` |

## Intent and acceptance criteria

- Intent: keep the Routine overview focused on routine management while preserving complete run history.
- Observable acceptance criteria: the overview has no historical summary feed; search/filter/cards and the template create flow remain available.
- Non-goals: no deletion, fake quota/upsell banner, API contract change, pagination migration, or routine-detail history change.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: an additional historical feed makes the overview noisy and violates the focused routine-management invariant.
- Root cause and shared fix boundary: `RoutinesPage` fetched and rendered recent runs alongside routine management; remove that overview feed at the presentation boundary.
- Dossier: `docs/changes/2026-08-23/routines-summary-overflow.bugfix.json`
- Sibling cases and counterexample: routine history present/absent, empty state, and routine-card actions remain unchanged.

## Changes

- Observable behavior: remove “Tóm tắt gần đây” from the overview; run history remains on routine detail.
- Components/files: `client/web-app/src/pages/RoutinesPage.tsx`, `client/web-app/tests/RoutinesPage.test.tsx`.
- Config/migration/API compatibility: unchanged.

## Agent handoffs and integration

- Ownership boundaries: Codex owns the frontend/test implementation; Antigravity is read-only reviewer.
- Integration order/conflicts: one frontend lane; no overlapping writer.
- Independent review: Antigravity APPROVED exact code change; no blocking findings. It also confirms no fake upsell banner should be added without quota/billing authority.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `python3 Guidebook-Agent-Deploy/scripts/validate_bug_fix_harness.py docs/changes/2026-08-23/routines-summary-overflow.bugfix.json` | valid: 4 cases across 2 dimensions | 2026-08-23 |
| `cd client/web-app && npm exec vitest run tests/RoutinesPage.test.tsx` | 1 file, 12 tests passed | 2026-08-23 |
| `cd client/web-app && npm run build && npm run lint` | build passed; lint passed with existing non-blocking warnings | 2026-08-23 |
| `cd client/web-app && npm exec vitest run` (Antigravity) | 85 files, 352 tests passed | 2026-08-23 |

Proof level / claim ceiling: `frontend integration` — overview behavior and full web-app regression independently verified; not deployed.

Tests not run and reason: authenticated production canary not run; merge/deploy requires explicit release approval.

## Risk, rollback and follow-up

- Risks: users may need to open routine detail to see older runs; no data is removed.
- Rollback: revert the frontend commit and redeploy the prior Vercel deployment.
- Follow-up: consider an explicit “view all” affordance if product wants archive access from the overview.

## Merge and deployment

- Merge status: merged to `main` and pushed.
- Environment / deployed SHA or artifact: Vercel production deployed from `28247fa` at `https://c3-app-004-l3890lp2c-meetmate.vercel.app`, aliased to `https://www.mondaiy.io.vn`.
- Health/log evidence: frontend canary returned HTTP 200; backend health remained `{"status":"ok","env":"production"}`.
- Previous known-good / rollback verification: Vercel deployment from `c28fe6a`.
