# WHAT_CHANGED — sửa 4 ca QA màn hình Task/To-do

| Field | Value |
| --- | --- |
| Task ID | `TC_UI_04_01/04/05/06` |
| Record schema | `v2` |
| Status | In progress — implementation validated, awaiting user review |
| Date | `2026-08-27` |
| Lead | `Codex` |
| Agents / lanes | `Codex: production/tests; Antigravity: test matrix + independent validation` |
| Base SHA | `6b18c78a7b31f249f1a117c50af715a91e517a91` |
| Head / merge SHA | `not merged — brief forbids commit` |
| PR / issue / ADR | `BRIEF.md`; PR/ADR not applicable |

## Intent and acceptance criteria

- Intent: làm dữ liệu task backend đã có trở thành thông tin và thao tác nhìn thấy được trên UI.
- Observable acceptance criteria: hiện priority/phiếu giao việc; lọc priority AND status; thống kê live; global empty state gửi prompt lập kế hoạch sang chat đúng một lần.
- Non-goals: backend/API/schema/model; trash/delete/cancelTask; source/deadline filter; commit/push/deploy.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: UI task không được làm mất dữ liệu có giá trị, bịa dữ liệu rỗng, hoặc tính derived state từ tập đã lọc.
- Root cause and shared fix boundary: `TasksPage` chỉ render legacy fields/status filter; fix tại frontend task type và task-list derivation/render boundary.
- Dossier: `docs/changes/2026-08-27/tasks-ui-qa.bugfix.json`.
- Sibling cases and counterexample: nhiều priority/status/deadline; null/blank/unknown priority; global-empty khác filter-empty.

## Changes

- Observable behavior: task card hiện priority/assignment fields thật; filter priority AND status; sort deadline rồi priority; live stats; global empty CTA auto-send chat prompt một lần.
- Components/files: `TasksPage.tsx`, `DailyBriefingPage.tsx`, `tasksApi.ts`, `chatHandoff.ts`, `translations.ts`, bốn test files liên quan, `BAOCAO.md`.
- Config/migration/API compatibility: frontend-only; không đổi API/config/migration.

## Agent handoffs and integration

- Ownership boundaries: Codex là writer duy nhất; Antigravity read-only cho production code.
- Integration order/conflicts: frontend type → derivation/UI → tests → independent validation; không có lane writer xung đột.
- Independent review: Antigravity rerun exact final working-tree diff: targeted 33/33, full 388/388, tsc/oxlint/build exit 0; PASS, không có correctness/security blocker.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `cd client/web-app && npx vitest run` | baseline pass: 382 tests / 92 files; failing-name set empty | `2026-08-27` |
| `cd client/web-app && npx vitest run tests/TasksCalendarPage.test.tsx tests/DailyBriefingStreaming.test.tsx tests/DailyBriefingApproval.test.tsx tests/DailyBriefingVisionSuggestions.test.tsx` | pass: 38 tests / 4 files | `2026-08-27` |
| `cd client/web-app && npx vitest run` | post-change pass: 388 tests / 92 files; failing-name set empty | `2026-08-27` |
| `cd client/web-app && npx tsc --noEmit` | pass, exit 0 | `2026-08-27` |
| `cd client/web-app && npx oxlint` | pass, exit 0; 10 pre-existing/out-of-scope warnings | `2026-08-27` |
| `cd client/web-app && npm run build` | pass, exit 0; existing chunk-size/deprecation warnings | `2026-08-27` |

Proof level / claim ceiling: component/integration build — bốn TC UI được chứng minh trong jsdom; chưa chạy browser E2E trực quan.

Tests not run and reason: browser E2E không được brief yêu cầu; component interaction + full suite + production build đã chạy.

## Risk, rollback and follow-up

- Risks: priority là chuỗi mở nên alias chuẩn được gom theo band, giá trị lạ vẫn hiện/lọc theo chuỗi gốc; chat handoff one-shot đã implement và clear state trước request.
- Rollback: bỏ diff frontend/test/evidence của task này; chưa commit.
- Follow-up: independent final validation sau khi implementation ổn định.

## Merge and deployment

- Merge status: not merged; brief yêu cầu chưa commit.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: base SHA ở trên.

| Item | Value |
| --- | --- |
| Batch / date | `tasks-ui-qa` / `2026-08-27` |
| User-visible update | Task priority/detail/filter/stats/empty-state chat CTA |
| Scope | frontend only |
| Source | working tree on `6b18c78` |
| Validation | baseline 382; post-change 388; tsc/oxlint/build pass |
| Status | Planned — no integration requested; working tree validated |
| Rollback | discard task-local uncommitted diff |
