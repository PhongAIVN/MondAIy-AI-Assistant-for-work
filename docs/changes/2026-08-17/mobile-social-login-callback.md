# Mobile social-login callback fix

## Objective

Make native Google and Apple sign-in usable in the mobile client and align the
native Google callback with the production VM configuration.

## Research

- `apps/mobile/src/components/MobileProduct.tsx`: native Google and Apple flows.
- `src/api/auth.py`, `src/api/connections.py`: backend token exchange and OAuth redirect validation.
- `src/services/apple_auth.py`: Apple identity-token verification.
- Production VM `/opt/p-004/.env`: Google/Apple credentials and native callback are configured.
- Production health check: `https://p004-api.duckdns.org/health` returned `status=ok`.

## Scope

- Use `mondaiy://auth/callback` consistently in mobile and backend defaults.
- Allow an optional `EXPO_PUBLIC_GOOGLE_CALLBACK_URI` override for native builds.
- Preserve backend-owned Google OAuth and Apple identity-token exchange.
- Do not copy or change production `.env`; Gmail OAuth remains a separate connector flow.

## Verification

- `npm.cmd test` in `apps/mobile`: passed, 10 tests.
- `npm.cmd run typecheck` in `apps/mobile`: passed.
- `.venv\Scripts\python.exe -m pytest tests/test_api/v1/test_google_login.py tests/test_api/v1/test_apple_login.py -q`: passed, 10 tests.
- `git diff --check`: passed.

## Deployment

Pending commit/push and VM rollout. Production rollback is the previous backend
image tag created by `scripts/deploy_vm_local.sh`.

## Risk and follow-up

The mobile app must be rebuilt/reinstalled after this callback change. The
Supabase migration is not part of this focused social-login fix.
