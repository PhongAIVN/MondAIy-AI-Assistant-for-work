# Spike — Luồng mobile-first qua kênh chatbot (Telegram, Discord, Zalo)

| Thuộc tính | Giá trị |
| --- | --- |
| Loại | Spike nghiên cứu, **chưa phải quyết định** |
| Author | Thái Hoài An (PM) + Claude |
| Last updated | 2026-08-13 |
| Trạng thái | Cần ADR trước khi build — đây là material change |
| Related | [ADR-002](adr/adr-002-connector-first-p0-scope.md) · [ADR-004](adr/adr-004-lien-ket-danh-tinh-qua-discord-oauth.md) · [ADR-007](adr/adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [PRD](../product/prd.md) · [One-page brief](../product/one-page-brief.md) |

## Câu hỏi

Mở thêm một bề mặt mobile-first, tiếp cận bằng chatbot (Telegram, Discord, Zalo…)
thay vì bắt học viên mở web app. Nền tảng nào, đánh đổi gì, tốn bao nhiêu?

## Kết luận ngắn

1. **Telegram Bot + Mini App là lựa chọn kỹ thuật tốt nhất cho pilot.** Nó là nền
   tảng duy nhất trong nhóm khảo sát cho phép **chủ động nhắn tin miễn phí, không
   giới hạn cửa sổ thời gian** — điều kiện sống còn cho bản tóm lược hằng ngày
   (UC-01/02) và lớp nhắc việc (ADR-007). Mini App giải được phần UI mà chat
   không làm nổi: preview `.ics`, đặt hai nguồn mâu thuẫn cạnh nhau (UC-03),
   duyệt draft (UC-05).
2. **Zalo OA phủ thị trường tốt nhất (98% người Việt) nhưng đắt và bị bó cửa sổ
   48 giờ.** Đúng cho giai đoạn phát hành rộng, sai cho pilot 5–10 người.
3. **Discord DM là đường rẻ nhất về mặt onboarding** (học viên đã ở sẵn trong
   server, ADR-004 đã dùng Discord OAuth) **nhưng là kênh đẩy không đáng tin**:
   bot chỉ DM được nếu chung server và người dùng chưa tắt DM.
4. **Chọn kênh nào cũng là material change**, và không được lẫn giữa *kênh giao
   tiếp* với *nguồn dữ liệu* trong ADR-002. Mục "Ranh giới tài liệu" bên dưới.

## Cái đã có, dùng lại được bao nhiêu

Bề mặt chat mới **không** phải xây lại lõi. Lõi đã nằm sẵn ở:

| Có sẵn | Vai trò với kênh mới |
| --- | --- |
| `src/api/conversations.py` (1058 dòng) | Vòng đời hội thoại, dùng nguyên |
| `src/services/agent_stream.py` | Streaming câu trả lời, cần bọc lại vì chat không stream token được |
| `src/agents/graph.py` + `nodes/` + `tools/` | Toàn bộ năng lực trả lời có dẫn nguồn |
| `src/services/scope.py`, `retrieval.py` | Phân quyền theo user — **bắt buộc đi qua**, không được bỏ qua vì là bot |
| `src/services/reminders.py` | Nội dung để đẩy |
| `src/services/connections/telegram.py` (54 dòng) | Chỉ là Telegram Login Widget, **không phải bot** — không dùng lại được |

Phần phải viết mới thực chất là **một adapter**: webhook nhận update → map sang
`user_id` → gọi conversation core → render câu trả lời về định dạng của kênh.

## So sánh nền tảng

| Tiêu chí | Telegram | Discord | Zalo OA | Messenger |
| --- | --- | --- | --- | --- |
| Chủ động nhắn (push) | Không giới hạn, miễn phí, **sau khi user bấm Start** | Chỉ khi chung server + user bật DM | Cửa sổ 48h; ngoài cửa sổ 55đ/tin | Cửa sổ 24h; **đẩy tự động ngoài cửa sổ gần như bị đóng trong 2026** |
| Chi phí nền tảng | 0đ | 0đ | Gói có API/chatbot từ ~2.5tr/năm | 0đ (nhưng cần Business verify) |
| Phủ người dùng VN | Thấp–trung bình | Cao trong cohort (đã dùng) | 98% dân số, 96% nhóm <26 tuổi | 88% |
| UI giàu | **Mini App** — web app đầy đủ trong client | Components, Modal, Activities | Rất hạn chế | Hạn chế |
| Xác thực danh tính | initData ký HMAC, verify được | OAuth `identify` (đã có, ADR-004) | Zalo ID qua OA | PSID |
| Duyệt / phê duyệt | Không | Không | **Có**, OA phải verify + xét duyệt | Có, App Review |
| Effort ước lượng | 2–3 ngày cho bot text; +3–5 ngày Mini App | 1–2 ngày | 5–8 ngày (gồm thủ tục) | 4–6 ngày |

### Vì sao "cửa sổ thời gian" là tiêu chí quyết định

mondaiy về bản chất là sản phẩm **đẩy**: tóm lược hằng ngày, "cái gì vừa đổi",
nhắc hạn chót. Nếu kênh chỉ cho trả lời trong cửa sổ 24–48h sau khi người dùng
nhắn, thì đúng cái giá trị chính của sản phẩm lại là cái kênh không cho làm miễn
phí. Zalo tính 55đ/tin ngoài cửa sổ nghe rẻ, nhưng 10 người × 1 briefing/ngày ×
30 ngày = 16.500đ/tháng cho pilot — không phải vấn đề tiền, vấn đề là ở quy mô
lớp học vài trăm người thì nó thành dòng chi phí biến đổi phải theo dõi, còn
Telegram thì bằng không.

### Ghi chú kỹ thuật từng nền tảng

**Telegram.** Bot API 10.2 (14/07/2026) có rich message với block/media/biểu
thức toán, tin nhắn ephemeral chỉ một người thấy trong nhóm, và 10.1 (11/06/2026)
bổ sung rich formatted text phục vụ **streaming câu trả lời AI** — đúng thứ
`agent_stream.py` đang làm trên web. Mini App 2026 chạy full-screen, có
`DeviceStorage`/`SecureStorage`, và từ 20/07/2026 bắt buộc chặn gọi method từ
origin lạ (ảnh hưởng nếu định nhúng iframe). Ràng buộc lớn duy nhất: **bot không
nhắn trước được**, người dùng phải chủ động Start — nhưng đây là điều xảy ra một
lần, không phải cửa sổ trượt.

**Discord.** Global 50 req/s, per-route theo bucket qua header `X-RateLimit-Bucket`
— đủ thoải mái cho pilot. Rủi ro thật nằm ở DM: `50007` (user chặn app) và
`50278` (tắt DM / không chung server) trả về **cùng một câu lỗi**, phải phân biệt
thủ công. Nghĩa là không thể hứa "mọi học viên đều nhận được briefing".

**Zalo OA.** Bảng giá áp dụng 01/06/2026: Tiêu chuẩn ~1tr/năm (không có API),
**Tăng trưởng ~2.5tr/năm mới có Chatbot & API**, Toàn diện 6tr/năm. Tin tư vấn
ngoài cửa sổ 48h: 55đ/tin. ZNS (tin template) tính giá riêng. OA còn bị **xếp
hạng Tốt/Trung bình/Kém theo số lượt báo xấu**, và hạn mức tin phụ thuộc hạng —
tức là chất lượng nội dung đẩy ảnh hưởng trực tiếp tới hạn mức kỹ thuật.

**Messenger.** Loại, và lý do cụ thể hơn "có cửa sổ 24h": **các đường đẩy tự
động ngoài cửa sổ đã bị đóng gần hết trong chính năm 2026.**

Trong cửa sổ 24h thì thoải mái, kể cả nội dung quảng bá. Ra ngoài cửa sổ chỉ còn
bốn đường: message tag cho use case được duyệt, One-Time Notification, News
Messaging (chỉ dành cho nhà xuất bản tin tức đã đăng ký), và Sponsored Messages
(trả tiền). Vấn đề nằm ở chỗ đường phù hợp với mondaiy nhất đã chết:

| Thay đổi 2026 | Hệ quả với mondaiy |
| --- | --- |
| `CONFIRMED_EVENT_UPDATE`, `ACCOUNT_UPDATE`, `POST_PURCHASE_UPDATE` trả lỗi 100 từ **27/04/2026** | Mất đúng cái tag tự nhiên nhất cho "hạn chót vừa đổi", "sắp tới hạn" |
| Message tag cho Recurring Notifications bị bỏ toàn cầu từ **10/02/2026**, trừ AU/EU/JP/KR/UK | Việt Nam nằm trong nhóm bị bỏ |
| `HUMAN_AGENT` (7 ngày) vẫn sống | **Không dùng được** — Meta cấm tường minh dùng cho tin tự động/bot và có cơ chế phát hiện lạm dụng |

Còn lại One-Time Notification — mỗi token chỉ đẩy được **một** thông báo, người
dùng phải bấm đồng ý từng lần, nên không dựng nổi briefing hằng ngày — hoặc trả
tiền qua Marketing Messages / Sponsored Messages.

Nói cách khác, vòng lặp chính của mondaiy (đẩy tóm lược mỗi ngày, nhắc hạn tự
động) là đúng thứ Messenger năm 2026 đang cố chặn nếu không trả tiền. Không phải
đắt — là sai kiến trúc kênh.

**Chưa verify:** giá và tình trạng khả dụng của Marketing Messages trên
*Messenger* tại Việt Nam (khác WhatsApp — số liệu giá per-message trôi nổi trên
mạng phần lớn là của WhatsApp, đừng dẫn nhầm sang đây). Chỉ cần verify nếu có ai
muốn lật lại quyết định loại Messenger.

**WhatsApp.** Không liên quan ở thị trường VN, không research.

## Kiến trúc đề xuất (nếu chốt Telegram)

```text
Telegram update  →  POST /api/v1/channels/telegram/webhook
                      ↓  verify secret_token header
                    channel_identity_links: telegram_user_id → user_id
                      ↓  không map được → trả lời hướng dẫn liên kết, KHÔNG trả nội dung nội bộ
                    conversation core (đang dùng cho web)
                      ↓  scope.py lọc theo user_id thật
                    render: text ngắn + nút mở Mini App cho phần cần duyệt
```

Ba nguyên tắc không được phá:

1. **Không có đường tắt phân quyền.** Bot đi qua đúng `scope.py` như web. Một
   `telegram_user_id` chưa liên kết đọc được 0 bằng chứng nội bộ — kiểm bằng
   test, không bằng câu dặn trong prompt (đúng tinh thần ADR-004).
2. **Liên kết danh tính bằng nonce, không bằng lời tự khai.** Web app (đã đăng
   nhập, đã confirm Discord theo ADR-004) sinh deep link
   `t.me/<bot>?start=<nonce>`; nonce dùng một lần, hết hạn ngắn. Tuyệt đối không
   cho gõ mã học viên trong chat — đó chính là phương án ADR-004 đã loại.
3. **Mọi hành động ghi vẫn qua preview → sửa → xác nhận.** Chat rất dễ cám dỗ
   làm tắt ("ok tạo luôn"). Nút xác nhận nằm trong Mini App hoặc inline keyboard,
   và bản draft vẫn là bản draft — ADR-002 mục 5 không có ngoại lệ cho kênh chat.

## Ranh giới tài liệu — đọc kỹ trước khi code

- **Kênh ≠ nguồn.** ADR-002 giới hạn *nguồn dữ liệu đọc vào* còn năm cái. Dùng
  Telegram làm *bề mặt giao tiếp* không phải thêm nguồn thứ sáu. Nhưng nếu bot
  bắt đầu **đọc nội dung nhóm chat Telegram để rút trích task**, đó mới là thêm
  nguồn và phải có ADR riêng. Ranh giới này phải ghi tường minh trong ADR mới,
  nếu không sáu tuần sau sẽ có người vượt qua nó mà không ai nhận ra.
- **Đây vẫn là material change** (thêm bề mặt, thay đổi ranh giới riêng tư: nội
  dung tóm lược nội bộ đi qua hạ tầng bên thứ ba). Theo DOCUMENTATION-GUIDE, cần
  decision record + đúng người duyệt. Spike này không thay được ADR đó.
- **CLAUDE.md đang ghi Telegram là chỗ "đang lệch, chưa chốt"**
  (`src/services/connections/telegram.py` nằm ngoài ADR-002). ADR mới là dịp giải
  quyết luôn khoản lệch này, hoặc xác nhận nó, hoặc gỡ file đó đi.
- **Không nằm trong phạm vi sáu tuần đã duyệt.** One-page brief §"Không làm trong
  sáu tuần" không cấm kênh chat, nhưng roadmap cũng không có chỗ cho nó. Mở luồng
  này là quyết định về ưu tiên, thuộc PM.

## Đề xuất lộ trình

| Bước | Việc | Ước lượng |
| --- | --- | --- |
| 0 | ADR "kênh mobile-first qua Telegram" — chốt ranh giới kênh/nguồn, privacy | 0.5 ngày |
| 1 | Spike: webhook + echo + bảng `channel_identity_links` + liên kết bằng nonce | 1 ngày |
| 2 | Cắm vào conversation core, trả lời có dẫn nguồn, test phân quyền tài khoản chưa liên kết | 1.5 ngày |
| 3 | Đẩy briefing hằng ngày + nhắc việc qua bot | 1 ngày |
| 4 | Mini App cho preview/confirm draft và `.ics` | 3–5 ngày |

Bước 0–3 đủ để kiểm chứng giả thuyết "học viên đọc briefing trên điện thoại
nhiều hơn trên web" — đo bằng chính chỉ số loại 2 đã có trong one-page brief (số
người mở bản tóm lược theo ngày). Bước 4 chỉ làm nếu bước 3 cho tín hiệu tốt.

## Câu hỏi còn mở

1. Mục tiêu thật của luồng mobile-first là **tăng lượt đọc briefing** hay **giảm
   ma sát khi hỏi đáp**? Hai mục tiêu này dẫn tới hai thiết kế khác nhau (đẩy
   nhiều vs hội thoại nhiều) và cần chốt trước bước 0.
2. Có chấp nhận nội dung tóm lược nội bộ của chương trình đi qua hạ tầng
   Telegram không? Đây là câu hỏi cho PM, không phải cho kỹ thuật.
3. Nếu pilot thành công, phát hành rộng ở VN gần như bắt buộc phải sang Zalo —
   có nên thiết kế adapter đa kênh ngay từ đầu, hay chấp nhận viết lại?
4. Web app hiện có bị hạ ưu tiên không? Hai bề mặt song song là hai chỗ phải bảo
   trì trong khi nhóm có bốn người.

## Nguồn

- [Telegram Bot API changelog](https://core.telegram.org/bots/api-changelog) — Bot API 10.1 (11/06/2026), 10.2 (14/07/2026)
- [Telegram Mini Apps](https://core.telegram.org/bots/webapps)
- [Discord Rate Limits](https://docs.discord.com/developers/topics/rate-limits)
- [Discord API — phân biệt lỗi 50007 và 50278](https://github.com/discord/discord-api-docs/issues/8238)
- [Bảng giá dịch vụ Zalo OA (áp dụng 01/06/2026)](https://zalo.solutions/oa/pricing)
- [Zalo for Developers — chatbot trả lời tự động](https://developers.zalo.me/docs/official-account/phu-luc/lam-the-nao-de-tao-chatbot-tra-loi-tu-dong-voi-zalo-api)
- [Messenger Platform — chính sách nhắn tin](https://developers.facebook.com/documentation/business-messaging/messenger-platform/policy)
- [Messenger Platform changelog](https://developers.facebook.com/documentation/business-messaging/messenger-platform/changelog) — deprecate message tag từ 27/04/2026
- [Manychat — Meta bỏ Message Tags](https://community.manychat.com/product-updates/meta-s-deprecation-of-the-message-tags-feature-on-messenger-9010) — mốc 10/02/2026, ngoại lệ AU/EU/JP/KR/UK, `HUMAN_AGENT` không bị ảnh hưởng
- [Q&Me / báo chí VN — Zalo 98% mức độ sử dụng, 96% nhóm dưới 26 tuổi (khảo sát 03/2026)](https://baonghean.vn/en/zalo-thong-tri-thi-truong-ung-dung-di-dong-viet-nam-nam-2026-voi-ty-le-su-dung-cham-muc-98-10329834.html)
