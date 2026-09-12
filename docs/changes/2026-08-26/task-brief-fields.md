# Task brief fields

- Objective: giữ 9 trường task brief đã trích qua API thay vì làm bẹp vào `detail`.
- Sources: ADR-018, ADR-019, `Task`, schemas và endpoint `/tasks/from-suggestion`.
- Scope: migration `9a42dcf7b631`, model, request/response API và test; không sửa frontend/extension, planner, `actual_minutes` hay runtime schema.
- Base/head: `253640b` / worktree chưa commit.
- Observable behavior: POST nhận và đọc lại đủ 9 trường; task cũ với các cột `NULL` vẫn đọc được; migration upgrade thêm cột và downgrade xoá chúng.
- Checks: `pytest tests/test_alembic/test_migrations.py -q` → 4 passed; targeted API tests → 2 passed; Ruff và `git diff --check` → passed. Full `pytest tests/ -q --tb=no` → 2352 passed, 301 failed, 7 skipped; baseline được giao là 2355 passed, 301 failed, 2 skipped. Hai test mới không nằm trong tập fail; chênh 5 pass/skip không thuộc diff này.
- Risk: round-trip migration được kiểm chứng trên SQLite; revision viết bằng Alembic `add_column`/`batch_alter_table` tương thích Postgres nhưng chưa chạy lên PostgreSQL thật. Không migration/deploy.
- Rollback: `alembic downgrade 5c3a646a710f` xoá đúng 9 cột mới.
