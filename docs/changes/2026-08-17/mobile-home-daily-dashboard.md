# Mobile home daily dashboard

## Objective

Expose a compact daily dashboard on the mobile home screen, inspired by the supplied reference: current date/time, week calendar overview, today's events, product-generated todo items, and reminders.

## Research sources

- `apps/mobile/src/components/RealWorkspace.tsx` — existing task/calendar APIs and home navigation.
- `apps/mobile/src/api/client.ts` — authenticated task and calendar contracts.
- `docs/projects/design/wireframe-ui-flow.md` — mobile information architecture.
- Base commit: `0d25411fd222a3da6f7dd7a21a567e4f3407cf69`.

## Scope

- Home now renders a daily-glance dashboard rather than choosing between separate task/calendar lists.
- Calendar data is loaded for the current local week using the existing `/api/v1/calendar/events` route.
- Product-generated tasks are shown inline and proposed tasks can be confirmed from the dashboard.
- Existing dedicated task and calendar views remain available through the current navigation.
- Uses device-local date/time formatting and preserves existing loading/error/empty components.

## Verification

- `apps/mobile/.\node_modules\.bin\tsc.cmd --noEmit` — passed.
- `node --experimental-strip-types --test tests/**/*.test.ts` — passed, 10 tests.
- `git diff --check` — passed.

## Risk and follow-up

- The dashboard is a summary view; dense event days are capped to five items and the dedicated calendar view remains the detailed fallback.
- Physical-device visual QA is recommended for narrow screens and long Vietnamese event titles.
- No backend schema, endpoint, or deploy change was made.
