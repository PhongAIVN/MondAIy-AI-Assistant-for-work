# WHAT_CHANGED — Projects navigation always visible

| Field | Value |
| --- | --- |
| Task ID | `projects-nav-always-visible` |
| Record schema | `v2` |
| Status | In progress — validated locally, awaiting user review |
| Date | `2026-08-26` |
| Lead | `Codex` |
| Agents / lanes | `Codex: production code/tests/integration; Antigravity: independent test matrix and review` |
| Base SHA | `bdac66ec68f41472331bacb2752b777e3c2560d1` |
| Head / merge SHA | `not merged` |
| PR / issue / ADR | `not applicable` |

## Intent and acceptance criteria

- Intent: Người dùng luôn vào được trang quản lý Projects, kể cả khi chưa có dự án.
- Observable acceptance criteria: Sidebar luôn có link Projects; danh sách project chỉ hiện khi có dữ liệu; empty state có CTA tạo rõ ràng; chấm nhắc hội thoại chưa xếp vẫn phụ thuộc `hasProjects`.
- Non-goals: Backend/API, ProjectDetailPage, mobile app và các thay đổi UI/UX khác.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: Lối điều hướng tới trang tạo resource không được phụ thuộc vào việc resource đã tồn tại.
- Root cause and shared fix boundary: `Sidebar` dùng `hasProjects` gác cả link quản lý thay vì chỉ gác danh sách và chấm nhắc.
- Dossier: `docs/changes/2026-08-26/projects-nav-always-visible.bugfix.json`.
- Sibling cases and counterexample: 0/1+ projects; empty overview VI/EN; reminder dot off/on theo project inventory và assignment.

## Changes

- Observable behavior: Link Projects luôn hiện và điều hướng tới `/projects`; list project vẫn chỉ hiện khi có dữ liệu; empty state có CTA focus vào form tạo; reminder dot giữ semantics cũ.
- Components/files: `Sidebar.tsx`, `ProjectsPage.tsx`, `SidebarProjectsNavigation.test.tsx`, `shellNavigation.test.ts`.
- Config/migration/API compatibility: Không đổi config, migration hay API.

## Agent handoffs and integration

- Ownership boundaries: Codex là writer duy nhất; Antigravity read-only.
- Integration order/conflicts: Không có lane ghi chồng file.
- Independent review: Antigravity PASS code/behavior trên exact file hashes; không thấy blocker correctness/accessibility/regression.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `npx vitest run` (baseline) | 358 passed, 1 failed / 88 files; fail: `RoutinesPage — create flow > creates a from-scratch routine with real instructions and a schedule` timeout 5000ms | 2026-08-26 |
| `npx vitest run tests/SidebarProjectsNavigation.test.tsx` | 7 passed / 1 file | 2026-08-26 |
| `node --experimental-strip-types --test tests/shellNavigation.test.ts` | 6 passed | 2026-08-26 |
| `npx vitest run` (final candidate) | 361 passed, 5 failed / 89 files; scope tests 7/7 pass; baseline Routines timeout + 4 non-scope failures dưới contention | 2026-08-26 |
| `npx vitest run tests/AdminProgramsPage.test.tsx tests/SignUpPage.test.tsx tests/TasksCalendarPage.test.tsx` | 22 passed; cả 4 failure mới của full run đều xanh khi chạy riêng | 2026-08-26 |
| `npx tsc --noEmit` | Pass | 2026-08-26 |
| `npx oxlint` | Exit 0; 9 warning có sẵn, không có warning mới trong test/ProjectsPage | 2026-08-26 |
| `npm run build` | Pass; Vite 2442 modules + PWA service worker | 2026-08-26 |
| Bug-fix dossier validator + `git diff --check` | Pass; 5 cases / 3 dimensions | 2026-08-26 |

Proof level / claim ceiling: `integration` — behavior router, inventory states, empty-state CTA, i18n VI/EN và frontend build đã được kiểm chứng; chưa có browser E2E.

Tests not completed: Full Vitest không lặp lại đúng failure set baseline do 4 test ngoài scope fail dưới contention 5s; cả 4 đều pass khi chạy riêng (22/22). Không chạy browser E2E/mobile vì ngoài phạm vi brief.

## Risk, rollback and follow-up

- Risks: Full-suite timing chưa ổn định khi chạy parallel; targeted behavior và các file phát sinh failure đều pass riêng.
- Rollback: Revert diff của task; chưa commit.
- Follow-up: Không có ngoài phạm vi brief.

## Merge and deployment

- Merge status: Chưa merge; user yêu cầu chưa commit.
- Environment / deployed SHA or artifact: Không deploy.
- Health/log evidence: Không áp dụng.
- Previous known-good / rollback verification: `origin/main@bdac66ec68f41472331bacb2752b777e3c2560d1`.

| Item | Value |
| --- | --- |
| Batch / date | `projects-nav-always-visible` / `2026-08-26` |
| User-visible update | Lối vào Projects luôn hiện; empty state có CTA tạo |
| Scope | Frontend |
| Source | Working tree, chưa commit |
| Validation | 7/7 scope tests; shell 6/6; tsc/oxlint/build pass; full-suite contention được cô lập 22/22 |
| Status | Planned — validated locally, awaiting user review |
| Rollback | `origin/main@bdac66ec68f41472331bacb2752b777e3c2560d1` |
