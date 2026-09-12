# ADR-012 — Telegram P0 cho tóm tắt và nhắc việc

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved for P0 pilot |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) + Codex |
| Reviewers | UI/UX Lead, PO/QC, Privacy/Security DRI |
| Last updated | 2026-08-13 |
| Related | [Mobile chat spike](../mobile-chat-channel-spike.md) · [Telegram command center proposal](../../drafts/telegram-mobile-command-center-plan.md) · [PRD](../../product/prd.md) · [ADR-002](adr-002-connector-first-p0-scope.md) · [ADR-004](adr-004-lien-ket-danh-tinh-qua-discord-oauth.md) · [ADR-007](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) |

## Bối cảnh

mondaiy đã sinh được daily brief, task reminder, task proposal và cảnh báo mâu
thuẫn, nhưng cơ chế giao P0 trong ADR-007 dựa vào extension và chỉ hoạt động khi
trình duyệt chạy. Điều này không đáp ứng mục tiêu người dùng theo dõi tiến độ
và nhận nhắc việc khi không mở laptop.

Spike mobile chat kết luận Telegram Bot phù hợp nhất cho pilot 5–10 người vì
cho phép push sau khi user đồng ý, hỗ trợ deep link và không cần xây native app.
PM đã chấp thuận làm lát cắt đầu tiên gồm **tóm tắt và nhắc việc**. Giao việc,
Gmail triage, lịch tương tác, cơ hội, tin tức và Mini App chưa thuộc quyết định
này.

## Quyết định

### 1. Telegram là kênh, không phải nguồn dữ liệu

Bot chỉ trình bày dữ liệu đã đi qua Evidence, Task, Brief và Reminder hiện có.
Bot không đọc group/private chat Telegram để trích xuất task và không tìm news
trên Internet. Thêm Telegram không thay danh sách connector nguồn của ADR-002.

### 2. Liên kết danh tính bằng Telegram Login Widget đã ký

Giữ Login Widget với `request_access=write`. Server xác minh chữ ký và thời gian
`auth_date`, sau đó lưu Telegram numeric user ID vào
`Connection.provider_user_id`. Trong private chat, ID này là đích `chat_id` để
gửi tin.

Webhook chỉ map update sang user qua `provider=telegram` và
`provider_user_id`. User chưa liên kết chỉ nhận hướng dẫn kết nối, không nhận
bất kỳ brief, task, reminder hay evidence nội bộ nào. Không cho liên kết bằng
mã học viên hoặc lời tự khai trong chat.

### 3. Webhook xác minh secret và xử lý tối thiểu

Endpoint `POST /api/v1/channels/telegram/webhook` bắt buộc kiểm header
`X-Telegram-Bot-Api-Secret-Token` bằng so sánh constant-time. P0 hỗ trợ:

- `/start`: xác nhận trạng thái liên kết hoặc hướng dẫn mở web app để kết nối;
- `/today`: dựng tóm tắt hiện tại từ task của đúng user và gửi lại trong chat;
- nội dung khác: trả danh sách lệnh được hỗ trợ, không đưa vào agent/LLM.

P0 không lưu raw Telegram message. Telegram retry cùng `update_id` phải được
dedupe bền vững.

### 4. Push dùng outbox reminder hiện có, receipt tách theo kênh

Worker quét user đã liên kết Telegram, lấy bundle từ cùng reminder service đang
áp quiet hours, batching, hourly cap, priority và evidence guard. Chỉ ghi receipt
sau khi Bot API trả thành công.

Receipt Telegram nằm trong bảng `channel_notification_deliveries`, khóa unique
theo `(channel, reminder_id)`. Không dùng chung receipt với extension: một kênh
giao thành công không được làm kênh kia mất lượt giao. Retry worker không gửi
trùng reminder đã có receipt trên cùng kênh.

### 5. Tóm tắt và reminder dùng plain text có giới hạn

Presenter dựng plain text, không dùng raw HTML/Markdown từ nguồn. Daily brief
hiển thị số task sắp hạn, tối đa năm tiêu đề và số task đang chờ xác nhận.
Reminder hiển thị loại, tiêu đề, hạn và link evidence nếu link đã qua guard hiện
có. Tin dài được cắt theo giới hạn Telegram trước khi gửi.

P0 chưa có callback `Đã làm`, `Nhắc lại`, `Bỏ qua`; các external write này sẽ
được quyết định ở lát cắt sau cùng preview/ownership/idempotency test.

### 6. Opt-in và rollback

- Daily brief vẫn mặc định tắt và dùng `NotificationPreference.daily_brief_hour`.
- Telegram delivery có feature flag toàn hệ thống, mặc định tắt.
- Unlink Telegram dừng push mới ngay lập tức.
- Khi Bot API lỗi/429/timeout, không ghi receipt; worker thử lại ở vòng sau và
  không làm crash các loop khác.
- Rollback bằng cách tắt feature flag; dữ liệu receipt được giữ làm audit kỹ
  thuật và không chứa nội dung tin nhắn.
- Sau deploy, vận hành chạy `python3 scripts/setup_telegram_webhook.py`; script
  chỉ chấp nhận `APP_PUBLIC_URL` HTTPS và đăng ký đúng update loại `message`.

## Phương án đã cân nhắc

| Phương án | Kết luận |
| --- | --- |
| Telegram tự polling endpoint `/reminders/due` như extension | Loại: Telegram cần server push và không có service worker phía user |
| Dùng chung `notification_deliveries` với extension | Loại: kênh giao trước sẽ chặn kênh còn lại |
| Gọi conversation agent cho mọi message | Hoãn: tăng latency/cost và mở rộng scope trước khi chứng minh giá trị read/push |
| Bot đọc group Telegram làm nguồn task | Loại khỏi ADR này: là connector mới và privacy boundary mới |
| Mini App ngay từ đầu | Hoãn: tóm tắt/reminder plain text đủ kiểm chứng hành vi đầu tiên |

## Hệ quả

- User có thể nhận brief và reminder khi không mở trình duyệt.
- Lõi reminder, priority, quiet hours và evidence guard chỉ có một nơi triển
  khai; Telegram là adapter/delivery mới.
- `Connection.provider_user_id` trở thành trường bắt buộc cho Telegram push;
  kết nối Telegram cũ thiếu ID phải liên kết lại.
- Thêm một outbound dependency và loop nền; cần quan sát lỗi theo error class,
  không log token, chat text hoặc response body chứa dữ liệu người dùng.
- Telegram là hạ tầng bên thứ ba nhận nội dung tóm lược; consent copy phải nói
  rõ trước khi bật.

## Acceptance và evidence

1. Webhook sai/mất secret bị từ chối.
2. Telegram ID chưa liên kết đọc được 0 dữ liệu nội bộ.
3. User A không nhận brief/reminder/evidence của user B.
4. Cùng update hoặc reminder retry không tạo side effect trùng.
5. Receipt chỉ được ghi sau send thành công; lỗi không làm worker crash.
6. Daily brief opt-out, quiet hours, batching và cap vẫn có hiệu lực.
7. Analytics/log không chứa raw Telegram message, task title, email content hay
   bot token.
8. Pilot báo số `x/n` user có hành động mobile có chủ đích; không suy diễn read
   receipt từ `sendMessage` thành “đã đọc”.

## Việc tiếp theo ngoài ADR

- Callback hoàn thành/snooze/dismiss.
- Giao việc bằng hội thoại và action preview.
- Gmail/lịch, cơ hội, tin tức và Mini App.
- Adapter đa kênh hoặc Zalo chỉ được mở bằng decision mới sau pilot.
