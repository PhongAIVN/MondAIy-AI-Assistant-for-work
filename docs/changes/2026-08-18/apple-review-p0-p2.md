# Apple review P0/P1/P2 remediation

## Objective

Close the mobile App Review blockers and high-risk review findings without
claiming approval or changing production state.

## Scope

- Added Sign in with Apple authorization-code exchange and encrypted refresh
  token storage so account deletion can revoke Apple access first.
- Added account-deletion regression coverage and wired the mobile Apple
  credential through to the backend.
- Added clickable privacy/help links and an explicit AI-provider disclosure for
  OpenRouter, Groq and OpenAI.
- Tightened iOS ATS, localized speech/microphone/photo permission strings,
  added the iOS build number, and enabled EAS production build-number
  auto-increment.
- Kept briefing copy aligned with the actual in-app notification feed rather
  than claiming native push delivery.

## Verification

- `apps/mobile`: `npm.cmd test` — 19/19 passed.
- `apps/mobile`: `npm.cmd run typecheck` — passed.
- `apps/mobile`: `npx.cmd expo-doctor` — 21/21 passed.
- iOS Expo export — passed; Metro bundled 1,397 modules.
- `python -m compileall -q src` — passed.
- JSON parse of `app.json` and `eas.json` — passed.
- `git diff --check` — passed.

## Known limitations / external release gates

- Backend pytest could not start in this workspace because the environment is
  missing the existing `slowapi` dependency; no backend test result is claimed.
- Apple Developer configuration must set `APPLE_TEAM_ID`, `APPLE_KEY_ID` and
  `APPLE_PRIVATE_KEY` in the authoritative VM environment, with the matching
  Sign in with Apple capability for `com.mondaiy.product`.
- App Store Connect still requires final privacy labels, privacy/support URLs,
  reviewer notes, demo-account policy, export-compliance answers, and a real
  TestFlight device review. These cannot be verified from source alone.
- Widget refresh uses iOS background scheduling and is best effort; the app
  must not promise an exact one-hour refresh to reviewers.

## Deployment

EAS project `@dung_parkwave/mondaiy-mobile` was created and linked with
project ID `f1b600bb-a141-486b-9b9f-5bbf0448637d`. A production iOS build was
requested, but EAS stopped before queueing because the remote Distribution
Certificate for `com.mondaiy.product` was not validated for non-interactive
builds; the widget target also requires its own provisioning profile. No
TestFlight upload or App Store Connect submission was performed.

## VM rollout update

- VM: `14.225.168.28`, `/opt/p-004`.
- Source commit deployed: `0b57c0c`.
- Apple Team ID, Key ID and PEM-normalized private key were written directly
  to the VM `.env`; no secret was added to git or copied back to the repo.
- Only `p004-backend` and `worker` were rebuilt/recreated. The previous image
  was retained under rollback tag `rollback-0b57c0c`.
- Both services are running; backend health is healthy and the public health
  endpoint returned `{"status":"ok","env":"production"}`.
- In-container `_client_secret()` smoke check passed.
- TestFlight/App Store Connect submission remains separate from VM deploy.
