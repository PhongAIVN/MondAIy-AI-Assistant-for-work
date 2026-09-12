# WHAT_CHANGED — Nhận diện task từ Google Sheets

| Field | Value |
| --- | --- |
| Task ID | User request: Google Sheets OAuth/read-only và tạo task từ bảng team |
| Status | Integrated |
| Date | `2026-08-16` |
| Lead | Codex |
| Agents / lanes | Research: OAuth/connector/task-flow review; implementation: Sheets connector + API; validation: connector/API/frontend contract tests |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | working tree; not merged |
| PR / issue / ADR | ADR-002; PRD FR-060–069, FR-100–105 |

## Intent and acceptance criteria

- Intent: Đọc một Google Sheet quản lý công việc của team, nhận diện các dòng liên quan tới người dùng và trả về task proposal để người dùng xác nhận.
- Observable acceptance criteria:
  - Google login/connection xin thêm scope Sheets chỉ đọc.
  - Mapping được các cột tiếng Việt/Anh của template backlog, bao gồm tên việc, người phụ trách, hạn chót và trạng thái.
  - Ngày/giờ thiếu múi giờ được hiểu theo `Asia/Ho_Chi_Minh`.
  - Tên khớp người dùng được nhận diện; tên không rõ trả về câu hỏi xác nhận, không tự gán.
  - Không ghi ngược vào Sheet và không tự chuyển task thành `confirmed`.
- Non-goals: Không dùng Drive write scope; không chỉnh sửa Sheet; không tự suy diễn tên người; không thêm event Calendar.

## Changes

- Observable behavior: Google OAuth dùng thêm `spreadsheets.readonly`; người dùng nhập URL + tên tab, hệ thống trả proposal task và câu hỏi khi assignee không khớp tên hiển thị.
- Components/files: `src/connectors/google_sheets.py`, `src/api/google_sheets.py`, schemas/config, `client/web-app/src/components/sources/GoogleSheetsTaskImporter.tsx`, client API và tests.
- Config/migration/API compatibility: Không migration; API mới `POST /api/v1/google-sheets/task-proposals`; không ghi ngược Sheet.

## Agent handoffs and integration

- Ownership boundaries: Backend connector/API and tests; frontend task-box client/component; no overlapping writer per file.
- Integration order/conflicts: OAuth scope/config → connector/schema/API → frontend box → tests/review.
- Independent review: Đã review diff các file mới; không chạm dữ liệu fixture gốc hoặc secret. Các thay đổi sẵn có khác trong working tree được giữ nguyên.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `pytest -q tests/test_connectors/test_google_sheets.py tests/test_connectors/test_calendar.py` | pass — 11 passed | `2026-08-16` |
| `pytest -q tests/test_api/test_google_sheets.py` | pass — 2 passed | `2026-08-16` |
| `npm test -- --run GoogleSheetsTaskImporter.test.tsx` | pass — 1 Vitest test; existing Node suite 103 passed | `2026-08-16` |
| `ruff check ...` (changed backend files) | pass — All checks passed | `2026-08-16` |
| `python3 -m compileall -q src/api/google_sheets.py src/connectors/google_sheets.py` | pass | `2026-08-16` |
| `git diff --check` | pass | `2026-08-16` |

Tests not run and reason: `npm run build` chưa pass do ba lỗi TypeScript tồn tại sẵn ở `src/lib/meetingDisplay.ts`, `src/lib/meetingNotesApi.ts` về extension `.js`; `npm run lint` chạy được với 5 warning cũ, không warning mới. Chưa chạy live Google API với credential thật.

## Risk, rollback and follow-up

- Risks: Sheet có thể dùng tên cột tự do; dòng không rõ người phụ trách phải giữ ở trạng thái cần xác nhận. Scope OAuth mới yêu cầu người dùng cấp lại consent. Tên người khác trong team cũng hiện thành cần xác nhận vì chưa có roster mapping.
- Rollback: Revert code/config change; không có migration dự kiến.
- Follow-up: Nếu cần tự động hỏi qua hội thoại nhiều lượt, nối clarification với conversation state sau khi API proposal ổn định.

## Merge and deployment

| Item | Value |
| --- | --- |
| Batch / date | `google-sheets-task-import` / `2026-08-16` |
| User-visible update | Đọc Sheet và trả task proposal có xác nhận người dùng |
| Scope | backend + web app; no deploy |
| Source | not merged |
| Validation | Pending |
| Status | Integrated |
| Rollback | Revert change commit |

- Merge status: Đã tích hợp vào working tree; chưa commit/merge/push/deploy.
- Environment / deployed SHA or artifact: None.
- Health/log evidence: None.
- Previous known-good / rollback verification: Base SHA ở trên.
