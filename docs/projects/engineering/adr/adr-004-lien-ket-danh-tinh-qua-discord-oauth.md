# ADR-004 — Liên kết danh tính học viên bằng Discord OAuth, không bằng lời tự khai

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Technical Lead, UI/UX Lead, PO/QC |
| Last updated | 2026-08-08 |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [ADR-003](adr-003-gmail-va-discord-truoc-trong-hai-tuan-build.md) · [PRD §5](../../product/prd.md#5-nhóm-người-dùng-và-quyền-truy-cập) · [Memory lifecycle](../memory-lifecycle.md) · [Architecture](../architecture.md) |

## Bối cảnh

`POST /api/v1/chat` hiện không biết người gọi là ai. Endpoint chưa xác thực và
đang bật cờ `demo_unscoped_search` để tắt toàn bộ scope tìm kiếm. Mọi thứ trong
[memory lifecycle](../memory-lifecycle.md) — profile, candidate, promotion,
feedback — đều gắn với một `user_id`, nên chưa có danh tính thì chưa dựng được
lớp memory.

Discord của chương trình đặt tên hiển thị theo mã học viên, nên về lý thuyết có
thể suy ra học viên nào ứng với tài khoản Discord nào, và mở sẵn ngữ cảnh cho họ
ngay khi đăng nhập lần đầu.

Đo trên dữ liệu Discord đã đồng bộ (DB local, ngày đo 2026-08-08; 20.893 item,
1.105 tài khoản):

| Dạng tên hiển thị | Số tài khoản | Tỷ lệ |
| --- | --- | --- |
| `T###…` — mã đứng đầu | 703 | 63% |
| `G##-T###-<tên>` — có tiền tố nhóm | 273 | 25% |
| `T###` nằm giữa chuỗi | 8 | <1% |
| Không có mã | 123 | 11% |

Hai quan sát đi kèm: định dạng không đồng nhất (dấu phân cách là khoảng trắng
hoặc gạch nối), và tên hiển thị đổi được — đã có 2 tài khoản đổi tên ngay trong
tập dữ liệu này.

### Giả định phải giữ đúng

Quyết định này đứng được **chỉ khi `source_items.author_external_id` là snowflake
Discord thật**. [Discord connector spike](../discord-connector-spike.md) đã cảnh
báo đường nạp từ xlsx sinh `AuthorID` giả theo tên, không đối chiếu được với
Discord — dữ liệu vào bằng đường đó thì cơ chế trong ADR này vô hiệu hoàn toàn.

Kiểm tra trên DB local ngày 2026-08-08 cho ba dấu hiệu đều chỉ về đường API:
`pipeline_raw_messages` và `runs` đều rỗng (đường xlsx không để lại vết); 20.893
item nhiều hơn hẳn 6.373 tin của dataset xlsx; và giải mã timestamp trong cả
1.105 ID đều rơi vào khoảng 2016-12 đến 2026-07, hợp lý cho ngày tạo tài khoản
thật.

Trước khi chuyển ADR sang `Accepted`, cần một lần đối chiếu trực tiếp: lấy một
`author_external_id` bất kỳ hỏi Discord API bằng bot token và xác nhận trả về
đúng tài khoản. Nếu về sau có nguồn nạp bằng xlsx, item của nguồn đó phải được
đánh dấu và loại khỏi việc đối chiếu danh tính.

Phương án đầu tiên được đề xuất là người dùng tự nhập tên/mã rồi hệ thống map
theo chuỗi đó. Cách này mở quyền đọc dữ liệu nội bộ dựa trên một lời khai không
kiểm chứng: bất kỳ ai gõ đúng một mã học viên đều thừa hưởng ngữ cảnh của người
đó — thảo luận nhóm, task và bản tóm lược. Nó vi phạm **BR-04** (không dùng dữ
liệu quan sát để khẳng định danh tính khi chưa xác nhận) và **PRD §5** (ngay cả
người quản trị cũng không mặc định được xem nội dung cá nhân của người khác).

## Lựa chọn đã cân nhắc

| Phương án | Kết luận |
| --- | --- |
| Người dùng tự nhập mã học viên | **Loại.** Tự khai, không kiểm chứng được; vi phạm BR-04 và PRD §5 |
| Đối chiếu email Google với danh sách học viên | **Loại cho P0.** Chưa có danh sách chính thức, và email đăng ký Discord thường khác email Google |
| Discord OAuth `identify` | **Chọn.** Chứng minh được quyền sở hữu tài khoản; hạ tầng đã có sẵn |
| Mentor duyệt thủ công toàn bộ | **Loại làm đường chính**, giữ làm đường dự phòng cho các trường hợp không khớp |

## Quyết định

1. **Tách hai loại danh tính.** Danh tính đăng nhập là tài khoản Google, trả lời
   "ai đang dùng ứng dụng". Danh tính trong bằng chứng là tài khoản Discord, trả
   lời "item nào trong kho là của người này". Hai thứ nối với nhau qua bảng
   `identity_links`, không gộp làm một.

2. **Chỉ Discord OAuth mới tạo được liên kết `confirmed`.** Người dùng bấm đăng
   nhập Discord với scope `identify`; hệ thống lấy snowflake ID trả về rồi đối
   chiếu với `source_items.author_external_id`. Người dùng không gõ mã học viên.

3. **Khoá liên kết là `author_external_id`.** Mã học viên và tên hiển thị chỉ
   được đọc ra và lưu lại tại thời điểm liên kết, không dùng làm khoá. Người dùng
   đổi tên Discord về sau không làm hỏng liên kết đã có.

4. **Không khớp thì không mở quyền.** Tài khoản Discord không có mặt trong kho
   bằng chứng, hoặc tên không chứa mã, thì liên kết dừng ở `candidate` và chờ
   mentor duyệt. `candidate` không mở bất kỳ quyền đọc nội bộ nào.

5. **Người dùng ngoài chương trình dùng được sản phẩm nhưng không truy vấn được
   nội dung nội bộ.** Giới hạn này thực thi bằng bộ lọc ở tầng truy vấn, không
   bằng câu chỉ dẫn trong prompt.

6. **Không bao giờ mở quyền dựa trên lời tự khai**, kể cả khi người dùng khai
   đúng.

## Lý do

**OAuth biến lời khai thành bằng chứng.** Discord trả về ID của chính tài khoản
vừa đăng nhập, nên liên kết là thứ chứng minh được chứ không phải thứ được khai.
Đây cũng là điều duy nhất phân biệt "tôi là T###" với "tôi chứng minh được tôi
là T###".

**Hạ tầng đã có.** `src/services/connections/discord.py` đã dựng sẵn OAuth với
đúng scope `identify`. Chọn phương án này rẻ hơn phương án tự nhập, vì phần khó
đã viết rồi.

**Bớt một bước cho người dùng.** Họ bấm hai lần thay vì bấm rồi gõ. Không phải
nhớ mã học viên của mình.

**Scope `identify` không nới ranh giới riêng tư.** Nó chỉ trả về thông tin tài
khoản cơ bản, không đọc thêm tin nhắn hay kênh nào. Discord vốn đã nằm trong
phạm vi năm nguồn của [ADR-002](adr-002-connector-first-p0-scope.md), nên đây
không phải thêm nguồn mới.

**Khoá theo ID chịu được thực tế dữ liệu.** Tên hiển thị đã được chứng minh là
thay đổi được; snowflake thì không.

## Hệ quả

**Chấp nhận:** thêm một bước OAuth trong lần đăng nhập đầu. Học viên thật nhưng
chưa từng nhắn gì trên Discord sẽ không khớp và phải đi đường mentor duyệt —
theo số đo hiện tại, nhóm này cộng với nhóm không có mã rơi vào khoảng 11% trở
lên.

**Phải làm:**

- Bỏ cờ `demo_unscoped_search`; `/api/v1/chat` nhận `user_id` từ JWT và truyền
  scope thật xuống tầng retrieval.
- Thêm trục *audience* cho `source_scopes`. **Không dùng lại cột `tier`** — `tier`
  A/B là mức đáng tin của nguồn theo PRD §6.4, khác hẳn với ai được phép đọc.
- Cập nhật [PRD §5](../../product/prd.md#5-nhóm-người-dùng-và-quyền-truy-cập):
  hiện chỉ có ba nhóm người dùng, "người dùng ngoài chương trình" là nhóm thứ tư
  và cần được định nghĩa kèm quyền. Đây là material change của PRD, phải chốt
  riêng.
- Bổ sung test phân quyền: cùng một câu hỏi nội bộ, chạy bằng tài khoản chưa liên
  kết, phải trả về 0 bằng chứng — không phải trả về câu từ chối do model tự nghĩ.

**Không đổi:** phạm vi năm nguồn của ADR-002; luật của
[memory lifecycle](../memory-lifecycle.md) về `candidate` và promotion — liên kết
danh tính tuân theo đúng vòng đời đó thay vì tự định nghĩa trạng thái riêng.

**Rollback:** liên kết lưu ở bảng riêng và có `status` cùng `valid_to`. Gỡ một
liên kết sai là chuyển trạng thái, không xoá dữ liệu, và quyền đọc mất hiệu lực
ngay ở lần truy vấn kế tiếp.

## Việc kèm theo

| Việc | Jira | DRI |
| --- | --- | --- |
| Đăng nhập Google, phát JWT có `user_id` | chưa tạo | Phong |
| Bảng `identity_links` và parser mã học viên bốn dạng | chưa tạo | An |
| Luồng liên kết Discord OAuth `identify` | chưa tạo | An |
| Màn hình onboarding và trạng thái chờ duyệt | chưa tạo | Nhi |
| Bỏ `demo_unscoped_search`, chặn quyền ở tầng truy vấn | chưa tạo | Phong |
| Test phân quyền cho tài khoản chưa liên kết | chưa tạo | Dũng |
