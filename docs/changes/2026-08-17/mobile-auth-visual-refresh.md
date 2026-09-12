# Mobile auth visual refresh

## Objective

Refresh the mobile login/register screen to follow the supplied reference: centered brand area, rounded lower form sheet, cream palette, and clear email/social entry points. The requested background color is `#FFFFDE`.

## Research sources

- `docs/projects/README.md` — project source map.
- `docs/projects/product/prd.md` — product/auth context.
- `docs/projects/design/wireframe-ui-flow.md` — mobile UX flow.
- `apps/mobile/src/components/MobileProduct.tsx` — existing auth state and handlers.
- Base commit: `0d25411fd222a3da6f7dd7a21a567e4f3407cf69`.

## Scope and ownership

- Lead/writer: Codex.
- Changed path: `apps/mobile/src/components/MobileProduct.tsx`.
- Preserved existing email/password, Google OAuth, Apple native identity-token exchange, guest mode, and login/register toggle behavior.
- Replaced the native Apple button presentation with a custom pressable while retaining the existing Apple authentication handler.

## Observable behavior

- Auth background uses `#FFFFDE`.
- Brand/mascot is centered above a rounded light form sheet.
- Email/password fields and social actions use the new cream/teal visual treatment.
- Register mode still adds the name field and submits through the existing `register` API.

## Verification

- `npm.cmd run typecheck` — passed.
- `npm.cmd test` — passed, 10 tests.
- `git diff --check` — passed.

## Risk and follow-up

- No API, auth contract, schema, or configuration changes.
- Visual verification on a physical iOS device is still recommended because the Apple icon/button rendering is platform-specific.
- No deploy, merge, or push performed.

## Workspace note

An unrelated pre-existing untracked directory `.p004-deploy-clone-20260817/` was observed and left untouched.
