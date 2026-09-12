# WHAT_CHANGED — Vision backend reuses shared Task suggestion pipeline (Lane B)

| Field | Value |
| --- | --- |
| Task ID | Lane B — vision-task-integration |
| Status | Committed on `agent/vision-task-integration`, not merged, not pushed |
| Date | 2026-08-18 |
| Lead | orchestrator (lead session) |
| Agent | general-purpose worker (p004-agent-dev:p004-worker's harness worktree-isolation hook failed for this session — "not in a git repository", since the primary working directory is the parent folder, not the P-004 git repo; routed to `general-purpose` with manual `git worktree add` instructions instead) |
| Base | `integrate/vision-sheets-calendar` @ `00d3649` (Lane A vision port + Lane D Sheets fix, already integrated) |
| Head SHA | see `git log -1` on `agent/vision-task-integration` after this commit |

Note: the agent's work stalled right at the final "commit" step (harness
stream watchdog, 600s no-progress). Its file edits were already staged
(`git add`) and complete; the lead reviewed the staged diff, ran tests, and
performed the commit itself rather than re-running the whole task.

## What changed

`src/api/vision.py` previously classified `/vision/actions` responses
(`task` / `calendar_event` / `mixed` / `unclear`) using a hand-rolled Vietnamese
regex heuristic (`_classify_action`) run *after* the same request already paid
for one LLM agent call that had itself reasoned about the image content — a
duplicated, less reliable inference. `task_suggestions` were also untyped
`list[dict]`, and `VisionActionResponse.calendar_suggestions` was declared but
never populated (always empty), which the original review flagged as
misleading dead API surface.

Fix, discovered by re-using an existing pattern already used by the text-chat
endpoint (`src/api/conversations.py::_task_suggestions_from_agent_result`):

1. `task_suggestions` now validates each `suggest_tasks` tool observation
   against the shared `TaskSuggestionAction` Pydantic model (moved earlier in
   `schemas.py`, no longer duplicated — it previously lived further down the
   file for the chat endpoint only). This is the exact same shape
   `POST /tasks/from-suggestion` (`TaskFromSuggestionRequest`) accepts, so a
   Lane C frontend suggestion card can call it directly with no manual field
   mapping. Also deduplicates suggestions by casefolded title.
2. `_classify_action` no longer re-derives intent from OCR text via regex. It
   classifies purely from the *already-validated* `task_suggestions`: any
   suggestion with `due_at` set → calendar signal; a mix of dated/undated →
   `mixed`; none → `unclear`. No extra LLM call added.
3. The agent prompt built in `vision_action()` now explicitly asks the agent
   to call `suggest_tasks` and to fill `due_at` per item when a clear
   date/time is present — giving the classifier a reliable structured signal
   instead of guessing from free text.
4. `VisionActionResponse.calendar_suggestions` field removed. Decision:
   option (b) from the brief — a suggestion with `due_at` still flows through
   the exact same Task → confirm → calendar-sync pipeline as a dateless task;
   splitting it into a second parallel `calendar_suggestions` list would only
   duplicate data and logic without changing observable behavior. This is
   documented directly in the `VisionActionResponse` docstring for future
   readers, referencing ADR-007 (agent proposes, user writes).
5. Anti-prompt-injection framing in `src/services/vision.py` (image content is
   untrusted, ignore in-image instructions) was **not touched** — left as-is
   per constraint.
6. `/vision/actions` still never calls `POST /tasks/from-suggestion` itself —
   confirmed unchanged; it only returns suggestions for a future frontend
   (Lane C) to render a confirm button against.

## Files touched (all within Lane B's owned scope)

- `src/api/vision.py`
- `src/models/schemas.py` (`TaskSuggestionAction` relocated above
  `VisionActionResponse`; `calendar_suggestions` removed;
  `VisionActionResponse.task_suggestions` now typed
  `list[TaskSuggestionAction]`)
- `tests/test_api/test_vision.py` (+112 lines: classify-action unit tests for
  calendar/task/mixed/unclear, task_suggestions validation/shape tests)
- `tests/test_services/test_vision.py` (minor cleanup, -7 lines)

## Tests run (real commands + output)

- `pytest tests/test_api/test_vision.py tests/test_services/test_vision.py -v`
  → **13 passed**.
- `ruff check src/api/vision.py src/models/schemas.py tests/test_api/test_vision.py tests/test_services/test_vision.py`
  → all checks passed.
- Full suite `pytest -q` → running at commit time; result appended by lead
  once complete (see follow-up note in this file or the integration summary
  reported to the user).

## Follow-ups for Lane C (frontend, next)

- `client/web-app/src/components/briefing/ChatTaskSuggestionCard.tsx` already
  exists and expects a `TaskSuggestionAction`-shaped `suggestion` prop
  (camelCase via `CamelModel`) — the vision endpoint's `taskSuggestions` can
  be rendered with that exact component, no new UI needed.
- `DailyBriefingPage.tsx`'s image branch (`handleStartBriefing`/
  `handleSendFollowUp`) currently only uses `result.response` — needs to also
  read `result.taskSuggestions`/`result.warnings`/`result.actionType` and
  render suggestion cards, matching how the text-chat `onDone` handler already
  passes `taskSuggestions` through.

## Rollback

`git branch -D agent/vision-task-integration` (never merged/pushed) fully
reverts this lane; nothing outside the worktree was touched.
