# WHAT_CHANGED — Program context and cohort schedules

| Field | Value |
| --- | --- |
| Task ID | program-context-cohort-schedule |
| Status | In progress |
| Date | 2026-08-16 |
| Lead | Codex |
| Agents / lanes | backend: cohort schedule/context API; frontend: admin/user UI; review: access and calendar-sync safety |
| Base SHA | e8e56c5a6d93dfa87c2d7ca025a98fdfaab49c41 |
| Head / merge SHA | not merged |
| PR / issue / ADR | pending product/architecture decision if notification or Google write behavior changes |

## Intent and acceptance criteria

- Intent: let admins publish program context and recurring cohort schedules, and let eligible type-A users receive the schedule for their cohort without cross-cohort leakage.
- Observable acceptance criteria:
  - Admin can create/edit/publish program context and cohort schedule rules.
  - 3A and 3B schedules remain isolated and render with Vietnam timezone.
  - User type A receives only the server-authorized cohort schedule.
  - Draft/team-scoped/unpublished records are not exposed.
  - Google Calendar writes remain explicit unless an existing approved contract already authorizes them.
- Non-goals: changing access-level classification, broad notification fanout, or silently writing to Google Calendar without an explicit user grant.

## Changes

- Observable behavior: pending implementation.
- Components/files: pending lane handoffs.
- Config/migration/API compatibility: pending review.

## Agent handoffs and integration

- Ownership boundaries: backend and frontend lanes are isolated; lead integrates shared contracts first.
- Integration order/conflicts: backend contract, frontend client/UI, tests/review.
- Independent review: pending.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| not run | implementation in progress | 2026-08-16 |

Tests not run and reason: implementation has not been integrated.

## Risk, rollback and follow-up

- Risks: cohort membership is currently derived from server configuration and Discord identity; multi-cohort membership requires a durable membership contract. Automatic Google Calendar writes require explicit consent and valid write scope.
- Rollback: revert the integrated feature commit to base SHA e8e56c5.
- Follow-up: structured schedule provenance and visible source citations in chat.

## Merge and deployment

- Merge status: not merged.
- Environment / deployed SHA or artifact: not deployed.
- Health/log evidence: not run.
- Previous known-good / rollback verification: e8e56c5.
