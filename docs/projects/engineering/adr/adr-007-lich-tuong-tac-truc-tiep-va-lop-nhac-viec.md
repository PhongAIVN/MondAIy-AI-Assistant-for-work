# ADR-007 — Lịch tương tác trực tiếp và lớp nhắc việc

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Lê Thị Yến Nhi (UI/UX Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-11 |
| Related | [PRD](../../product/prd.md) · [ADR-002](adr-002-connector-first-p0-scope.md) · [Calendar pipeline](../../../calendar-pipeline.md) · [Agent productivity actions](../../../agent-productivity-actions.md) · [Wireframe & UI flow](../../design/wireframe-ui-flow.md) |

## Bối cảnh

P0 hiện chỉ cho tạo mới event/task/todo qua proposal của agent, và chỉ đẩy task
lên Google Calendar bằng thao tác Confirm + Sync. Người dùng không có nơi nào
nhìn thấy công việc của mình theo trục thời gian, không sửa hay xóa được event
đã tạo, và không được nhắc khi hạn chót tới gần.

Hệ quả là chỉ số quan trọng nhất — tỷ lệ hoàn thành công việc đến hạn trong
tuần (PRD §4.2) — không có cơ chế nào tác động vào. Sản phẩm biết việc sắp đến
hạn nhưng không nói cho người dùng đúng lúc, và người dùng không có đường phản
hồi rằng việc đó đã xong, chưa xong hay không còn cần nữa.

ADR-002 khoản 5 và 6 đặt ranh giới "mọi hành động ghi phải qua preview và nút
Chấp nhận, sửa/xóa ngoài phạm vi". Ranh giới đó được đặt ra để chặn **agent tự
ý ghi**, nhưng khi áp nguyên văn lên một giao diện lịch thì nó biến thao tác
kéo một event sang khung giờ khác thành ba lần xác nhận. Cần tách hai chủ thể
ghi khác nhau thay vì nới lỏng nguyên tắc.

## Quyết định

### 1. Tách quyền ghi theo chủ thể khởi tạo

| Chủ thể khởi tạo | Luồng bắt buộc |
| --- | --- |
| Người dùng thao tác trực tiếp trên giao diện lịch | Ghi ngay, kèm Undo |
| Agent đề xuất từ hội thoại hoặc từ nguồn | Draft → preview → nút Chấp nhận → executor |

Thao tác trực tiếp là tạo, sửa, kéo đổi giờ hoặc xóa event do chính người dùng
thực hiện trên lưới lịch hoặc form chi tiết. Bản thân thao tác đó là sự xác
nhận; không hiện thêm hộp thoại.

Agent **không được ghi thẳng trong mọi trường hợp**. Luồng
`create_productivity_item` giữ nguyên như [Agent productivity
actions](../../../agent-productivity-actions.md): tool chỉ dựng proposal, side
effect chỉ chạy qua endpoint approve, proposal ký HMAC, chỉ draft của message
ngay trước đó được tiếp tục.

### 2. Undo thay cho hộp thoại xác nhận

Mọi thao tác ghi trực tiếp hiện thanh Undo trong 10 giây. Xóa event là thao tác
duy nhất không khôi phục được từ phía Google nếu bỏ lỡ cửa sổ này, nên bản ghi
event bị xóa được giữ lại trong `calendar_events` với trạng thái `deleted` cho
tới hết thời hạn lưu, đủ để tạo lại nội dung nếu người dùng yêu cầu.

### 3. Mở whitelist tool cho thao tác của người dùng, không cho agent

PRD §11 được mở rộng thêm `update_calendar_event` và `delete_calendar_event`,
kèm điều kiện thực thi:

- `actor_type = user` và request đến từ endpoint thao tác trực tiếp;
- ownership và scope được kiểm lại phía máy chủ, không tin field client gửi lên;
- agent không được bind hai tool này; danh sách tool của agent giữ nguyên.

### 4. Phân biệt bỏ qua lời nhắc với hủy công việc

Đây là hai hành vi khác nhau và phải nằm ở hai tầng khác nhau:

| Thao tác | Tầng | Kết quả | Ảnh hưởng chỉ số |
| --- | --- | --- | --- |
| Bỏ qua | Lời nhắc | `reminder.status = cancelled`, không nhắc lại nữa | Task vẫn nằm trong mẫu số |
| Nhắc lại | Lời nhắc | Dời thời điểm giao thông báo, trạng thái không đổi | Không |
| Đã làm | Công việc | `task.status = completed` | Vào tử số |
| Hủy việc | Công việc | `task.status = cancelled` | Rút khỏi mẫu số |

"Bỏ qua" trên popup chỉ tắt lời nhắc, không đụng tới công việc. Chỉ nút Hủy
việc trong màn hình chi tiết mới rút công việc khỏi mẫu số của PRD §4.2.

Nếu gộp hai thứ này, người dùng bấm bỏ qua càng nhiều thì tỷ lệ hoàn thành báo
cáo càng cao trong khi thực tế không có việc nào được làm. Đó là lý do bắt buộc
phải tách, không phải sở thích đặt tên.

### 5. Ưu tiên công việc tính bằng luật, không bằng mô hình

Mức ưu tiên của một lời nhắc được tính bằng hàm xác định từ: khoảng cách tới
hạn chót, mức độ đáng tin của nguồn (Mức A hay Mức B), công việc có thuộc về
người dùng không, và số lần người dùng đã bỏ qua nó.

Mô hình chỉ được xếp lại thứ tự **trong cùng một bậc ưu tiên**. Điều này giữ
đúng PRD §6.4 và FR-042 — phán đoán của AI chỉ sắp xếp mức liên quan, không đổi
mức độ đáng tin — và giúp mức ưu tiên kiểm chứng được trên bộ dữ liệu kiểm thử
thay vì phải tin vào đầu ra của mô hình.

### 6. Không tạo calendar mới; nhiều lịch chỉ để đọc và chọn đích ghi

mondaiy không tạo calendar mới trên tài khoản người dùng. Sản phẩm liệt kê các
lịch sẵn có, cho người dùng chọn lịch nào hiển thị và chọn lịch đích khi ghi
event.

Scope OAuth hiện tại đủ cho toàn bộ phạm vi này: `calendar.readonly` liệt kê và
đọc mọi lịch người dùng có quyền, `calendar.events` ghi event vào lịch họ chọn.
**Không cần scope mới và không cần người dùng kết nối lại Google.**

### 7. Lưu lại lịch đã đọc

Event đọc từ Google được lưu vào `calendar_events` khóa theo
`(user_id, calendar_id, event_id)`. Lần đọc sau dùng `syncToken` của Google để
chỉ lấy phần thay đổi thay vì quét lại toàn bộ khoảng thời gian; con trỏ lưu
trong `sync_cursors`, bảng đã có ràng buộc `UniqueConstraint(user_id, key)`.

Giao diện đọc bản đã lưu để hiện ngay, làm mới ở nền, và luôn hiển thị thời
điểm cập nhật gần nhất. Không trình bày dữ liệu đã lưu như dữ liệu thời gian
thực.

Khi Google trả `410 Gone` cho một `syncToken`, hệ thống đọc lại toàn bộ khoảng
thời gian và thay con trỏ. Event không còn tồn tại phía Google được đánh dấu
`stale`, không tự tạo lại.

### 8. Chống bão thông báo

Mặc định nhắc trước 1 ngày và trước 30 phút, người dùng chỉnh được. Kèm theo:

- lời nhắc rơi vào cùng một khung giờ được gộp thành một thông báo;
- có trần số thông báo trong một giờ;
- có giờ yên lặng; lời nhắc rơi vào giờ yên lặng được dời tới đầu khung giờ hoạt động.

Không có ba thứ này thì với 5–10 người thử nghiệm và khoảng 15 công việc mỗi
tuần mỗi người, extension sẽ bị tắt trước khi thu được dữ liệu.

### 9. Cơ chế đẩy thông báo

Dùng `chrome.alarms` trong extension, nạp lịch nhắc từ một endpoint đọc nhẹ.
Không dựng hạ tầng push phía máy chủ trong P0.

Service worker của MV3 bị dừng bất kỳ lúc nào, nên mỗi lần đánh thức phải nạp
lại lịch nhắc từ máy chủ thay vì tin vào state trong bộ nhớ. Mỗi lần giao thông
báo ghi vào `notification_deliveries` để khởi động lại không giao trùng.

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
| --- | --- |
| Agent được ghi thẳng như người dùng | Phá BR-08 và nguyên tắc sản phẩm số 6; một lần agent sửa sai lịch là mất niềm tin, đúng vấn đề PRD §2 đặt ra |
| Bắt người dùng xác nhận cả khi kéo event | Ba lần xác nhận cho một thao tác kéo; người dùng sẽ quay về dùng Google Calendar |
| Tạo một calendar riêng tên `mondaiy` | Cần scope tạo calendar, kéo theo rủi ro verification của Google dài hơn cả pilot; giá trị phân loại đạt được bằng nhãn trong sản phẩm |
| Đồng bộ hai chiều thật với Google | Đụng FR-013 (không ghi đè) và BR-09 (nguồn đổi không tự sửa hành động đã xác nhận), buộc phải làm giao diện xử lý mâu thuẫn. P0 ghi một chiều và chỉ cảnh báo khi phát hiện lệch |
| Lịch lặp, mời người tham dự | RRULE kèm ngoại lệ và múi giờ là khối lượng lớn nhất của miền lịch; mời người tham dự gửi thư cho bên thứ ba, nằm ngoài PRD §4.4 |
| Push server (FCM hoặc Web Push) | Khoảng một tuần công để đổi lấy độ trễ thấp hơn mà quy mô thử nghiệm không cần |
| Cho mô hình chấm mức ưu tiên tự do | Không chứng minh được ở gate vì không chạy được trên bộ dữ liệu kiểm thử |

## Hệ quả

- Người dùng có nơi nhìn thấy công việc theo trục thời gian và được nhắc đúng
  lúc; chỉ số chính của PRD §4.2 lần đầu có cơ chế tác động.
- Ranh giới "agent không tự ghi" của ADR-002 được giữ nguyên, không nới.
- Chỉ số ngưỡng cứng *hành động xảy ra trước khi người dùng xác nhận = 0* phải
  được đọc là **hành động do hệ thống khởi tạo**. Nếu không sửa câu chữ này
  trong PRD §4.3, thao tác trực tiếp hợp lệ sẽ bị tính là vi phạm khi nghiệm thu.
- Thêm rủi ro mới: xóa nhầm event thật. Undo và bản lưu `deleted` là biện pháp
  giảm thiểu; cần test riêng cho luồng này.
- Cache lịch tạo thêm bề mặt rò dữ liệu giữa người dùng. Ngưỡng của PRD §4.3 cho
  lỗi này là 0, nên test đọc chéo người dùng phải có ngay từ commit đầu, không
  để cuối.
- Không phát sinh scope OAuth mới, không phát sinh lần kết nối lại nào.
- Lịch lặp, mời người tham dự và đồng bộ hai chiều chỉ được xem lại sau thử
  nghiệm bằng ADR mới, không tự động quay lại backlog P0.

## Việc phải làm để quyết định này có hiệu lực

| # | Việc | Người phụ trách |
| --- | --- | --- |
| 1 | Cập nhật PRD §4.2, §4.3, §9, §10, §11 và mục 8.7, 8.9 | Thái Hoài An |
| 2 | Thiết kế trạng thái rỗng, chưa đầy đủ, mâu thuẫn và Undo cho lưới lịch tuần | Lê Thị Yến Nhi |
| 3 | Bổ sung ca kiểm thử: đọc chéo người dùng trên cache, Undo, chống giao trùng thông báo, tách dismiss với cancel | Nguyễn Đức Dũng |
| 4 | Contract endpoint thao tác trực tiếp và endpoint đọc lịch nhắc | Nguyễn Văn Phong |
