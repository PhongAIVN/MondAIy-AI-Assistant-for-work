# WHAT_CHANGED — Hoàn thiện phát hiện xung đột lịch theo cửa sổ

| Field | Value |
| --- | --- |
| Task ID | User request: kiểm tra và hoàn thiện luồng nhận ra lịch người dùng bị trùng |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | Codex |
| Agents / lanes | Research: source-of-truth/code-path review; implementation: backend conflict candidate query; validation: backend/frontend regression review |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | working tree; not merged |
| PR / issue / ADR | PRD FR-032/FR-100–105; ADR-007; ADR-009 |

## Intent and acceptance criteria

- Intent: Không bỏ sót sự kiện lịch kéo dài vào cửa sổ đang quét khi phát hiện xung đột với task.
- Observable acceptance criteria:
  - Event bắt đầu trước cửa sổ nhưng còn giao với cửa sổ được phát hiện.
  - Event không giao với cửa sổ vẫn bị bỏ qua.
  - Các hành vi idempotency, ownership và resolve hiện có không đổi.
- Non-goals: Không mở rộng thành phát hiện event-với-event; không đổi schema, provider, privacy hoặc quyết định ghi lịch.

## Changes

- Observable behavior: Candidate event được chọn theo giao nhau của khoảng thời gian, có giữ fallback cho event thiếu end.
- Components/files: `src/services/schedule_conflicts.py`, regression tests, this change record.
- Config/migration/API compatibility: Không đổi API/schema/migration.

## Agent handoffs and integration

- Ownership boundaries: Chỉ lane implementation sở hữu service và backend tests; frontend lane chỉ review read-only.
- Integration order/conflicts: Backend logic và regression test cùng thay đổi; không có contract dependency.
- Independent review: Read-only final diff review completed; no schema/API or unrelated-file changes found.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `pytest -q tests/test_services/test_schedule_conflicts.py tests/test_api/test_schedule_conflicts.py` | pass — 39 passed in 4.48s (with local PostgreSQL access) | `2026-08-16` |
| `ruff check src/services/schedule_conflicts.py tests/test_services/test_schedule_conflicts.py` | pass — All checks passed | `2026-08-16` |
| `python3 -m compileall -q src/services/schedule_conflicts.py` | pass | `2026-08-16` |
| `git diff --check` | pass | `2026-08-16` |

Tests not run and reason: `mypy src/` chưa chạy được vì `mypy` không có trong PATH hoặc project `.venv`; frontend checks không chạy vì không có thay đổi frontend.

## Risk, rollback and follow-up

- Risks: Query candidate rộng hơn có thể làm tăng số cặp cần classify trong cửa sổ; vẫn bounded bởi cửa sổ detect và user scope.
- Rollback: Revert commit chứa thay đổi service/test; không có migration.
- Follow-up: Event-với-event conflict cần decision riêng nếu muốn đưa vào scope.

## Merge and deployment

| Item | Value |
| --- | --- |
| Batch / date | `schedule-conflict-window` / `2026-08-16` |
| User-visible update | Không bỏ sót event dài giao vào cửa sổ quét |
| Scope | backend + tests; no deploy |
| Source | not merged |
| Validation | Pending |
| Status | Integrated |
| Rollback | Revert change commit |

- Merge status: Đã tích hợp vào working tree; chưa commit/merge/push/deploy.
- Environment / deployed SHA or artifact: None.
- Health/log evidence: None; chưa deploy.
- Previous known-good / rollback verification: Base SHA ở trên.
