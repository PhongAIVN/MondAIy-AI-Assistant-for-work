# WHAT_CHANGED — Multi-cohort lane + mẫu lịch chương trình

| Field | Value |
| --- | --- |
| Task ID | `p004-cohort-refresh-20260902` |
| Record schema | `v2` |
| Status | Merged to `main`, **not deployed** |
| Date | `2026-09-02` |
| Lead | `Tatejo (Claude Opus 5)` |
| Agents / lanes | `Tatejo: gỡ conflict, gate, merge` |
| Base SHA | `d31ff5a7611a5c2b23b68a7076c86cf3be5f8a34` |
| Head / merge SHA | `244337d8954dc4ae3b8546e7fdb11c5389807964` (`main`) |
| Nhánh nguồn | `agent/cohort-refresh-20260820` (3 commit, 2026-08-20) |
| Nhánh tích hợp | `integrate/cohort-refresh-20260902` |
| PR / issue / ADR | none — fast-forward sau khi gate xanh trên nhánh tích hợp |

## Intent and acceptance criteria

- Intent: lấy lại lane multi-cohort đã bị cất từ 2026-08-20, sau khi `main` đã đi trước 12 ngày.
- Observable acceptance criteria: backend + frontend gate xanh trên **đúng tree sẽ push**; không xoá file nào của `main`; không mất tính năng `main` thêm sau ngày nhánh tách.
- Non-goals: deploy, migration dữ liệu, đụng production, sửa 9 nhánh `origin/sync/*` còn tồn.

## Changes

- Observable behavior:
  - Thêm API admin quản lý **mẫu lịch chương trình** (`admin_program_schedule_templates`) và service sinh event từ mẫu.
  - Thêm service `program_cohorts` cho lane multi-cohort; `scope.py` phân giải cohort theo `User`.
  - `google_drive`: phân loại lỗi 403 khi list file thay vì gộp chung mọi lỗi.
- Components/files: 40 file, `+1071 / −47`. Năm file mới:
  `src/api/admin_program_schedule_templates.py`, `src/models/program_schedule_template.py`,
  `src/services/program_cohorts.py`, `src/services/program_schedule_templates.py`,
  `tests/test_services/test_program_schedule_templates.py`.
- Config/migration/API compatibility: thêm `PROGRAM_COHORT_SLUG` + `APP_TIMEZONE` vào env test; **không** migration; route mới nằm dưới `/api/v1`, không đổi contract cũ.

## Conflict resolution — 13 hunk / 8 file

Nhánh tách trước `main` 12 ngày, nên **đa số conflict là nhánh xoá thứ `main` thêm sau**, không phải hai bên tranh nhau một thiết kế. Chia hai nhóm:

**Giữ bản `main`** (nhánh chỉ tụt hậu):

| File | Lý do |
| --- | --- |
| `AGENTS.md` | `main` sửa cổng merge ngày 25/08; nhánh còn bản "trước mọi push" đã bị thay có chủ đích |
| `src/agents/tools/program_information_tool.py` | nhánh chỉ tách biến, logic phân quyền y hệt |
| `src/models/schemas.py` | nhánh thiếu nguyên khối schema `Consent*` / `Learning*` của `main` |
| `tests/test_api/v1/test_program_information.py` | test `main` phủ rộng hơn (B chỉ thấy `public`, A thấy tất cả) |

**Giữ cả hai** (nhánh có phần mới thật):

| File | Ghép gì |
| --- | --- |
| `src/main.py` | thêm router mẫu lịch + đăng ký model, **vẫn giữ** `announcement_candidates` / `discord_channel` / `project` của `main` |
| `src/services/scope.py` | giữ cả `llm_usage_scope` lẫn `import User` |
| `tests/conftest.py` | giữ khối env test của `main` (~298 test phụ thuộc `APP_SECRET_KEY`), thêm `APP_TIMEZONE` + `PROGRAM_COHORT_SLUG` |
| `client/web-app/tests/agentApi.test.ts` | thân test assert **cả** `taskBacklogCount === 4` **lẫn** `sources[0].url` → fixture phải mang cả hai trường |

Bẫy đáng ghi: `agentApi.test.ts` là hunk duy nhất mà "chọn một bên" làm test đỏ — hai phía sửa cùng một chuỗi SSE fixture nhưng thêm hai trường khác nhau. Cũng đã gỡ 2 dòng assert bị auto-merge nhân đôi.

Commit `8968d654` tự đặt tên `wip` nhưng **không dở dang**: nó là lát cắt "cất lane lại", có test kèm cho `AdminProgramEventsPage`, `AdminUsersPage`, `DailyBriefingStreaming`.

## Validation evidence

Chạy trên nhánh tích hợp; `main` sau đó fast-forward nên **tree push lên khớp byte-đúng với tree đã gate** (`git rev-parse HEAD^{tree}` == tree của nhánh tích hợp).

| Command | Result | Timestamp |
| --- | --- | --- |
| `pytest tests/ -q -p no:randomly` | `3071 passed, 6 skipped` (baseline trước merge: `3052 passed`) | 2026-09-02 |
| `npm test` (client/web-app) | `96 test files, 448 tests passed`, rc=0 | 2026-09-02 |
| `node --experimental-strip-types --test tests/agentApi.test.ts` | `pass 3, fail 0` — file sửa tay | 2026-09-02 |
| `npx tsc -b --force` | rc=0 | 2026-09-02 |
| `npm run lint` (oxlint) | rc=0 | 2026-09-02 |
| `ruff check src/ tests/` | `All checks passed` | 2026-09-02 |
| `git diff --name-status main..HEAD \| grep '^D'` | trống — không xoá file nào | 2026-09-02 |
| `git fetch` + `git log d31ff5a7..origin/main` | trống — không có race khi push | 2026-09-02 |

Proof level / claim ceiling: **gate offline pass**. Không có bằng chứng production — đợt này không deploy, không lấy log/metric từ instance thật.

## Risk, rollback and follow-up

- Risk: route admin mới chưa chạy trên instance thật lần nào; mọi khẳng định ở đây dừng ở mức test.
- Đã ghi nhận, chưa sửa: `tests/test_services/test_program_schedule_templates.py` phát `InsecureKeyLengthWarning` (HMAC key 15 byte) do `APP_SECRET_KEY` test-only ngắn hơn 32 byte. Chỉ warning, không fail.
- Rollback: revert `244337d8`; không có mutation dữ liệu/config/migration.
- Follow-up: còn 9 nhánh `origin/sync/*` (2026-08-17, 32–55 commit, conflict 22–43 file) chưa quyết bỏ hay giữ.

| Item | Value |
| --- | --- |
| Batch / date | `cohort-refresh` / `2026-09-02` |
| User-visible update | Admin quản lý mẫu lịch chương trình; lane multi-cohort; lỗi 403 Drive phân loại rõ |
| Scope | Backend API/service + model, test frontend |
| Source | `244337d8954dc4ae3b8546e7fdb11c5389807964` |
| Validation | 3071 passed; FE 448 passed; tsc/oxlint/ruff pass |
| Status | Merged, not deployed |
| Rollback | revert `244337d8` |
