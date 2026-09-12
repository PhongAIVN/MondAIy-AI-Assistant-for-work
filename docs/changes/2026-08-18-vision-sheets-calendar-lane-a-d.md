# WHAT_CHANGED — Vision image port (Lane A) + Sheets matching fix (Lane D)

| Field | Value |
| --- | --- |
| Task ID | Lane A (vision-image-port) + Lane D (sheets-matching-fix) |
| Status | Integrated onto `integrate/vision-sheets-calendar`, not merged into `feat/ui-revamp-va-agent-openrouter`, not pushed |
| Date | 2026-08-18 |
| Lead | orchestrator (lead session) |
| Agents / lanes | Lane A worker — ported `POST /vision/actions` OCR-paste feature from branch `sync/main-8403c7a` (not previously on `main` or the working branch). Lane D worker — fixed `_name_matches`/`_parse_due` in the Google Sheets connector. |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` for both lanes as originally briefed |
| Integration base | `b74fd67` — checkpoint commit of 96 previously-uncommitted WIP files in the main checkout (see below) |

## Why this record differs from each lane's own report

Both lanes were briefed against base `cec16e4`, but the main checkout actually
had 96 uncommitted files at task time — including the *entire* Google Sheets
feature (`src/connectors/google_sheets.py`, `src/api/google_sheets.py`,
`src/models/schemas.py` GoogleSheets* classes, and 3 frontend files) as
untracked WIP, plus edits to `DailyBriefingPage.tsx`. Neither lane's isolated
`git worktree add` (built from committed refs only) could see that WIP.

- **Lane D** could not find `google_sheets.py` at the given base, correctly
  identified it existed on the unrelated `sync/main-8403c7a` branch, and
  applied its fix to a fresh copy sourced from there — a parallel file, not
  the user's real WIP.
- **Lane A** ported the vision feature fine (it doesn't depend on
  `google_sheets.py`), but its `DailyBriefingPage.tsx` changes were based on
  the pre-WIP version of that file.

Resolution performed by lead:
1. Committed the 96 WIP files as-is to `feat/ui-revamp-va-agent-openrouter`
   (commit `b74fd67`) — user confirmed this explicitly.
2. Created `integrate/vision-sheets-calendar` from `b74fd67`.
3. Cherry-picked Lane A's 2 commits onto it — one trivial import-order
   conflict in `DailyBriefingPage.tsx` (both sides only added new import
   lines), resolved by keeping both blocks.
4. Re-applied Lane D's `_name_matches`/`_parse_due` fix directly onto the
   real (now-committed) `src/connectors/google_sheets.py`/`schemas.py`/test
   file, discarding Lane D's parallel copy of the connector itself. Diffed
   Lane D's reconstructed file against the real WIP file first to confirm
   they were otherwise identical (only the intended fix differed), so no
   other Sheets logic was lost or duplicated.

## Observable behavior change

- Backend: `POST /api/v1/vision/actions` now exists (OpenAI vision OCR on
  pasted/dropped images, returns text response; does not yet create
  tasks/calendar events — see review notes for lane B follow-up).
- Frontend: paste/drop an image into the daily-briefing chat box now sends it
  for OCR and shows the model's text reply inline.
- `GoogleSheetsConnector._name_matches` no longer substring-matches assignee
  names (was: "An" matched "Nguyễn Văn Anh"); now requires exact match or
  ≥2 overlapping name tokens.
- `GoogleSheetsConnector._parse_due` flags proposals as `needs_confirmation`
  when the due-date cell has no explicit year, with a clarification message
  instead of silently trusting `dateutil`'s inferred year.
- New response field `GoogleSheetsTaskProposal.date_ambiguous: bool`.

## Files touched (beyond each lane's own file list)

- `client/web-app/src/pages/DailyBriefingPage.tsx` — merge-resolved import
  block only.
- `src/connectors/google_sheets.py`, `src/models/schemas.py`,
  `tests/test_connectors/test_google_sheets.py` — Lane D's fix re-applied on
  the real file instead of Lane D's reconstructed copy.

## Tests run (real commands + output)

- `pytest tests/test_connectors/test_google_sheets.py tests/test_api/test_vision.py tests/test_services/test_vision.py -q`
  → **18 passed** (run from `/tmp/p004-integrate` worktree with the main
  checkout's `.venv` and a copy of the gitignored `.env`, since a fresh
  worktree has neither).
- Full suite (`pytest -q`) — running in background at time of writing; result
  to be appended once complete.
- Each lane's own targeted/full-suite results are recorded in their own
  worker output (Lane A: 1036 passed/2 skipped/1 pre-existing unrelated
  fail; Lane D: 10/10 own tests, 38/38 connector+config tests, full suite
  pre-existing failures unrelated to these files).

## Known follow-ups (not done here)

- `/vision/actions` still does not create tasks or calendar events from OCR
  output — this was flagged in the original review as the priority fix
  (Lane B, not yet started).
- `src/services/vision.py` calls OpenAI directly instead of via OpenRouter —
  pre-existing deviation carried over as-is per Lane A's port-only scope.
- Frontend `DailyBriefingPage.tsx` image branch does not yet surface
  task/calendar suggestions in the UI (also Lane B/C scope).

## Rollback

`git reset --hard b74fd67^` on `feat/ui-revamp-va-agent-openrouter` restores
the exact WIP checkpoint before this integration if needed (nothing here has
been merged into that branch yet — this record documents the
`integrate/vision-sheets-calendar` branch only).
