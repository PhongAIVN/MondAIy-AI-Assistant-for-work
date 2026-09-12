# WHAT_CHANGED — Sửa cảnh báo lỗi khó đọc ở dark mode

| Field | Value |
| --- | --- |
| Task ID | `darkmode-agent-error-20260816` |
| Status | In progress — local fix, not deployed |
| Date | `2026-08-16` |
| Lead | Codex |
| Agents / lanes | `controller: UI fix + regression test` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `not committed` |
| PR / issue / ADR | User-reported screenshot |

## Intent and acceptance criteria

- Intent: cảnh báo lỗi trong luồng Briefing phải đọc được khi bật dark mode.
- Observable acceptance criteria: không còn nền sáng hardcode; cảnh báo dùng theme tokens và có regression test.
- Non-goals: không đổi nội dung quota/feedback hoặc luồng xử lý lỗi.

## Changes

- Observable behavior: nền cảnh báo dùng `--color-danger-soft`, chữ dùng `--color-text-primary`, nên dark mode không còn chữ sáng trên nền hồng nhạt.
- Components/files: `client/web-app/src/pages/DailyBriefingPage.tsx`, `client/web-app/tests/DailyBriefingStreaming.test.tsx`.
- Config/migration/API compatibility: không đổi.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `npx vitest run tests/DailyBriefingStreaming.test.tsx -t 'uses theme tokens'` | pass: 1 test | `2026-08-16` |
| `npm run lint -- src/pages/DailyBriefingPage.tsx tests/DailyBriefingStreaming.test.tsx` | pass | `2026-08-16` |
| `git diff --check` | pass | `2026-08-16` |
| `npx vitest run tests/DailyBriefingStreaming.test.tsx` | 6 passed, 1 pre-existing/환경-dependent timeout at 5s | `2026-08-16` |

Tests not run and reason: full production build remains affected by unrelated existing TypeScript import-extension errors in meeting notes files.

## Risk, rollback and follow-up

- Risks: low; only presentation token changed.
- Rollback: revert the scoped class change and regression test.
- Follow-up: run the normal frontend build after the unrelated import errors are resolved.

## Merge and deployment

- Merge status: not merged.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: not applicable.

