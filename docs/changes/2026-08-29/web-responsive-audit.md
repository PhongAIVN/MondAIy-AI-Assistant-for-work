# Web responsive audit

## Objective

Harden the authenticated web shell and task/planner surfaces for narrow phones,
large text settings and intentionally wide calendar views.

## Changes

- The application shell now clips accidental horizontal overflow at the content
  boundary while preserving local scrolling for wide calendar timelines.
- Tasks statistics use shrinkable cells, compact mobile padding and wrapping
  labels instead of forcing translated labels outside the viewport.
- Planner refresh/reschedule cards wrap long task titles and reasons without
  breaking the time label.
- Mobile controls remove the tap highlight and keep common controls at a
  touchable minimum height.

## Verification

- `npm run lint`: no errors; only existing warnings in unrelated files.
- `npm run build`: TypeScript and the application Vite bundle completed; the
  command window ended during the existing service-worker build stage, so the
  final command was not recorded as a complete pass.
- `git diff --check`: pass.

## Risk and rollback

No API, data or migration changes. Revert the responsive-audit commit if a
device-specific layout regression is found. Wide calendar content remains
locally scrollable rather than hidden.
