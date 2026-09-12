# Enable Slack connector in /sources UI

## Objective

Show Slack as a connectable source on `/sources`, per PM decision (see
`docs/projects/engineering/adr/adr-016-slack-connector-pilot-scope.md`).

## Research

- `client/web-app/src/types/pipeline.ts`: `ENABLED_PROVIDERS` gate hid `slack`
  pending ADR/PM decision on the 5 open questions in `slack-detail.drawio`.
- `client/web-app/src/pages/SourceLibraryPage.tsx`: `INTEGRATION_CATALOG` had
  no Slack entry for the same reason.
- `src/api/connections.py`: backend `_PROVIDERS` already included `"slack"`.
- `src/connectors/slack.py`: `list_sources()` already lists channels, DMs,
  and group DMs as individually selectable `Source` items — matches the
  "user selects channel" decision without code changes.
- `src/config.py`: `slack_client_id`/`slack_client_secret` are empty — no
  real Slack App registered yet.

## Scope

- Added `'slack'` to `ENABLED_PROVIDERS` in
  [pipeline.ts](../../../client/web-app/src/types/pipeline.ts).
- Added a Slack entry to `INTEGRATION_CATALOG` in
  [SourceLibraryPage.tsx](../../../client/web-app/src/pages/SourceLibraryPage.tsx).
- Wrote ADR-016 recording the PM's answers to 3 of 5 open questions from
  `slack-detail.drawio` (channel scope, DM privacy, app distribution scope).
- Did not touch `src/services/slack_rules.py`, `src/connectors/slack.py`, or
  any backend Slack code — connector behavior already matched the decisions.

## Verification

- `npx tsc -b --noEmit` in `client/web-app`: passed, no errors.
- Browser check at `http://localhost:5173/sources`: blocked by login (no
  test credentials available this session) — could not visually confirm the
  Slack card renders. Typecheck is the only verification for the UI change.
- `.venv\Scripts\python.exe -m pytest tests/test_connectors/v1/test_slack_normalize.py tests/test_services/v1/test_slack_rules.py -q`:
  39 passed, 3 pre-existing failures in `TestScoreMessage`/`TestExtractTitle`/
  `TestEvaluateMessageIntegration` — in `slack_rules.py` scoring logic, a file
  this change did not touch. Failures predate this change (part of WIP stash
  restored before this session). Not fixed — out of scope for a UI-gate change.

## Risk and follow-up

- Connect Slack button will render but OAuth will fail until a real Slack
  App is registered and `SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET` are set.
- ADR-016 question #2 (deadline-confidence display) remains open — resolve
  before showing extracted Slack tasks to real users.
- The 3 pre-existing `slack_rules.py` test failures should be fixed before
  the connector ships end-to-end (separate task).
