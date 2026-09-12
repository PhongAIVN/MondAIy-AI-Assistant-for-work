# Discord connector — kết quả spike đọc raw message

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Done — chờ quyết định về phạm vi truy cập |
| Owner | Thái Hoài An (PM) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-05 |
| Jira | TAPB-122 |
| Related | [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [ADR-003](adr/adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · [Architecture](architecture.md) |

## Câu hỏi cần trả lời

TAPB-122 yêu cầu Discord trả ra raw message đúng shape. Trước khi viết bước
normalize phải biết: lấy được những trường nào, bằng quyền gì, và thiếu gì.

## Kết luận

**OAuth2 không đọc được nội dung kênh.** Scope `messages.read` chỉ chạy qua RPC
cục bộ trên Discord client và cần Discord duyệt riêng; không có scope OAuth2 nào
cho phép web app đọc tin nhắn. Vòng OAuth hiện có trong
`src/services/connections/discord.py` vẫn đúng cho mục đích nhận diện người dùng,
nhưng không mở rộng sang đọc dữ liệu được.

**Đọc raw message bắt buộc dùng bot token.** Bot phải ở trong server, có quyền
View Channel + Read Message History, và bật Message Content Intent. Thiếu intent
thì API vẫn trả 200 nhưng trường `content` rỗng.

**Không dùng lại đường của DiscordChatExporter.** Tool đó chạy bằng user token.
Discord siết mạnh từ tháng 03/2026, tài khoản dùng bị đăng xuất hàng loạt. Dataset
cào sẵn vẫn dùng được, nhưng cách cào ra nó thì không lặp lại.

## Đã làm

| Việc | Nơi |
| --- | --- |
| Kéo raw message từ Discord API, có phân trang và chờ khi bị rate limit | `scripts/discord_fetch_raw.py` |
| Dựng raw message đúng shape từ xlsx của DiscordChatExporter, dùng khi chưa có token | `scripts/xlsx_to_discord_raw.py` |
| 15 test, không cần token và không cần mạng | `tests/test_scripts/` |
| Bot token, redirect URI, intent, biến môi trường | `.env.example` |

Hai script cho ra cùng một shape nên bước normalize phía sau không cần biết dữ
liệu tới từ đâu.

## Kiểm chứng trên môi trường thật

Chạy ngày 2026-08-05 với app `Mondaiy` trên server `T004-Demo`:

| Điểm kiểm | Kết quả |
| --- | --- |
| Bot token hợp lệ | Đạt |
| Bot thấy được kênh trong server | Đạt, 6 kênh |
| `GET /channels/{id}/messages` | Đạt |
| `guild_id` lấy được để dựng deep link | Đạt |
| Nội dung thật với reply, ảnh, reaction | Chưa — kênh mẫu mới chỉ có tin hệ thống |

## Trường lấy được

Payload giữ nguyên như Discord trả, không đụng vào nội dung:

| Trường | Dùng để |
| --- | --- |
| `id`, `channel_id`, `channel.guild_id` | deep link và chống trùng |
| `timestamp`, `edited_timestamp` | ISO 8601 kèm múi giờ |
| `author.{id,username,global_name,bot}` | loại tin của bot khỏi pipeline |
| `referenced_message`, `message_reference`, `thread` | nối reply và thread |
| `attachments`, `embeds`, `reactions`, `mentions` | giữ nguyên cấu trúc |
| `type`, `pinned`, `flags` | loại tin hệ thống như tham gia server hay ghim tin |

Đủ cho yêu cầu của [ADR-002](adr/adr-002-connector-first-p0-scope.md) mục 4 về mã
nguồn, deep link và thời điểm cập nhật.

## Dataset xlsx thiếu gì so với API

Ba file trong `Week 1/5. Mini-Hackathon/Dataset` chỉ có sáu cột. Đã chuyển được
6.373 tin sang shape Discord, nhưng phải biết bốn giới hạn sau trước khi tin số
liệu rút ra từ chúng:

- **Không có `message_id`.** Script sinh snowflake từ mốc thời gian để giữ đúng
  thứ tự, nhưng đây là id giả, không đối chiếu được với Discord.
- **`AuthorID` đã hỏng.** Excel lưu thành số thực nên mất chữ số cuối. Script
  sinh id giả ổn định theo tên; chống trùng theo người vẫn chạy.
- **`Crawl_QA_Discord` trải chín kênh hoặc thread.** Chỉ tin có ảnh đính kèm mới
  suy ra được kênh của nó, phần còn lại bị gán kênh hay gặp nhất. Đây là suy
  đoán, script in cảnh báo và ghi lại danh sách kênh đã thấy.
- **Mất hẳn `referenced_message`, `thread`, `embeds`, `mentions`.** Chỉ bot token
  mới lấy được.

Kết luận: dataset xlsx dùng để thử bước lọc và bước rút trích thì được, làm bằng
chứng nghiệm thu cho connector thì không.

## Quyết định còn treo

Bot đọc được **toàn bộ kênh** mà nó nhìn thấy, không giới hạn ở dữ liệu của
người dùng đã bấm kết nối. Đây rộng hơn ranh giới mà
[ADR-002](adr/adr-002-connector-first-p0-scope.md) mục 1 mô tả, nên là material
change về riêng tư và cần một ADR mới trước khi lên production.

Ba câu cần chốt trong ADR đó:

1. Bot được vào những server và kênh nào, ai duyệt việc mời bot.
2. Tin của thành viên chưa kết nối tài khoản mondaiy có được xử lý không, hay bị
   loại ngay ở bước thu thập.
3. Lưu giữ bao lâu, và xoá thế nào khi có người rút lại đồng ý.

Spike và fixture thì không vướng, vẫn chạy tiếp được trong lúc chờ.

## Việc tiếp theo

| Việc | DRI |
| --- | --- |
| Bơm nội dung thật vào kênh mẫu rồi kéo lại, đủ ca reply, ảnh, reaction, tin đã sửa | An |
| Viết ADR-004 về phạm vi truy cập của bot | An, duyệt bởi Phong và Dũng |
| Cắm raw message vào bước normalize chung với Gmail (TAPB-130) | An |
| Đưa `DISCORD_BOT_TOKEN` vào `src/config.py` khi script chuyển thành service | Phong |
