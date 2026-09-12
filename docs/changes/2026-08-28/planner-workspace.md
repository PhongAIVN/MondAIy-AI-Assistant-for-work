# AI Planning Workspace

## Objective

Add a user-controlled day/week planning workspace that turns open tasks into
time-block proposals while protecting lunch and Happy Time.

## Scope

- Backend preferences, plan generation API and Alembic migration.
- Deterministic scheduler support for protected time windows.
- Planning page and sidebar route in the web client.
- Chat tools to generate a day/week plan and update the internal Workday
  Contract from explicit HH:MM values.
- Product feature specification and focused scheduler regression test.
- Calendar-aware proposal update: cached personal Calendar events and published
  cohort program events are immutable busy windows; Planner still never writes
  an external calendar.
- Planner hierarchy update: one primary NOW task, up to three NEXT tasks, and
  calendar/risk/chat as secondary CONTEXT rather than competing widgets.

## Decisions and boundaries

- The LLM-backed task breakdown remains responsible for analysing detailed task
  instructions; time allocation remains deterministic (deadline/WSJF/estimate/
  energy) and explainable.
- `POST /api/v1/planner/generate` creates a proposal only. It does not write an
  external calendar, send a message or mutate a task.
- Existing `stakeholders` and `deliver_to` data is surfaced as a communication
  commitment; no recipient is inferred.
- Chat can run planner generation and save explicit internal workday settings;
  external Calendar writes remain confirmation-gated.

## Verification

- `python -m compileall -q src/api/planner.py src/models/planner_preference.py src/services/planner/workspace.py src/services/planner/schedule.py` — pass.
- Focused direct smoke for protected Happy Time and invalid workday ordering — pass.
- `npx tsc --noEmit --pretty false` in `client/web-app` — pass.
- `npm run lint` in `client/web-app` — pass with pre-existing warnings outside Planner.
- Focused pytest invocation was attempted but did not return before the execution environment's 30-second command limit; the equivalent focused smoke was run directly above.
- `planner busy-calendar smoke` (09:00--11:00 shared meeting) placed the task
  at 11:00 -- pass; `ruff check` on Planner backend/test files -- pass.
- `npm run build` and `npm run lint` in `client/web-app` -- pass. Lint retains
  pre-existing warnings outside Planner; build reports the existing large chunk
  advisory only.

## Migration and rollback

Apply Alembic revision `b9d1e4f2a6c8`. Rollback drops only
`planner_preferences`; it does not touch tasks or external calendars.
