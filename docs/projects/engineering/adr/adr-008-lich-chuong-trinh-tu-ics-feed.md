# ADR-008 — Lịch chương trình nhập từ ICS feed, chỉ mở cho mức A

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-12 |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [ADR-004](adr-004-lien-ket-danh-tinh-qua-discord-oauth.md) · [ADR-007](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [Discord access and tool contract](../../../discord-access-and-tools.md) |

## Bối cảnh

Ban tổ chức công bố toàn bộ lịch khóa học trên Phoenix: workshop, office hour,
hạn nộp daily/weekly, gate và mốc demo day. Đây chính là loại câu hỏi Program
Navigator sinh ra để trả lời — "tuần này có buổi nào", "gate MVP hạn khi nào",
"office hour tối nay ai chủ trì".

Hiện agent không có đường nào chạm tới dữ liệu đó. Nó chỉ có `discord_*` (tin
nhắn đã cào) và `calendar_search_events` (Google Calendar cá nhân). Hệ quả:

- Hỏi lịch khóa học thì agent hoặc tìm trong Discord và trả về một mẩu thảo
  luận rời rạc, hoặc tra Google Calendar cá nhân và trả lời "không có sự kiện
  nào" — sai theo cách nguy hiểm nhất, vì nghe như một câu trả lời chắc chắn.
- Lịch bị đổi buổi (dời workshop, dời mentor duty) chỉ nằm trong thông báo
  Discord, phải suy ra từ văn bản. Đó đúng là chỗ mô hình hay đoán sai.

ADR-002 khoản về phạm vi nguồn buộc mọi nguồn mới phải có ADR riêng, nên đây là
material change chứ không phải task kỹ thuật.

Ba dữ kiện quyết định hình dạng lời giải:

1. Ban tổ chức **không mở API** cho bên thứ ba. `/api/events` của Phoenix đòi
   cookie đăng nhập của chính học viên.
2. Trang lịch có nút "Đăng ký lịch", phát ra một **feed `.ics` chuẩn iCalendar**
   theo token cá nhân, không cần đăng nhập khi gọi lại. Feed chứa đúng tập sự
   kiện của `/api/events`, kèm `REFRESH-INTERVAL:PT1H`.
3. Trong feed có cả **lịch trực của từng nhóm mentor** (UID tiền tố `duty:`).
   Đây là lịch riêng của một nhóm, không phải lịch chung của khóa.

## Quyết định

### 1. ICS feed là nguồn nhập, không phải scrape HTML hay gọi API nội bộ

Nhập bằng `scripts/import_program_calendar.py`, đọc URL từ
`PHOENIX_ICS_FEED_URL`. Không tự động hóa việc đăng nhập vào Phoenix và không
đọc `/api/events` bằng phiên của người dùng.

Lý do: feed là kênh ban tổ chức **chủ động phát ra** cho mục đích đúng như thế,
có hợp đồng ổn định (RFC 5545) và có TTL. Còn tự động đăng nhập rồi gọi API nội
bộ là dùng danh tính của học viên để lấy dữ liệu theo cách chủ sở hữu chưa đồng
ý — trái nguyên tắc "chỉ làm việc trên nguồn người dùng đã cho phép" của sản
phẩm.

### 2. Bảng riêng `program_events`, không nhét vào `source_items` hay `calendar_events`

| Bảng | Đơn vị | Chủ sở hữu |
| --- | --- | --- |
| `source_items` | tin nhắn | kênh Discord |
| `calendar_events` | event Google | một user |
| `program_events` | mốc chương trình | cả cohort |

Nhét vào `source_items` thì phải giả một `author_external_id` và mất hai mốc
thời gian của sự kiện. Nhét vào `calendar_events` thì phải nhân bản cùng một
buổi workshop cho từng học viên. Khóa upsert là `(cohort_slug, UID của ICS)`.

### 3. Đọc lịch chương trình là quyền của mức A

Tool `program_schedule` chỉ trả dữ liệu khi `program_access_level == "A"`.

Mức B/C nhận **câu từ chối nêu lý do**, không nhận danh sách rỗng — cùng lập
luận đã áp cho `discord_list_announcements`: trả rỗng là nói với học viên rằng
chương trình không có buổi nào, sai hoàn toàn và họ không có manh mối để sửa.

Mức truy cập tính lại trong `apply_search_scope` bằng `reconcile_program_access`
rồi mới truyền xuống tool qua ContextVar, không nằm trong schema tool — model
hoặc câu lệnh nhét vào prompt không tự nâng mình lên mức A được.

### 4. Sự kiện riêng của một nhóm không nằm trong câu trả lời chung

Sự kiện `mentor_duty` được nhập nhưng đánh `visibility = "team"`, và
`list_program_events` mặc định **loại** chúng. Cờ mở là `include_team_scoped`,
mặc định `False`: quên truyền thì kết quả hẹp hơn thực tế chứ không rộng hơn
quyền.

P0 chưa có ánh xạ user → nhóm mentor trong P-004, nên **chưa tool nào trả về
lịch trực của nhóm**. Khi có ánh xạ đó thì mở bằng một thay đổi riêng, không
phải bằng cách bỏ cờ này đi.

### 5. Nhập lại là idempotent, và không tự xóa

Băm nội dung (không băm `DTSTAMP`) để phân biệt "ban tổ chức sửa lịch" với
"feed được sinh lại". Sự kiện vắng mặt trong feed **không bị xóa**: ban tổ chức
gỡ một buổi và feed lỗi một nửa là hai chuyện khác nhau, mà từ phía ta chúng
trông giống hệt nhau.

### 6. Dữ liệu đã nhập không được trình bày như dữ liệu thời gian thực

Giống khoản 7 của ADR-007. Lịch trong `program_events` là ảnh chụp của lần nhập
gần nhất; nguồn chuẩn vẫn là trang của ban tổ chức.

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
| --- | --- |
| Tự động đăng nhập Phoenix rồi gọi `/api/events` | Dùng phiên đăng nhập của học viên để lấy dữ liệu bên thứ ba chưa đồng ý mở; hợp đồng nội bộ đổi lúc nào cũng được |
| Scrape HTML trang `/events` | Trang render phía client, phải chạy trình duyệt thật; giòn hơn ICS mà không được thêm gì |
| Chép lịch thành file markdown trong repo | Hết hạn ngay khi ban tổ chức dời buổi, và không ai biết nó đã cũ |
| Nhét lịch vào system prompt cho mức A | Tốn token mỗi lượt, không lọc được theo khoảng thời gian, và cập nhật phải sửa code |
| Mở lịch cho cả mức B/C | Đây là dữ liệu chương trình; ADR-004 đã đặt ranh giới mức A là ranh giới đọc dữ liệu chương trình. Mở ở đây là mở một lỗ bên cạnh cửa đã khóa |
| Đưa mentor duty vào lịch chung | Trả lịch trực của nhóm khác cho người không thuộc nhóm đó — đúng loại lỗi làm mất niềm tin nhanh nhất |
| Đồng bộ hai chiều với Phoenix | Ta không có quyền ghi và không nên có |

## Hệ quả

- Agent trả lời được câu hỏi lịch khóa học bằng dữ liệu có cấu trúc, thay vì
  suy từ tin nhắn Discord.
- Thêm một nguồn dữ liệu ngoài vào P0 → PRD mục nguồn dữ liệu và ADR-002 phải
  được cập nhật cho khớp, nếu không tài liệu và code lệch nhau.
- `PHOENIX_ICS_FEED_URL` chứa token cá nhân. Token này **không được commit**,
  không vào `.env.example` với giá trị thật, và phải nằm trong danh sách quét
  secret trước khi ship.
- Vòng nhập nền đã có trong worker nhưng **mặc định tắt**: bật là hệ thống tự
  gọi ra ngoài theo nhịp, và feed chỉ có ở máy đã điền token. Chưa bật thì vẫn
  nhập tay bằng script. Nhịp mặc định 60 phút, khớp `REFRESH-INTERVAL:PT1H` của
  feed — quét dày hơn là gọi thừa.
- Lịch nhập vào chưa nối với lớp nhắc việc của ADR-007. Nối được là bước tiếp
  theo có giá trị nhất, nhưng nằm ngoài quyết định này.

## Đã hiện thực theo quyết định này

| Thành phần | Đường dẫn |
| --- | --- |
| Bảng lịch chương trình | `src/models/program_event.py` |
| Đọc ICS, nhập, truy vấn | `src/services/program_calendar.py` |
| Tool gate theo mức A | `src/agents/tools/program_calendar_tool.py` |
| Đặt phạm vi mỗi lượt agent | `src/services/scope.py` |
| Script nhập lịch | `scripts/import_program_calendar.py` |
| Vòng nhập nền (mặc định tắt) | `src/worker.py` · `refresh_from_feed` trong `src/services/program_calendar.py` |
| Kiểm thử | `tests/test_services/test_program_calendar.py` · `tests/test_agents/test_program_calendar_tool.py` |

## Việc phải làm để quyết định này có hiệu lực

| # | Việc | Người phụ trách |
| --- | --- | --- |
| 1 | Cập nhật PRD mục nguồn dữ liệu và whitelist tool, thêm `program_schedule` | Thái Hoài An |
| 2 | Ghi nguồn mới vào ADR-002 hoặc nêu rõ ADR-008 mở rộng phạm vi của nó | Nguyễn Văn Phong |
| 3 | Ca kiểm thử mức B/C không đọc được lịch, mentor duty không lọt lịch chung, nhập lại không nhân bản | Nguyễn Đức Dũng |
| 4 | ~~Lên job định kỳ~~ — đã có vòng nền, còn lại là quyết định bật ở môi trường nào và nơi giữ token | Nguyễn Văn Phong |
