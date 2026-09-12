# WHAT_CHANGED — Bó gọn task decision cards

| Field | Value |
| --- | --- |
| Task ID | `p004-task-cards-noise-20260827` |
| Record schema | `v2` |
| Status | In progress |
| Date | `2026-08-27` |
| Lead | `Codex` |
| Agents / lanes | `Codex: production/tests; Antigravity: test matrix + independent final review` |
| Base SHA | `1d463149f7878b02d4419d37dd17b4a54deef6d9` |
| Head / merge SHA | `uncommitted by brief` |
| PR / issue / ADR | `BRIEF.md; no ADR required` |

## Intent and acceptance criteria

- Intent: không biến một câu agenda thành hàng trăm card; chỉ `proposed` còn cần quyết định mới được xét.
- Observable acceptance criteria: cửa sổ overdue 7 ngày, cap 8, backlog count chính xác, `draft_task` vừa tạo luôn hiện.
- Non-goals: không đổi agent prose, `list_tasks`, planner, task state/data, deploy hoặc push.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: decision surface không được lặp task đã quyết hoặc phát danh sách không giới hạn.
- Root cause and shared fix boundary: `_task_drafts_from_agent_result` gom unbounded proposed+confirmed; sửa một lần tại conversation API boundary.
- Dossier: `docs/changes/2026-08-27/task-cards-noise.bugfix.json`.
- Sibling cases and counterexample: stale, overflow, confirmed list/Sheet, foreign ownership, zero backlog và forced `draft_task`.

## Changes

- Observable behavior: tối đa 8 listed cards; phần proposed bị ẩn trả `taskBacklogCount`; zero không persist dòng thừa.
- Components/files: conversation API/schema/Telegram shared caller, web response types/plumbing, API + frontend tests.
- Config/migration/API compatibility: field response additive; không migration/config change.

## Agent handoffs and integration

- Ownership boundaries: Codex là production writer; Antigravity read-only, không commit/push.
- Integration order/conflicts: một writer, base đúng `origin/main`, chỉ có `BRIEF.md` untracked từ user.
- Independent review: pending exact-candidate result.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| baseline full pytest command from BRIEF | `2809 passed, 7 skipped` | 2026-08-27 |
| targeted API regression | `8 passed`; cả 8 đỏ trước production fix | 2026-08-27 |
| conversation API regression | `40 passed` | 2026-08-27 |
| frontend parser / interaction | `3 passed` / `15 passed` | 2026-08-27 |
| web build / lint | build pass; lint pass với 10 warning ngoài diff | 2026-08-27 |
| full `ruff check src/ tests/` | pass | 2026-08-27 |
| full pytest after change | `2815 passed, 7 skipped` (+6 tests, 0 failed) | 2026-08-27 |
| bug-fix dossier validator | valid: 5 cases across 2 dimensions | 2026-08-27 |

Proof level / claim ceiling: `API integration` — sync/SSE/persisted extras và frontend contract đã kiểm; không claim production/UI render.

Tests not run and reason: production E2E không thuộc brief; không dùng production data.

## Risk, rollback and follow-up

- Risks: task đã được prose nhắc vẫn có thể lặp card vì tool output chưa mang ID.
- Rollback: revert local diff; không có migration hay data mutation.
- Follow-up: mở structured task-ID contract riêng nếu product cho phép sửa `list_tasks`/planner.

## Merge and deployment

- Merge status: not committed/merged by brief.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: local test evidence only.
- Previous known-good / rollback verification: base `1d463149`.

| Item | Value |
| --- | --- |
| Batch / date | `task-cards-noise` / `2026-08-27` |
| User-visible update | Bó task decision cards và trả exact backlog count |
| Scope | Backend response contract + minimal web types; no deploy |
| Source | Uncommitted diff on `1d463149` |
| Validation | Targeted/API/frontend/build/lint/ruff + full pytest 2815 passed |
| Status | Planned (awaiting user review; no commit by brief) |
| Rollback | Discard local diff back to `1d463149` after user review |
