# WHAT_CHANGED — Sửa contract đăng ký PWA Web Push

| Field | Value |
| --- | --- |
| Task ID | `pwa-push-subscription-contract-20260816` |
| Status | In progress — VM test blocked by deploy gates |
| Date | `2026-08-16` |
| Lead | Codex |
| Agents / lanes | `controller: client Web Push contract + regression test + verification` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `not committed` |
| PR / issue / ADR | User-requested bug fix; no new product scope |

## Intent and acceptance criteria

- Intent: làm cho payload đăng ký subscription của PWA khớp schema API hiện tại.
- Observable acceptance criteria: bật Web Push gửi `keys.p256dh` và `keys.auth` đúng cấu trúc; regression test khóa contract; backend và frontend targeted tests pass.
- Non-goals: không đổi VAPID, worker delivery, notification UX hoặc các thay đổi sẵn có trong worktree.

## Changes

- Observable behavior: client không còn gửi payload phẳng gây HTTP 422 khi đăng ký.
- Components/files: `client/web-app/src/lib/pushApi.ts`, `client/web-app/tests/PushApi.test.tsx`.
- Config/migration/API compatibility: khớp schema `PushSubscribeRequest` hiện có; không migration/config.

## Agent handoffs and integration

- Ownership boundaries: chỉ hai file Web Push client/test thuộc task; không chạm file đang có thay đổi khác.
- Integration order/conflicts: contract backend đã tồn tại; sửa client và test phụ thuộc.
- Independent review: chưa có lane phụ; diff được controller review.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `npm test -- --run tests/PushApi.test.tsx tests/PushToggle.test.tsx tests/PushNotification.test.ts` | pass: 103 Node tests, 17 targeted Vitest tests | `2026-08-16` |
| `npm run lint -- src/lib/pushApi.ts tests/PushApi.test.tsx` | pass | `2026-08-16` |
| `git diff --check` | pass | `2026-08-16` |
| `DATABASE_URL=sqlite:///./data/push-check.db pytest -q tests/test_api/test_push.py tests/test_services/test_web_push.py tests/test_worker.py` | pass: 25 | `2026-08-16` |
| `npm run build` | blocked by pre-existing unrelated missing `.js` extensions in meeting notes imports | `2026-08-16` |
| `bash ../Guidebook-Agent-Deploy/scripts/deploy_vm_local.sh --dry-run` | blocked by canonical gate: current branch is not `main` | `2026-08-16` |
| `curl -fsS https://p004-api.duckdns.org/health` | pass: HTTP 200, production health OK | `2026-08-16` |
| `curl -fsS https://p004-api.duckdns.org/api/v1/push/public-key` | pass: HTTP 200, Web Push enabled on current VM | `2026-08-16` |

Tests not run and reason: the fixed commit was not deployed, so authenticated browser-to-VM push smoke test was not run. The canonical Guidebook deploy script requires clean `main`; current checkout is a dirty feature branch with unrelated user changes. No production `.env` or SSH credential was read.

## Risk, rollback and follow-up

- Risks: browser subscription created before a failed API call can remain locally; retrying the toggle reuses/updates the endpoint and fixes server ownership.
- Rollback: revert the two scoped file changes before integration.
- Follow-up: integrate on reviewed clean `main`, run Guidebook VM dry-run/deploy path, then perform public health and authenticated Web Push smoke test. Revisit FR-097 handling for notification kinds without deep links.

## Merge and deployment

- Merge status: not merged.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: current VM read-only checks passed (`/health` 200; `/api/v1/push/public-key` 200 and `enabled=true`), but they describe the pre-fix deployment.
- Previous known-good / rollback verification: not applicable; no deployment occurred.
