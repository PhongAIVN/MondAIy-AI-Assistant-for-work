# WHAT_CHANGED — Thu gọn menu tài khoản sidebar

| Field | Value |
| --- | --- |
| Task ID | `sidebar-account-menu-items` |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | `Codex` |
| Agents / lanes | `Codex: Sidebar + test + validation` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `Working tree, chưa commit` |
| PR / issue / ADR | `Không có` |

## Intent and acceptance criteria

- Intent: Xóa các mục `Chạy tổng hợp`, `Thông báo` và `Routine` khỏi menu tài khoản trong sidebar.
- Observable acceptance criteria: Menu tài khoản không còn ba mục trên; vẫn giữ `Thư viện nguồn` và `Dữ liệu & Quyền riêng tư`.
- Non-goals: Không xóa route, page hoặc chức năng phía sau ba mục này.

## Changes

- Observable behavior: `accountExtraLinks` không còn các liên kết `/run`, `/notifications` và `/routines`.
- Components/files: `client/web-app/src/components/layout/Sidebar.tsx`; `client/web-app/tests/shellNavigation.test.ts`.
- Config/migration/API compatibility: Không thay đổi.

## Agent handoffs and integration

- Ownership boundaries: Một lane duy nhất sở hữu Sidebar và test điều hướng.
- Integration order/conflicts: Không có conflict; không sửa các thay đổi sẵn có ngoài phạm vi.
- Independent review: Đã review diff và kiểm tra `git diff --check`.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `node --experimental-strip-types --test tests/shellNavigation.test.ts` (tại `client/web-app`) | Pass, 4/4 | `2026-08-16` |
| `npm test` (tại `client/web-app`) | Pass, 99 Node tests + 197 Vitest tests, 45 files | `2026-08-16` |
| `npm run lint` (tại `client/web-app`) | Pass, exit 0; còn 5 warning có sẵn | `2026-08-16` |
| `npm run build` (tại `client/web-app`) | Fail trước lỗi có sẵn ở `src/lib/meetingDisplay.ts` và `src/lib/meetingNotesApi.ts` do import tương đối thiếu `.js`; không liên quan diff | `2026-08-16` |
| `git diff --check` | Pass | `2026-08-16` |

Tests not run and reason: Không có.

## Risk, rollback and follow-up

- Risks: Ba route vẫn tồn tại nhưng không còn entry trực tiếp trong menu tài khoản; người dùng cần truy cập qua luồng khác nếu route còn được dùng.
- Rollback: Revert thay đổi trong `Sidebar.tsx` và `shellNavigation.test.ts`.
- Follow-up: Sửa lỗi import extension trong build TypeScript nếu cần khôi phục build xanh toàn repo.

## Merge and deployment

- Merge status: Chưa commit/merge.
- Environment / deployed SHA or artifact: Chưa deploy.
- Health/log evidence: Không áp dụng.
- Previous known-good / rollback verification: Chưa áp dụng.
