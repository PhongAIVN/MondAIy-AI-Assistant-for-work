# Streaming agent — production closeout

Ngày xác nhận: 2026-08-11 (Asia/Ho_Chi_Minh)

## Trạng thái

Task streaming đã hoàn tất và đang chạy production.

- Backend/worker VM: image `p004-backend:6ac1024`, Linux/AMD64.
- Backend commit: `6ac1024` (kế thừa `0eadf01`, `c7db46a` và `1edb326`).
- Frontend: Vercel project `c3-app-004`, canonical URL `https://www.c3-app-004.io.vn/`.
- Model production: `gpt-4o-mini`, provider `openai`.
- Caddy dùng chung không bị sửa; SSE trả `Cache-Control: no-cache, no-transform` để tránh proxy encode buffer.

## Hành vi đã xác nhận

Frontend nhận SSE semantic progress và token thật theo luồng:

`thinking → calling → observing → responding → done`

UI hiển thị tên tool thân thiện (Calendar, Gmail, nguồn dữ liệu...) và nối token vào câu trả lời theo thời gian thực. Planning/day-summary không còn đi qua mock shortcut.

## Kiểm thử

- Backend snapshot sạch: `383 passed, 2 skipped`.
- VM focused regression: `36 passed` trên database tạm với `vector`, `unaccent`, `pg_trgm`; database tạm được drop sau test.
- Frontend: 43 tests pass, lint pass (chỉ warning cũ), typecheck/build pass.
- Production E2E với tài khoản test: byte đầu SSE `0.216813s`, 461 token events, `done=1`, `error=0`, Calendar tool được gọi và quan sát, health `8/8` trong lúc stream.
- Frontend canonical và bundle: HTTP 200; activity labels hiện diện.
- Calendar timed events are displayed in `APP_TIMEZONE` (`Asia/Ho_Chi_Minh` in production); UTC is retained internally for ordering and filtering. This prevents mixed `UTC`/`UTC+7` labels when Google Calendar returns different event offsets.

### Calendar timezone regression

- Calendar connector tests on the clean production snapshot: `4 passed`.
- Production E2E query `lịch của tôi hôm nay`: phases included `calling:calendar_search_events` and `observing:calendar_search_events`; `456` token events, `done=1`, `error=0`; displayed times were `09:00–13:00`, `14:00–18:00`, `19:00–21:00`.

## Rollback

Trên VM, backup cấu hình cuối là:

`/opt/p-004/.env.bak-2026-08-11-streaming-0eadf01`

Rollback: khôi phục file backup vào `/opt/p-004/.env`, chạy `docker compose -f docker-compose.prod.yml --env-file .env config -q`, rồi recreate `p004-backend` và `worker` theo runbook GreenFlow.

Các archive image trong `/opt/p-004/` được giữ lại để rollback/audit; chỉ xóa sau khi có quyết định vận hành riêng.

## Tồn đọng / lưu ý

- Chưa chạy browser automation trực tiếp; E2E API + kiểm tra bundle đã xác nhận contract streaming. Nên thực hiện một smoke test trình duyệt thủ công sau lần release UI kế tiếp.
- Cấu hình Caddy thuộc stack dùng chung và không được chỉnh trong task này; `no-transform` là biện pháp per-response hiện tại.
- Các thay đổi avatar/calendar khác đang có trong worktree nhưng không thuộc commit streaming/timezone và không được đưa vào image production này.
