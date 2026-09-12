# WHAT_CHANGED — Định dạng timestamp trong hội thoại

| Field | Value |
| --- | --- |
| Task ID | `conversation-timestamp-format` |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | `Codex` |
| Agents / lanes | `Codex: UI timestamp + formatter + regression test` |
| Base SHA | `Working tree tại thời điểm bắt đầu; chưa commit` |
| Head / merge SHA | `Working tree, chưa commit` |
| PR / issue / ADR | `User-reported UI bug via screenshot` |

## Intent and acceptance criteria

- Intent: Không hiển thị chuỗi ISO thô của `createdAt` trong hội thoại.
- Observable acceptance criteria: `2026-08-16T07:50:54.680Z` hiển thị thành giờ/ngày đọc được theo locale; nhãn đã có như `Vừa xong` vẫn giữ nguyên.
- Non-goals: Không thay đổi timestamp gốc trong API/store và không đổi nội dung nguồn bằng chứng.

## Changes

- Observable behavior: Timestamp tin nhắn trong Daily Briefing và Navigator được format theo ngôn ngữ/trình duyệt.
- Components/files: `client/web-app/src/lib/conversationTimestamp.ts`, `client/web-app/src/pages/DailyBriefingPage.tsx`, `client/web-app/src/components/navigator/ChatMessage.tsx`, `client/web-app/tests/conversationTimestamp.test.ts`.
- Config/migration/API compatibility: Không thay đổi.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `node --experimental-strip-types --test tests/conversationTimestamp.test.ts` (tại `client/web-app`) | Pass, 2/2 | `2026-08-16` |
| `npm test` (tại `client/web-app`) | Pass, 103 Node tests + 199 Vitest tests, 45 files | `2026-08-16` |
| `npm run lint` (tại `client/web-app`) | Pass, exit 0; 5 warning có sẵn | `2026-08-16` |
| `npx vite build` (tại `client/web-app`) | Pass; client và Service Worker build thành công | `2026-08-16` |
| `npm run build` (tại `client/web-app`) | Fail trước lỗi có sẵn ở `src/lib/meetingDisplay.ts` và `src/lib/meetingNotesApi.ts` do import tương đối thiếu `.js` | `2026-08-16` |
| `git diff --check` | Pass | `2026-08-16` |

Tests not run and reason: Không có.

## Risk, rollback and follow-up

- Risks: Timestamp ngày cũ hiển thị cả ngày và giờ; chuỗi không phải ngày hợp lệ được giữ nguyên để không làm mất thông tin cũ.
- Rollback: Revert formatter, hai điểm render và regression test.
- Follow-up: Sửa lỗi import extension TypeScript trong meeting API để `npm run build` xanh hoàn toàn.

## Merge and deployment

- Merge status: Chưa commit/merge.
- Environment / deployed SHA or artifact: Chưa deploy.
- Health/log evidence: Không áp dụng.
- Previous known-good / rollback verification: Chưa áp dụng.
