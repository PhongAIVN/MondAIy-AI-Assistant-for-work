-- Thêm `extras` và `feedback` vào conversation_messages.
--
-- Môi trường mới không cần chạy file này: bảng chưa tồn tại thì create_all dựng
-- luôn bản đủ cột. Chỉ những máy đã chạy app trong khoảng giữa hai lần đổi model
-- mới có bảng thiếu cột — create_all không sửa bảng đã có.
--
--   docker exec -i p-004-db-1 psql -U app -d ai20k -v ON_ERROR_STOP=1 \
--     < scripts/migrate_2026-08-08b_conversation_extras.sql

BEGIN;

-- extras giữ nguyên khối các trường có cấu trúc của một câu trả lời có căn cứ
-- (tóm lược, bằng chứng, mức tin cậy) do đường Gmail briefing dựng ra.
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS extras JSON;

-- feedback: helpful | partly | incorrect (FR-035).
ALTER TABLE conversation_messages ADD COLUMN IF NOT EXISTS feedback VARCHAR(16);

COMMIT;
