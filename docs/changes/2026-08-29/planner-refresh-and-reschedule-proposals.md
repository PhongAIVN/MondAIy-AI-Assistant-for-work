# Planner refresh and reschedule proposals

## Objective

Make the Planning Workspace respond safely to newly discovered work, especially
work due today, while using the task brief and the user's observed work history
to produce a more useful plan.

## Behaviour

- The deterministic planner remains the decision-maker required by ADR-018:
  no LLM chooses time slots or fabricates duration; no refresh writes to Google
  Calendar, a task deadline, or a task record.
- Task brief fields now survive planner normalization. The plan explanation
  explicitly says when expected output, acceptance criteria, context,
  constraints, execution method/tool or delivery commitment shaped preparation.
  Existing `actual_minutes` reference classes and reminder-dismiss behaviour
  remain inputs to duration/priority.
- The client sends its last viewed task/block snapshot when the user selects
  `Làm mới`. The API compares that snapshot with live open tasks and calendar
  availability, identifies new tasks and separately counts work due today or
  overdue, then returns only proposed moves with explicit reasons.
- The UI calls out urgent new work and every affected block. A missing target
  slot is shown as a decision required, never silently discarded.

## Verification

- `python -m compileall -q src`: pass.
- Targeted `ruff check`: pass.
- Planner request-model construction with a refresh snapshot: pass.
- `npm run build` in `client/web-app`: pass. Existing bundle-size advisory
  remains.
- Target pytest execution did not finish before this environment's 30-second
  command limit; it is not recorded as a pass.

## Safety and rollback

This is an API/UI contract expansion only; it needs no migration. Revert the
feature commit to return to stateless plan generation. Planner refresh remains
a draft, so rollback cannot leave external Calendar writes behind.
