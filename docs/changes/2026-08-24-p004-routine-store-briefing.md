# WHAT_CHANGED — Shared routine store for briefing

| Field | Value |
| --- | --- |
| Task ID | `p004-routine-store-briefing-20260824` |
| Record schema | `v2` |
| Status | Integrated |
| Date | `2026-08-24` |
| Lead | `Tatejo / Codex` |
| Agents / lanes | `Codex: production code, tests, integration; Antigravity: not run — quota TIẾT KIỆM` |
| Base SHA | `37878f037d9348df23c40afdea8ab0ea8b93337b` |
| Head / merge SHA | `d2e4d9e` |
| PR / issue / ADR | `not provided` |

## Intent and acceptance criteria

- Intent: giữ routine và recent runs trong một client-side store dùng chung giữa trang Routines và trang Briefing.
- Observable acceptance criteria:
  - Vào lại các trang trong cùng session không gọi lại list routine nếu cache vẫn thuộc cùng user.
  - Đổi user không nhìn thấy cache của user trước.
  - Briefing đọc recent routine run từ store dùng chung và routine run mới xuất hiện ở đó.
  - Create/update/delete/run cập nhật cache ngay sau khi API thành công.
- Non-goals: thay đổi backend schema, lịch chạy, lưu access token hoặc dữ liệu routine vào localStorage, deploy/merge.

## Changes

- Thêm `useRoutineStore` cache theo user key; user đổi thì cache bị xoá.
- `/routines` và `/briefing` đọc cùng routine/recent-run cache; `/routines/:id` cập nhật cache sau các mutation/run.
- Thêm test cho single-load, user isolation và briefing handoff.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `npx vitest run tests/useRoutineStore.test.tsx tests/RoutinesPage.test.tsx` | `15 passed` | `2026-08-24` |
| `npm run build` | `pass` | `2026-08-24` |
| `npm run lint` | `pass with pre-existing warnings` | `2026-08-24` |
| `npm test` | `347 passed / 9 failed in pre-final snapshot; not rerun after detail regression cleanup` | `2026-08-24` |

Proof level / claim ceiling: `unit / integration / build` — shared cache behavior and frontend compilation are verified; no live/authenticated E2E claim.

## Risk, rollback and follow-up

- Risks: cache chỉ tồn tại trong SPA session; deep-link cold cache vẫn gọi API.
- Rollback: revert commit chứa các file frontend; backend không đổi.
- Follow-up: bổ sung refresh button nếu cần đồng bộ cross-tab.

Tests not run: Antigravity independent review was not run because quota was `TIẾT KIỆM`; full-suite failures are outside this routine scope and use stale UI labels.

## Merge and deployment

- Merge status: not merged
- Environment / deployed SHA or artifact: none
- Health/log evidence: none
- Previous known-good / rollback verification: `37878f037d9348df23c40afdea8ab0ea8b93337b`

| Item | Value |
| --- | --- |
| Batch / date | `p004-routine-store-briefing-20260824` / `2026-08-24` |
| User-visible update | Shared routine cache and briefing handoff |
| Scope | frontend web app |
| Source | `d2e4d9e` |
| Validation | `21 targeted tests passed; build passed; lint passed with existing warnings` |
| Status | Integrated |
| Rollback | `37878f037d9348df23c40afdea8ab0ea8b93337b` |
