# Mobile home overlay and automated briefing configuration

## Objective

Keep the existing mobile user home screen intact, overlay the calendar/todo glance on demand, and expose automated briefing scheduling from the user/profile area.

## Research sources

- `apps/mobile/src/components/RealWorkspace.tsx` — current home/profile shell and API wiring.
- `src/api/routines.py` and `src/services/routines.py` — authenticated routine CRUD and worker schedule matching.
- `src/models/routine.py` and `src/models/schemas.py` — routine frequency contract.
- `src/api/connections.py` and `src/services/telegram_channel.py` — Telegram connection/delivery boundaries.
- Base commit: `0d25411fd222a3da6f7dd7a21a567e4f3407cf69`.

## Scope

- Restored the existing Home route; the calendar/todo dashboard is now a modal overlay opened from a floating `Lịch & todo` action.
- Added a profile action that opens a briefing configuration sheet.
- Mobile configuration loads the user's first routine and can create/update a real backend routine with daily, every-other-day, or weekly frequency, local timezone, and hour selection.
- Added backend support for `every_other_day`, anchored to the routine creation date.
- Kept Telegram channel ownership/delivery separate; this change does not falsely claim that routine output is delivered to Telegram until that backend delivery path is explicitly connected.

## Verification

- `apps/mobile/.\node_modules\.bin\tsc.cmd --noEmit` — passed.
- `node --experimental-strip-types --test tests/**/*.test.ts` — passed, 10 tests.
- `python -m py_compile src/models/routine.py src/models/schemas.py src/services/routines.py tests/test_services/test_routines.py` — passed.
- `git diff --check` — passed.
- `python -m pytest tests/test_services/test_routines.py -q` — skipped/blocked because the environment lacks `slowapi`, imported by `tests/conftest.py`.

## Risk and follow-up

- Routine execution currently stores output in Mondaiy; Telegram delivery for routine output still requires a separate backend integration with the existing Telegram delivery service.
- Physical-device QA is recommended for modal height, keyboard overlap, and Vietnamese text wrapping.
- No deploy or production runtime change was made.
