# WHAT_CHANGED — Sửa tràn URL trong bubble chat

| Field | Value |
| --- | --- |
| Task ID | `chat-url-overflow-20260817` |
| Status | In progress — local fix, not deployed |
| Date | `2026-08-17` |
| Lead | Codex |
| Agents / lanes | `controller: chat UI + regression test` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `not committed` |
| PR / issue / ADR | User-reported screenshot |

## Intent and acceptance criteria

- Intent: URL dài trong tin nhắn người dùng không làm tràn ngang khung chat.
- Observable acceptance criteria: bubble bật wrapping cho chuỗi dài và test hồi quy với URL Google Sheets pass.
- Non-goals: không đổi nội dung hoặc logic gửi tin nhắn.

## Changes

- Observable behavior: thêm `break-words` và `whitespace-pre-wrap` cho bubble người dùng.
- Components/files: `client/web-app/src/pages/DailyBriefingPage.tsx`, `client/web-app/tests/DailyBriefingStreaming.test.tsx`.
- Config/migration/API compatibility: không đổi.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `npx vitest run tests/DailyBriefingStreaming.test.tsx -t 'wraps long URLs'` | pass: 1 test | `2026-08-17` |
| `npm run lint -- src/pages/DailyBriefingPage.tsx tests/DailyBriefingStreaming.test.tsx` | pass | `2026-08-17` |
| `git diff --check` | pass | `2026-08-17` |

Tests not run and reason: full frontend build remains affected by unrelated existing TypeScript import-extension errors in meeting notes files; no deployment was requested in this task.

## Risk, rollback and follow-up

- Risks: low; wrapping only affects presentation of user messages.
- Rollback: revert the scoped class and regression test.
- Follow-up: verify visually in the deployed PWA after the frontend deployment path is available.

## Merge and deployment

- Merge status: not merged.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: not applicable.

