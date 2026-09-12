# WHAT_CHANGED — Admin Discord announcement ingest

## Objective and acceptance

Implement the vertical slice **Admin paste Discord announcement → structured
preview → Admin confirm/publish**. Confirmation must retain raw text/evidence
and create canonical Mức A program information. Only user Type A may claim an
action as a personal proposed Task; the user still confirms that Task before
using the existing Calendar handoff. Ambiguous times remain empty and flagged;
explicit or evidence-backed relative times resolve in `Asia/Ho_Chi_Minh`.
Preview, publish and task-claim retries are idempotent; no Google Calendar write
occurs in this flow.

## Research and decisions

- Sources: `AGENTS.md`; PRD FR-040..045 and FR-060..068; ADR-009, ADR-010 and
  ADR-015; current program information, program calendar, task and Discord
  announcement code.
- Cohort comes only from server configuration. Discord paste is an official
  Mức A source but remains evidence, not an authority inferred from client data.
- The feature creates internal drafts only; Calendar sync stays an explicit
  learner-owned action.

## Ownership and baseline

| Item | Value |
| --- | --- |
| Date / batch | 2026-08-24 / admin-discord-announcement-ingest |
| Base SHA | `401827a42c20f81150fa28bebaa1dd0cf65cf128` |
| Branch | `feat/admin-discord-announcement-ingest` |
| Production writer | Codex lead — backend, migration, web admin, integration |
| Independent reviewer | Pending/unavailable; Antigravity has not run this task |
| External effect | None; no provider credential or Calendar write |

## Verification plan

- API: admin allowed/denied, ambiguity, idempotent confirm, retained raw
  evidence, cohort scope and no external calendar side effect.
- Web: paste → preview → confirm interaction; then `test`, `lint`, `build`.
- Final SHA, actual commands/results, risks and rollback are recorded below
  after validation.

## Implementation and validation

Feature SHA: `3e37063`. Implemented locally: one paste retains raw evidence and
holds multiple parsed action items. Admin confirmation publishes canonical
information once; only a Type A learner can claim an action as one personal
proposed Task with `TaskEvidence`. Office Hours with two speakers produces two
calendar-shaped actions; deadline, reschedule and booking cases preserve their
different semantics. This flow never calls a Calendar connector.

Commands actually run:

- checkout-root `.venv/bin/python -m pytest -q
  tests/test_services/test_announcement_candidates.py
  tests/test_api/v1/test_announcement_candidates.py` — **6 passed**.
- checkout-root `.venv/bin/ruff check <changed Python paths>` — **passed**;
  `ruff format --check` was satisfied after formatting.
- `vitest run tests/AdminDiscordAnnouncementPage.test.tsx` — **1 passed**.
- `tsc --noEmit -p tsconfig.app.json` — **passed**.
- targeted `oxlint` — **0 errors**, one existing Fast Refresh warning for
  `Sidebar.tsx` exporting `SIDEBAR_WIDTH` with the component.
- `npm run build` — **passed**; existing chunk-size and PWA deprecation warnings
  remain.
- `git diff --check` — **passed**.

Proof level / claim ceiling: API integration + frontend component interaction
+ production build. The feature is locally implemented and tested; it is not
independently reviewed, merged, pushed or deployed.

Tests not run: full repository regression and authenticated browser E2E, to
keep the deadline-bound pass targeted. Independent review remains unavailable:
Antigravity was not authorized to receive P-004 source for this task.

Independent review remains pending/unavailable; Antigravity has not run this
task.

## Deployment notification

| Item | Value |
| --- | --- |
| Batch / date | admin-discord-announcement-ingest / 2026-08-24 |
| User-visible update | Admin can paste/review/publish; learner can add a cohort candidate as draft task |
| Scope | backend, web admin, learner web |
| Source | Feature SHA `3e37063` |
| Validation | 6 backend tests + 1 frontend interaction test + Ruff + TypeScript + oxlint + production build |
| Status | Planned — local branch only, not merged/deployed |
| Rollback | Reset to base SHA `401827a42c20f81150fa28bebaa1dd0cf65cf128` |
