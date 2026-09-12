# WHAT_CHANGED — Khôi phục conflict/proposal sau calendar sync

| Field | Value |
| --- | --- |
| Task ID | User report: không thấy propose các việc và task bị trùng nhau |
| Status | Implemented; current integrated release not yet deployed |
| Date | `2026-08-23` |
| Lead | Codex |
| Agents / lanes | Một owner; không fan-out do quota đang tiết kiệm |
| Base SHA | `f0bbf165a446ade5460753c669c26e5c0aa205a6` |

## Intent and acceptance criteria

- Conflict detection phải chạy lại sau khi `calendar_events` cache tải xong.
- Đổi tuần cũng phải refresh conflict theo cache mới.
- Khi có conflict, UI phải hiện cả hai bên và gợi ý ưu tiên hiện có.
- Không đổi API, schema, rule phân loại hoặc resolution.

## Root cause

`ScheduleConflictPanel` detect song song với `TasksPage.loadCalendar`. Detect đọc cache,
nhưng không có tín hiệu để chạy lại sau khi calendar request hoàn tất; race này làm panel
giữ kết quả rỗng dù lưới đã có event và task trùng giờ.

## Scope

`TasksPage` phát một `calendarSyncVersion` sau mỗi lần calendar load; panel đưa version vào
dependency của detect. Thêm frontend regression test cho empty-first, conflict-after-sync.

## Validation

| Command | Result |
| --- | --- |
| `npx vitest run tests/ScheduleConflictPanel.test.tsx` | pass — 9 tests |
| `npm run build` | pass — `tsc -b` + Vite/PWA build |
| `npx oxlint src/pages/TasksPage.tsx src/components/calendar/ScheduleConflictPanel.tsx tests/ScheduleConflictPanel.test.tsx` | pass |
| `git diff --check` | pass |

The original artifact failure was fixed in the same release by aligning the test
with the current Manifest V3 side-panel contract (`sidepanel.html`). The full-suite
result recorded below is prior release evidence; current validation is targeted.

## Deployment

| Item | Value |
| --- | --- |
| Batch / date | `schedule-conflict-calendar-sync-race` / `2026-08-23` |
| User-visible update | Conflict panel không còn giữ empty state sau calendar sync |
| Scope | frontend |
| Source | integrated branch (pending deploy) |
| Validation | Targeted Vitest 9/9, build and lint pass |
| Status | Implemented; not deployed |
| Rollback | Revert change commit |

## Prior deployment evidence

The previous frontend deployment used source `da5bc786b8f5b5036f344b2e840d1c1d47a369d0`
with Vercel alias and API health checks recorded at that time. It is not evidence
for the current integrated SHA.
