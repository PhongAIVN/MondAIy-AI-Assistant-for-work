# WHAT_CHANGED — Sửa định tuyến câu hỏi “mai phải làm gì”

| Field | Value |
| --- | --- |
| Task ID | `agenda-query-routing-2026-08-16` |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | `Codex` |
| Agents / lanes | `main: router + regression test + verification` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | `not merged; working tree change` |
| PR / issue / ADR | `none supplied` |

## Intent and acceptance criteria

- Intent: Sửa câu hỏi “Chương trình AI thực chiến mai tôi phải làm gì” bị trả lời như ngoài phạm vi.
- Observable acceptance criteria: câu hỏi được nhận diện là agenda cho ngày mai và lập kế hoạch đọc các nguồn task, lịch, email, Jira và Discord; không bị nhận nhầm là tìm kiếm web.
- Non-goals: không thay đổi phạm vi nguồn dữ liệu hoặc thực hiện deploy.

## Changes

- Observable behavior: nhận diện đúng từ “mai” và không coi cụm “phải làm” là “AI là”.
- Components/files: `src/services/temporal_understanding.py`, `src/services/intent_router.py`, `tests/test_intent_router.py`.
- Config/migration/API compatibility: không có.

## Agent handoffs and integration

- Ownership boundaries: một writer duy nhất trên router và test; không có lane ghi chồng.
- Integration order/conflicts: tích hợp trong working tree; chưa merge vào branch khác.
- Independent review: sẽ review diff và chạy test sau implementation.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `DATABASE_URL=sqlite:////private/tmp/p004-intent-router-test.db python3 -m pytest tests/test_intent_router.py -q` | `15 passed` | `2026-08-16` |
| `DATABASE_URL=sqlite:////private/tmp/p004-backend-regression.db python3 -m pytest tests/ -q` | `1032 passed, 6 skipped, 1 unrelated failure` | `2026-08-16` |
| `ruff check src/services/intent_router.py src/services/temporal_understanding.py tests/test_intent_router.py` | `passed` | `2026-08-16` |
| `ruff check src/ tests/` | `passed` | `2026-08-16` |
| `python3 -m compileall -q src/services/intent_router.py src/services/temporal_understanding.py` | `passed` | `2026-08-16` |
| `git diff --check` | `passed` | `2026-08-16` |

Tests not run and reason: `mypy src/` chưa chạy vì mypy không được cài; PostgreSQL fixture mặc định không chạy được trong sandbox nên regression dùng SQLite tạm.

## Risk, rollback and follow-up

- Risks: từ “mai” được hiểu là ngày kế tiếp trong câu hỏi lịch trình; các câu không mang ngữ cảnh công việc không bị mở rộng ngoài router agenda.
- Rollback: revert các file trong change record về base SHA nếu cần.
- Follow-up: xử lý riêng test reminder đang phụ thuộc cách SQLite lưu timezone nếu cần làm xanh toàn bộ suite.

## Merge and deployment

- Merge status: chưa merge.
- Environment / deployed SHA or artifact: chưa deploy.
- Health/log evidence: không áp dụng.
- Previous known-good / rollback verification: chưa chạy.

### Deployment notification

| Item | Value |
| --- | --- |
| Batch / date | `not scheduled` / `2026-08-16` |
| User-visible update | Không còn rơi câu hỏi “mai phải làm gì” vào phản hồi ngoài phạm vi | 
| Scope | `backend router` |
| Source | `working tree based on cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Validation | `15 targeted passed; full suite 1032 passed, 6 skipped, 1 unrelated failure` |
| Status | `Integrated` |
| Rollback | `revert change files to base SHA` |
