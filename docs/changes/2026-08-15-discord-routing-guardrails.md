# WHAT_CHANGED — Discord routing và callback feedback

| Field | Value |
| --- | --- |
| Task | Complete three interrupted Discord fixes |
| Status | Implemented locally; awaiting review/merge |
| Base SHA | `a19a9dd` |
| Head SHA | uncommitted |

## Observable behavior

- OAuth callback toast keeps the backend's safe `message` query value instead of replacing it with generic text.
- Callback redirect query values are URL encoded.
- Questions about received announcements or Gmail are no longer mistaken for the user's authored Discord messages.
- `discord_list_announcements` is classified as read-only, so the guardrail allows it during read phase.

## Verification

- `APP_SECRET_KEY=test-secret DATABASE_URL=sqlite:////tmp/p004-discord-fixes-2.db APP_ENV=test pytest -q tests/v1/test_guardrail.py tests/v1/test_intent_router.py tests/test_api/test_connections_redirect.py` — 48 passed.
- `npx vitest run tests/connectionCallbackMessage.test.tsx` — 2 passed.
- `ruff check ...`, `python3 -m compileall -q src tests`, `git diff --check` — passed.
- `npm run lint` — passed with seven pre-existing project warnings; this change adds none.
- `npm run build` — passed.

## Risk and rollback

- The backend message comes from the server callback; no provider error payload is forwarded directly.
- Revert this change record's source commit to restore prior routing and generic toast behavior.
- No migration, push, or deploy was performed.
