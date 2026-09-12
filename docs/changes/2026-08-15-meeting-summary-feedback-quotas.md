# WHAT_CHANGED — Meeting summary và feedback quotas

| Field | Value |
| --- | --- |
| Task ID | `meeting-summary-feedback-quotas` |
| Status | Integrated into `main`, pushed and deployed |
| Date | `2026-08-15` |
| Lead / lane | `/root`; `quota_change_review` read-only review |
| Base SHA | `cb99196fd6d8adce2700d7b8ef94fcc5d3e35598` |
| Head SHA | `f90cd5a` |

## Mục tiêu và hành vi observable

- User thường chỉ được reserve một lượt tóm tắt meeting mỗi ngày; lượt thứ hai trả HTTP 429 và hướng dẫn liên hệ đội ngũ phát triển.
- Admin không bị quota tóm tắt meeting.
- Feedback được đánh giá tối đa năm lần mỗi cửa sổ; sau lần thứ năm endpoint trả HTTP 429 trong năm phút trước khi cho thử lại.
- Ngưỡng feedback giảm từ 41 xuống 20 ký tự; prompt đánh giá chấp nhận phản hồi ngắn/genuine hơn.

## File chính và migration

- `src/models/user.py`, `src/services/usage_quota.py`
- `src/api/meeting_notes.py`, `src/api/ratings.py`, `src/services/feedback_quality.py`
- `src/db.py`
- `scripts/migrate_2026-08-15_usage_quotas.sql`
- Tests: `tests/test_api/v1/test_meeting_notes.py`, `tests/test_api/v1/test_ratings.py`, `tests/v1/test_db_runtime_schema.py`

## Validation evidence

| Command | Kết quả |
| --- | --- |
| `python3 -m compileall -q src tests` | pass |
| `ruff check ...` trên các file backend/test thay đổi | pass |
| `git diff --check` | pass |
| `APP_SECRET_KEY=test-secret DATABASE_URL=sqlite:////tmp/p004-main-ratings-test.db APP_ENV=test pytest -q tests/test_api/v1/test_ratings.py` | pass — 4 tests |
| `APP_SECRET_KEY=test-secret DATABASE_URL=sqlite:////tmp/p004-main-quota-api.db APP_ENV=test pytest -q tests/test_api/v1/test_meeting_notes.py tests/test_api/v1/test_meeting_notes_audio.py` | pass — 28 tests |
| `APP_SECRET_KEY=test-secret DATABASE_URL=sqlite:////tmp/p004-main-quota-test-2.db APP_ENV=test pytest -q tests/v1/test_db_runtime_schema.py` | pass — 5 tests |
| `ruff check ...` + `python3 -m compileall -q src tests` + `git diff --check` | pass |

## Risk, rollback, follow-up

- Quota summary được reserve trước khi gọi LLM; lỗi provider vẫn tiêu thụ lượt trong ngày để tránh retry lặp làm phát sinh chi phí.
- Database cũ cần chạy SQL migration hoặc để `ensure_runtime_schema()` thêm cột khi khởi động.
- Merge: cherry-pick `cec16e4` onto `origin/main`, resolved main's test-path/schema conflicts; final commits `82075a0`, `f90cd5a`.
- Deploy: `deploy_vm_local.sh` dry-run passed; production deployed `f90cd5a` via rsync/build, recreating only `p004-backend` and `worker`.
- Health evidence: backend container healthy; `https://p004-api.duckdns.org/health` returned `{"status":"ok","env":"production"}`.
- Rollback: image rollback tag is created by the deploy script as `rollback-f90cd5a`; rerun the canonical deploy script with the prior known-good source if needed.
