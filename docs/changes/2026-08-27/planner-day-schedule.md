# Lịch trong ngày theo giờ và sức người

## Objective

Thêm scheduler xác định dùng nhịp ngày cấu hình được, bắt đầu từ thời điểm hiện
tại, tôn trọng deep/shallow và công khai việc dời sang ngày mai; ghép kết quả
vào response `task_breakdown` mà không thay phần LLM tách bước.

## Research sources

- `BRIEF.md`, `AGENTS.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`
- `docs/projects/product/prd.md`
- `docs/projects/engineering/adr/adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md`
- `src/services/task_breakdown.py`, `src/services/planner/{score,estimate}.py`
- `src/models/{task,schemas}.py`, `src/config.py`, `src/api/tasks.py`

## Scope and ownership

- Lead Codex là writer duy nhất của production code và integration.
- Antigravity thiết kế test matrix, chỉ được viết dưới `tests/**`, rồi review và
  chạy validation độc lập trên exact candidate.
- Không sửa `score.py`, `estimate.py`, `priority_rank`, UI, trash hay cancel.

## Base and head

- Branch: `feat/planner-day-schedule`
- Base/HEAD trước thay đổi: `69278d3025554eafc00cfeb03f2b1fd78b21d4b2`
- Theo BRIEF: chưa commit; head Git dự kiến giữ nguyên, diff nằm trong worktree.

## Acceptance and verification plan

- Không xếp vào quá khứ/khung nghỉ; deep không vào buổi tối; block không chồng
  lấn và `end - start` khớp `minutes`.
- Quá tải và lúc 23:00 dời toàn bộ sang mai; buổi tối chỉ nhắc nghỉ khi thật sự
  có block; estimate thiếu dùng neutral fallback và ghi rõ confidence.
- Baseline và after-run dùng cùng Python/worktree; so tập test fail, chạy targeted,
  full pytest và Ruff trên `src/ tests/`.

## Results, risks and rollout

- Đang thực hiện; sẽ cập nhật command/result thật, diff review và skipped checks.
- Rủi ro: response API mở rộng và quy đổi timezone; không đổi schema/migration.
- Merge/deploy: không commit, không merge, không push, không deploy theo BRIEF.
- Rollback: bỏ diff scheduler/config/schema-response/integration/tests; không có
  data rollback.

| Item | Value |
| --- | --- |
| Batch / date | `planner-day-schedule` / 2026-08-27 |
| User-visible update | Lịch hôm nay theo giờ, sức người và phần dời sang mai |
| Scope | backend API |
| Source | worktree diff từ `69278d3025554eafc00cfeb03f2b1fd78b21d4b2` |
| Validation | đang chạy |
| Status | Planned |
| Rollback | bỏ worktree diff, không có data migration |
