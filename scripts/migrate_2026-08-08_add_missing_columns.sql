-- Vá schema trôi ngày 2026-08-08.
--
-- Nguyên nhân: src/main.py gọi Base.metadata.create_all() lúc khởi động. Lệnh
-- đó tạo bảng còn thiếu nhưng không bao giờ sửa bảng đã tồn tại, nên khi model
-- thêm cột thì bảng cũ giữ nguyên hình dạng. Hậu quả là /api/v1/auth/register
-- và /login trả 500 với lỗi "column users.last_synced_at does not exist".
--
-- Không dùng cách tạo lại database: DB dev đang giữ dữ liệu Discord thật và
-- tài khoản người dùng đã đăng ký.
--
-- Script idempotent, chạy lại nhiều lần không sao. Áp cho cả DB dev lẫn DB trên
-- VM, vì cả hai cùng đi qua create_all nên cùng lệch.
--
--   docker exec -i p-004-db-1 psql -U app -d ai20k -v ON_ERROR_STOP=1 \
--     < scripts/migrate_2026-08-08_add_missing_columns.sql
--
-- Lưu ý: docker exec phải có cờ -i, thiếu thì stdin không vào tới psql và
-- script im lặng không chạy gì cả.

BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;

ALTER TABLE connections ADD COLUMN IF NOT EXISTS provider_user_id VARCHAR(128);
ALTER TABLE connections ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS last_error VARCHAR(1024);

-- Ba cột dưới đây model khai là NOT NULL. DEFAULT chỉ để lấp giá trị cho dòng
-- đã có sẵn, xong thì bỏ đi cho khớp model — model dùng default phía Python
-- chứ không dùng server_default.
ALTER TABLE connections
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'connected_pending_sync';
ALTER TABLE connections
    ADD COLUMN IF NOT EXISTS initial_sync_completed BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE connections
    ADD COLUMN IF NOT EXISTS email_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE connections ALTER COLUMN status DROP DEFAULT;
ALTER TABLE connections ALTER COLUMN initial_sync_completed DROP DEFAULT;
ALTER TABLE connections ALTER COLUMN email_count DROP DEFAULT;

COMMIT;
