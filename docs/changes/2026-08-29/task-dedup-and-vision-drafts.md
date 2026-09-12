# Task deduplication and screenshot drafts

## Objective

Prevent a user-confirmed suggestion from creating a duplicate active task, and
keep screenshot/OCR extraction on the review-first path.

## Scope and behaviour

- `POST /tasks/from-suggestion` now uses the existing exact, fuzzy and semantic
  task-dedup service under the per-user transaction lock.
- A matching active task with the same/similar title and nearby deadline is
  returned instead of inserting a second row. The incoming source is attached
  as task evidence and an audit event records the merge without storing source
  content in telemetry.
- The API response explicitly marks a merge; the chat card says that it merged
  rather than incorrectly saying a new task was created.
- OCR/screenshot suggestions carry an assignee only when the image states one.
  The Vision endpoint still returns only draft suggestions. It never persists a
  task before the user presses the confirmation control.

## Files

- `src/api/tasks.py`, `src/services/task_dedup.py` integration point
- `src/api/vision.py`, `src/agents/tools/task_tool.py`, schemas and web types
- regression tests in `tests/test_api/v1/test_tasks.py` and
  `tests/test_api/test_vision.py`

## Verification

- `python -m compileall -q src`: pass.
- `ruff check src/api/tasks.py src/api/vision.py src/agents/tools/task_tool.py
  tests/test_api/v1/test_tasks.py tests/test_api/test_vision.py`: pass.
- Target pytest collection: 13 tests collected.
- Target pytest execution did not finish within the 30-second execution window
  in this environment; it produced only the existing pytest-asyncio
  configuration deprecation warning. It is not recorded as a test pass.
- `npm run lint` and `npm run build` in `client/web-app`: pass; pre-existing
  lint warnings and the existing bundle-size advisory remain.

## Risk and rollback

The matching window only applies where the existing dedup service has a clear
deadline, avoiding merges of unrelated tasks without a time anchor. Roll back
by reverting the feature commit; no migration or configuration change is
required.
