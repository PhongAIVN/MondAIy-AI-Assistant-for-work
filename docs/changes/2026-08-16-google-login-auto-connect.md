# WHAT_CHANGED — Tái sử dụng phiên Google khi kết nối

| Field | Value |
| --- | --- |
| Task ID | `google-login-auto-connect` |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | Codex |
| Agents / lanes | `Zeno: frontend OAuth/session research`; `Archimedes: backend connector auth research`; `Planck: test and verification research`; `Codex: implementation/integration` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `not committed; integrated in working tree` |
| PR / issue / ADR | `not linked` |

## Intent and acceptance criteria

- Intent: Khi người dùng vừa đăng nhập bằng Google, bước kết nối Google không bắt họ đăng nhập lại nếu phiên Google còn hợp lệ.
- Observable acceptance criteria:
  - Nút `Continue with Google` hoàn tất một OAuth flow để tạo app session và Google connection cho cùng một user.
  - Callback đổi login code ngắn hạn thành `nav_session`, rồi điều hướng vào briefing/onboarding thay vì bắt đăng nhập lại.
  - Google consent vẫn do Google hiển thị; không đưa access/refresh token vào URL redirect.
  - Redirect ngoài allowlist, state sai và login code sai bị từ chối; luồng connect Google cũ vẫn hoạt động.
  - Regression tests kiểm tra session persistence, auto-connect, redirect allowlist và đường từ chối.
- Non-goals: không đổi provider/scope OAuth, không tự cấp consent, không đổi schema hoặc deployment.

## Changes

- Observable behavior: `Continue with Google` vừa đăng nhập mondaiy vừa lưu connection Google; reconnect giữ refresh token cũ nếu Google không cấp token mới.
- Components/files: `client/web-app/src/components/auth/GoogleAuthButton.tsx`, `client/web-app/src/pages/auth/GoogleCallbackPage.tsx`, auth store/API/routes; `src/api/connections.py`, `src/services/connections/google.py`, OAuth state, User schema/migration; regression tests.
- Config/migration/API compatibility: thêm `/api/v1/auth/google/login`, `/api/v1/auth/google/session`, `flow=login` trong OAuth state; migration PostgreSQL cho phép `users.password_hash` NULL để tài khoản Google-only không cần mật khẩu. Manual connector endpoints giữ tương thích.

## Agent handoffs and integration

- Ownership boundaries: Zeno/Archimedes/Planck read-only research; Codex owns implementation, tests, change record and final integration in the current checkout.
- Integration order/conflicts: restored the historical Google-login scaffold from `38eb01a` as reference, then adapted the callback to upsert the Google connection; no merge or branch rewrite performed.
- Independent review: three research handoffs confirmed the missing Google-login flow, Bearer/state boundary and test gaps. Existing dirty files were preserved.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `git status --short --branch` | `inspected; pre-existing user changes preserved` | `2026-08-16` |
| `DATABASE_URL=sqlite:////private/tmp/p004-google-login-test.sqlite3 APP_ENV=test pytest -q tests/test_api/v1/test_google_login.py` | `7 passed` | `2026-08-16` |
| `DATABASE_URL=sqlite:////private/tmp/p004-google-login-test.sqlite3 APP_ENV=test pytest -q` | `1031 passed, 6 skipped, 1 unrelated failure in test_reminders.py caused by SQLite naive datetime` | `2026-08-16` |
| `npm test` (client/web-app) | `45 Vitest files / 199 tests passed; Node tests 101 passed` | `2026-08-16` |
| `ruff check src/ tests/` | `pass` | `2026-08-16` |
| `npm run lint` (client/web-app) | `pass with 5 pre-existing warnings` | `2026-08-16` |
| `python3 -m compileall -q <changed Python files>` | `pass` | `2026-08-16` |
| `git diff --check` | `pass` | `2026-08-16` |
| `npm run build` (client/web-app) | `not pass: 3 pre-existing TS2835 errors in meetingDisplay.ts/meetingNotesApi.ts for missing .js extensions` | `2026-08-16` |
| `mypy <changed Python files>` | `not run: mypy command unavailable in environment` | `2026-08-16` |
| `pytest -q ...` with default PostgreSQL test config | `not pass: 21 setup errors; localhost:5433 blocked/unavailable (`Operation not permitted`)` | `2026-08-16` |

Tests not run and reason: full PostgreSQL-backed verification could not run because the local PostgreSQL endpoint is unavailable in the sandbox; SQLite regression was run instead.

## Risk, rollback and follow-up

- Risks: first-time Google sign-in now requests the configured Gmail/Calendar scopes in the same consent; production Google OAuth client must include the callback URI and the frontend origin must be in CORS/`WEB_APP_PUBLIC_URL` allowlists.
- Rollback: revert the task files and disable the Google login button/routes; PostgreSQL migration is additive and can remain with nullable `password_hash`.
- Follow-up: run the OAuth smoke test against a configured Google client and PostgreSQL before merge; resolve the unrelated frontend build imports and SQLite reminder timezone failure separately.

## Merge and deployment

- Merge status: local working tree only; not merged or deployed.
- Environment / deployed SHA or artifact: not applicable.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: base SHA recorded above.
