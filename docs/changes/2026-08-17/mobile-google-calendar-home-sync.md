# Mobile Google Calendar home sync

## Objective

Show Google Calendar events on the existing mobile Home screen while keeping the full calendar and todo dashboard available as an overlay.

## Research sources

- `apps/mobile/src/components/RealWorkspace.tsx`: existing Home, Sources OAuth flow, and calendar tab.
- `apps/mobile/src/api/client.ts`: authenticated `listCalendarEvents` contract and Google connection types.
- `src/api/calendar.py`: backend calendar endpoint and Google connection requirement.
- `docs/projects/README.md` and repository `AGENTS.md`: project source-of-truth and verification contract.

## Scope and behavior

- Added a compact upcoming-events preview to the existing Home screen.
- Preview loads the next seven days through the same authenticated calendar API as the full calendar view.
- Events are sorted by start time and the next three upcoming events are shown.
- If Google Calendar is not connected, the Home card explains that the user should connect it from `Nguồn dữ liệu`.
- Existing `Lịch & todo` overlay and `Lịch 7 ngày` tab remain available.
- Extended the mobile routine frequency type with `every_other_day` to match the backend briefing configuration.

## Files

- `apps/mobile/src/components/RealWorkspace.tsx`
- `apps/mobile/src/api/client.ts`

## Verification

- `apps/mobile/.\node_modules\.bin\tsc.cmd --noEmit` — pass.
- `apps/mobile/node --experimental-strip-types --test tests/**/*.test.ts` — 10 tests pass.
- `git diff --check` — pass; only existing line-ending warnings were reported.

## Risks and limitations

- OAuth is intentionally still initiated from `Nguồn dữ liệu → Google`, using the existing backend-owned flow; this change does not duplicate credentials or create a second connection path.
- The preview depends on a signed-in user and an active Google connection. It shows an explanatory empty/error state otherwise.
- Telegram delivery for automatic briefing remains a separate integration concern and is not changed by this calendar work.

## Rollback

Remove `HomeCalendarPreview`, its styles, and the `RoutineFrequency` union addition from the two mobile files. No schema or migration is required.
