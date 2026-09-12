# WHAT_CHANGED — Lưu lịch sử task đã hoàn thành 7 ngày

| Field | Value |
| --- | --- |
| Task ID | completed-task-retention |
| Record schema | v2 |
| Status | Integrated |
| Date | 2026-08-24 |
| Lead | Tatejo/Codex |
| Agents / lanes | Codex — production code and validation |
| Base SHA | 3df0d2c |
| Head / merge SHA | 11b9921 |

## Intent and acceptance criteria

- Khi bấm “Đã làm”, task rời nhóm đang chờ và xuất hiện ở cuối dưới mục “Đã làm trong tuần này”.
- Task hoàn tất được giữ 7 ngày để chat/tool có thể tổng kết việc đã làm; quá hạn thì task và evidence bị xoá.
- Tool `list_tasks` đọc được `status=completed` và lọc khoảng thời gian theo thời điểm hoàn tất.

## Changes

- Thêm `completed_at` và migration runtime cho bảng `tasks`.
- Thêm retention service xoá task completed quá 7 ngày cùng `task_evidence`.
- UI tách nhóm completed khỏi inbox active nhưng vẫn hiển thị trong archive tuần.

## Validation evidence

| Command | Result |
| --- | --- |
| `./.venv/bin/pytest -q tests/test_api/v1/test_tasks.py tests/test_agents/v1/test_task_tool.py` | 48 passed |
| `npm run build` tại `client/web-app` | pass; `tsc -b` và Vite build pass |
| `git diff --check` | pass |

Tests not run: independent Antigravity review chưa chạy trong pass tiết kiệm quota hiện tại.

## Risk, rollback and follow-up

- Risk: purge hiện là lazy, chạy khi API `/tasks` hoặc tool task được gọi; không có cron riêng.
- Rollback: revert commit này; migration column có thể giữ lại an toàn.

## Merge and deployment

- Merge status: chưa push/deploy.
- Environment / deployed SHA: none.
- Health/log evidence: not applicable.
