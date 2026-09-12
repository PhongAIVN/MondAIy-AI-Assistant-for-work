# WHAT_CHANGED — Toast báo bản cập nhật mới

| Field | Value |
| --- | --- |
| Task ID | `app-update-toast` |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | `Codex` |
| Agents / lanes | `Codex: update detection + toast + test` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `Working tree, chưa commit` |
| PR / issue / ADR | `Không có` |

## Intent and acceptance criteria

- Intent: Báo ngắn cho người đang mở app khi team phát hành bản web app mới.
- Observable acceptance criteria: Khi Service Worker mới được cài trên app đã có controller, toast cập nhật xuất hiện; lần cài đầu tiên không hiện toast.
- Non-goals: Không gửi thông báo đẩy mới, không thay đổi backend và không tự reload làm mất draft của người dùng.

## Changes

- Observable behavior: AppShell theo dõi `updatefound`/`statechange` của Service Worker và gọi toast đa ngôn ngữ yêu cầu người dùng tải lại trang.
- Components/files: `client/web-app/src/lib/appUpdateNotice.ts`, `client/web-app/src/components/pwa/AppUpdateNotice.tsx`, `client/web-app/src/components/layout/AppShell.tsx`, `client/web-app/src/i18n/translations.ts`, `client/web-app/tests/appUpdateNotice.test.ts`.
- Config/migration/API compatibility: Không thay đổi.

## Agent handoffs and integration

- Ownership boundaries: Một lane duy nhất sở hữu cơ chế phát hiện cập nhật, UI toast và regression test.
- Integration order/conflicts: Không có conflict; giữ nguyên các thay đổi sẵn có ngoài phạm vi.
- Independent review: Đã review diff và kiểm tra `git diff --check`.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `node --experimental-strip-types --test tests/appUpdateNotice.test.ts` (tại `client/web-app`) | Pass, 2/2 | `2026-08-16` |
| `npm test` (tại `client/web-app`) | Node pass 101/101; Vitest 44/45 files, 196/197 tests do test nền `SignInPage` không ổn định khi chạy song song | `2026-08-16` |
| `npx vitest run tests/SignInPage.test.tsx` (tại `client/web-app`) | Pass, 3/3; xác nhận lỗi trên là flaky ngoài phạm vi | `2026-08-16` |
| `npm run lint` (tại `client/web-app`) | Pass, exit 0; còn 5 warning có sẵn | `2026-08-16` |
| `npx vite build` (tại `client/web-app`) | Pass; bundle và Service Worker build thành công | `2026-08-16` |
| `npm run build` (tại `client/web-app`) | Fail trước lỗi có sẵn ở `src/lib/meetingDisplay.ts` và `src/lib/meetingNotesApi.ts` do import tương đối thiếu `.js` | `2026-08-16` |
| `git diff --check` | Pass | `2026-08-16` |

Tests not run and reason: Không có.

## Risk, rollback and follow-up

- Risks: Người dùng cần tải lại trang để nhận JavaScript mới; không tự reload để tránh làm mất draft đang sửa.
- Rollback: Revert `AppUpdateNotice`, helper theo dõi Service Worker, bản dịch, wiring trong AppShell và regression test.
- Follow-up: Sửa lỗi import extension TypeScript trong meeting API để `npm run build` xanh hoàn toàn.

## Merge and deployment

- Merge status: Chưa commit/merge.
- Environment / deployed SHA or artifact: Chưa deploy.
- Health/log evidence: Không áp dụng.
- Previous known-good / rollback verification: Chưa áp dụng.
