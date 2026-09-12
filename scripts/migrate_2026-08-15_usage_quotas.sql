-- Hạn mức tóm tắt meeting và cửa sổ feedback.
-- Môi trường mới được create_all dựng; database đã tồn tại cần chạy file này
-- hoặc để ensure_runtime_schema() thêm cột khi ứng dụng khởi động.
ALTER TABLE users ADD COLUMN IF NOT EXISTS meeting_summary_quota_day VARCHAR(10);
ALTER TABLE users ADD COLUMN IF NOT EXISTS meeting_summaries_used INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS feedback_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS feedback_cooldown_until TIMESTAMPTZ;
