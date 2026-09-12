# WHAT_CHANGED — Extension hỏi bắt đầu/xong task

| Field | Value |
| --- | --- |
| Task ID | extension-work-checkin |
| Record schema | v2 |
| Status | In progress — validated, awaiting user review |
| Date | 2026-08-27 |
| Lead | Codex |
| Agents / lanes | Codex: production code/tests; Antigravity: test matrix + independent review |
| Base SHA | `662187171153d306be5f30ccd67e6d98063df704` |
| Head / merge SHA | not merged; brief requires no commit |
| PR / issue / ADR | `docs/projects/engineering/adr/adr-021-cam-bien-thoi-gian-lam-viec-va-nhip-ngay.md` |

## Intent and acceptance criteria

- Intent: extension hỏi gần lúc làm việc để thu `startedAt`/`actualMinutes` từ xác nhận thật.
- Observable acceptance criteria: task chưa bắt đầu được hỏi một lần; task đã bắt đầu quá estimate được hỏi xong một lần; ngoài `[08:00, 22:00)` không hỏi và không gọi API task check-in; mỗi poll tối đa một task; nút xác nhận gọi đúng API.
- Non-goals: backend/schema/migration, web app, học nhịp ngày/nhắc ngủ, manifest permissions, commit/push/deploy.

## Bug-fix generalization

- Change kind: not a bug fix (bounded feature).
- Bug class and violated invariant: not applicable.
- Root cause and shared fix boundary: cảm biến `completedAt` không đại diện thời gian làm thật; boundary chỉ ở extension.
- Dossier: not applicable.
- Sibling cases and counterexample: task đã hỏi, task trước/sau giờ làm, nhiều task cùng eligible.

## Changes

- Observable behavior: hỏi bắt đầu một lần cho task chưa có `startedAt`; sau 30 phút hỏi xong một lần; mỗi poll một task; không hỏi và không fetch confirmed tasks ngoài `[08:00, 22:00)`.
- Components/files: `client/extension/entrypoints/background.ts`, `entrypoints/background.test.ts`, `lib/api.ts`, `lib/storage.ts`, `lib/taskCheckIn.ts`, `lib/taskCheckIn.test.ts`, `types/index.ts` và focused tests.
- Config/migration/API compatibility: dùng API `/start` và `/complete` đã có; không đổi config/migration.

## Agent handoffs and integration

- Ownership boundaries: Codex là writer duy nhất production code; Antigravity read-only production code.
- Integration order/conflicts: test matrix → implementation → exact working-tree review; không commit theo brief.
- Independent review: Antigravity PASS; không có finding correctness/security blocking.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `pnpm install --frozen-lockfile` | pass; 271 packages theo lockfile | 2026-08-27 17:23 +07 |
| `WXT_WEB_APP_URL=http://localhost:5173 WXT_API_BASE_URL=http://localhost:8000 pnpm exec vitest run lib/taskCheckIn.test.ts lib/api.test.ts` | 2 files, 17 passed | 2026-08-27 17:25 +07 |
| `WXT_WEB_APP_URL=http://localhost:5173 WXT_API_BASE_URL=http://localhost:8000 pnpm test` | 10 files, 123 passed | 2026-08-27 17:25 +07 |
| `pnpm compile` | pass, `tsc --noEmit` | 2026-08-27 17:25 +07 |
| `pnpm build` | pass, Chrome MV3 artifact 1.08 MB | 2026-08-27 17:24 +07 |
| `bash tests/test_build_artifact.sh .output/chrome-mv3 production` | pass; production targets đúng, không cross-world modulepreload | 2026-08-27 17:24 +07 |
| `git diff --check` | pass | 2026-08-27 17:26 +07 |
| Baseline: `WXT_API_BASE_URL=http://127.0.0.1:8000 WXT_WEB_APP_URL=http://127.0.0.1:3000 pnpm test` | 10 files, 123 passed | 2026-08-27 20:48 +07 |
| `WXT_API_BASE_URL=http://127.0.0.1:8000 WXT_WEB_APP_URL=http://127.0.0.1:3000 pnpm exec vitest run lib/taskCheckIn.test.ts entrypoints/background.test.ts` | 2 files, 24 passed | 2026-08-27 20:56 +07 |
| `WXT_API_BASE_URL=http://127.0.0.1:8000 WXT_WEB_APP_URL=http://127.0.0.1:3000 pnpm test` | 11 files, 136 passed | 2026-08-27 20:56 +07 |
| `pnpm compile` | pass, `tsc --noEmit` | 2026-08-27 20:57 +07 |
| `git diff --check` | pass | 2026-08-27 20:54 +07 |

Proof level / claim ceiling: unit + TypeScript compile + production artifact — logic và wiring build được; chưa chứng minh OS notification bằng Chrome UI thật.

Tests not run and reason: chưa load artifact và bấm notification trong Chrome UI; brief chỉ yêu cầu dùng hạ tầng test sẵn có và build, không có E2E harness cho background notification.

## Risk, rollback and follow-up

- Risks: giờ làm dùng local browser; neutral estimate 30 phút vì TaskResponse chưa expose estimate; background guard có integration test bằng Chrome mock nhưng chưa chạy UI Chrome thật.
- Rollback: bỏ các diff trong task này trước khi commit.
- Follow-up: backend expose estimate nếu cần thay neutral fallback bằng estimate cá nhân hoá.

## Merge and deployment

- Merge status: not merged; brief requires no commit/push.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: base SHA `6621871`.

| Item | Value |
| --- | --- |
| Batch / date | extension-work-checkin / 2026-08-27 |
| User-visible update | Extension hỏi “bắt đầu chưa / xong chưa” tối đa một lần mỗi câu |
| Scope | client/extension only |
| Source | uncommitted working-tree diff on `6621871` |
| Validation | 24 focused work-hours + 136 full tests; compile/build/artifact pass; Antigravity PASS |
| Status | Planned |
| Rollback | discard task-owned uncommitted diff |
