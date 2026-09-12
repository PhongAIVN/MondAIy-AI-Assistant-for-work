# ADR-010 — Trang quản trị lịch chương trình: sửa tay thắng feed, phát hành có bước duyệt

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Lê Thị Yến Nhi (UI/UX Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-12 |
| Related | [ADR-008](adr-008-lich-chuong-trinh-tu-ics-feed.md) · [ADR-009](adr-009-dong-bo-lich-chuong-trinh-sang-lich-ca-nhan.md) · [PRD §5](../../product/prd.md) |

## Bối cảnh

ADR-008 coi feed ICS là nguồn nhập và bảng `program_events` là bản sao chỉ đọc.
Giả định ngầm ở đó là ban tổ chức nội bộ không bao giờ cần sửa gì. Giả định đó
sai ngay khi dùng thật:

- Feed ghi thiếu hoặc ghi sai (tiêu đề cụt, thiếu tên diễn giả, sai link phòng).
- Có buổi phát sinh chưa kịp lên Phoenix nhưng cần báo học viên ngay.
- Có mốc cần soạn trước rồi mới công bố, không phải hiện ngay khi vừa nhập.

Không có trang quản trị thì cách duy nhất để sửa là vào DB bằng tay — không dấu
vết, không ai duyệt, và bị lần nhập feed kế tiếp xoá sạch.

Xoá sạch **im lặng** mới là phần nguy hiểm: người sửa tưởng đã sửa xong, học
viên vẫn đọc bản cũ, và không có tín hiệu nào cho biết chuyện đó đã xảy ra.

## Quyết định

### 1. Sửa tay thắng feed, ở mức từng trường

Trường nào quản trị sửa trên một mốc gốc feed thì trường đó vào `locked_fields`.
Lần nhập sau **không** ghi đè các trường đó, nhưng vẫn cập nhật bình thường mọi
trường còn lại.

Khoá theo trường chứ không theo cả dòng: sửa tiêu đề không có lý do gì làm mốc
đó ngừng nhận cập nhật giờ giấc từ ban tổ chức.

### 2. Feed đổi đúng vào trường đang khoá thì báo, không tự chọn

Mỗi lần nhập lưu lại `feed_payload` — ảnh chụp bản của ban tổ chức. Nếu lần nhập
mới đổi đúng một trường đang khoá, mốc đó bật `source_conflict` và hiện lên trang
quản trị kèm cả hai bản để người quyết định.

Tự chọn hộ bên nào cũng sai: chọn feed thì xoá chỉnh sửa có chủ đích, chọn bản
sửa tay thì giấu mất việc ban tổ chức vừa dời lịch.

### 3. Có đường lui: hoàn về bản gốc

`POST /{id}/revert-to-source` bỏ toàn bộ khoá và ghi lại giá trị từ
`feed_payload`. Không có đường này thì một lần sửa nhầm là mốc đó đóng băng vĩnh
viễn, không bao giờ nhận cập nhật từ ban tổ chức nữa.

### 4. Ba trạng thái phát hành, mặc định khác nhau theo nguồn

| Trạng thái | Ai thấy |
| --- | --- |
| `draft` | chỉ quản trị |
| `published` | học viên mức A, qua `program_schedule` và đồng bộ lịch |
| `archived` | không ai, nhưng dòng vẫn còn |

Mốc **nhập từ feed** vào thẳng `published`: đó là bản ban tổ chức đã công bố
công khai rồi, giữ ở `draft` nghĩa là học viên mất lịch cho tới khi có người bấm
phát hành từng mốc một — 83 lần bấm cho một lần nhập.

Mốc **quản trị tự tạo** bắt đầu ở `draft`: thêm xong hiện ngay thì không còn
bước nào để soát lại trước khi tới tay học viên.

`list_program_events` mặc định chỉ trả `published`. Tham số `statuses` để mặc
định ở giá trị hẹp nhất — quên truyền thì kết quả hẹp hơn thực tế, không rộng
hơn quyền.

### 5. Không có xoá cứng

Chỉ `archived`. Mốc đã phát hành có thể đã nằm trong lịch Google của học viên
(ADR-009); xoá sạch dấu vết ở đây là mất khả năng giải thích thứ họ đang thấy
đến từ đâu.

### 6. Mọi thay đổi vào audit, nhưng audit không mang nội dung

Tạo, sửa, phát hành, rút về nháp, gỡ, hoàn về gốc — đều `emit_audit`. Nhưng
details **chỉ ghi tên trường đã đổi**, không ghi giá trị.

Lý do là một chốt chặn đã có: `/admin/audit` là luồng chung cho mọi loại đối
tượng và PRD §5 cấm nội dung gốc xuất hiện ở đó. Ghi giá trị vào audit là mở một
đường cho nội dung của loại đối tượng khác đi ra theo. Nội dung mốc đọc trên
chính trang lịch, nơi nó thuộc về.

### 7. Endpoint quản trị lịch **có** trả nội dung, và điều đó không phá PRD §5

`/admin/program-events` trả `title`, `description`. Đây là ngoại lệ có chủ đích
so với các endpoint admin khác: nội dung mốc là **dữ liệu chương trình do ban tổ
chức soạn để phát cho học viên**, không phải nội dung cá nhân của người dùng.
Ranh giới PRD §5 bảo vệ email, tin nhắn, câu hỏi của người dùng — nó không nói
rằng quản trị không được đọc lịch mình đang biên tập.

Cần ghi rõ ở đây vì test chốt chặn `test_khong_endpoint_admin_nao_tra_noi_dung_ca_nhan`
liệt kê đường dẫn tường minh; ai thêm đường dẫn này vào danh sách đó sẽ làm hỏng
tính năng mà tưởng là đang siết bảo mật.

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
| --- | --- |
| Feed luôn thắng, quản trị chỉ bật/tắt hiển thị | Không sửa được tiêu đề sai, đúng nhu cầu số một |
| Quản trị thắng ở mức cả dòng | Sửa tiêu đề xong thì mốc đó ngừng nhận cả cập nhật giờ giấc — hỏng âm thầm hơn |
| Sửa xong tự động ghi đè ngược lên feed | Ta không có quyền ghi lên Phoenix và không nên có |
| Bảng `program_event_overrides` riêng | Đúng về mô hình nhưng mọi truy vấn đọc phải join và tự trộn; giá trị thêm không bù nổi |
| Phát hành theo lô cả cohort | Nhanh hơn nhưng mất khả năng giữ một mốc ở nháp trong khi phát hành phần còn lại |
| Xoá cứng | Mất dấu vết của mốc có thể đang nằm trong lịch cá nhân học viên |

## Hệ quả

- Ban tổ chức nội bộ sửa được lịch mà không đụng DB, và mọi thay đổi có dấu vết.
- Thêm một trạng thái vào đường đọc: mốc `draft` không tới học viên. Nếu ai đó
  nhập mốc mới bằng đường khác mà quên `status`, mặc định của cột là `published`
  — chọn như vậy để lỗi nghiêng về "hiện lịch" chứ không "mất lịch".
- `locked_fields` là nợ vận hành: khoá nhiều thì mốc đó dần rời khỏi nguồn. Trang
  quản trị hiện nhãn "giữ tay" trên từng mốc để chỗ này không vô hình.
- Chưa có phân quyền nhỏ hơn admin. Trợ giảng muốn sửa lịch vẫn phải là admin
  toàn quyền — cần role `program_editor` nếu vận hành thật cần.
- Chưa có lịch sử phiên bản của từng mốc. Audit ghi ai đổi trường nào lúc nào,
  nhưng không dựng lại được nội dung cũ nếu mốc đó không phải gốc feed.

## Đã hiện thực theo quyết định này

| Thành phần | Đường dẫn |
| --- | --- |
| Cột lớp quản trị | `src/models/program_event.py` · migration trong `src/db.py` |
| Luật nhập tôn trọng khoá tay | `src/services/program_calendar.py` |
| Endpoint quản trị | `src/api/admin_program_events.py` |
| Schema | `src/models/schemas.py` |
| Giao diện | `client/web-app/src/pages/admin/AdminProgramEventsPage.tsx` · `src/lib/adminApi.ts` |
| Kiểm thử | `tests/test_api/test_admin_program_events.py` · `client/web-app/tests/AdminProgramEventsPage.test.tsx` |

## Việc phải làm để quyết định này có hiệu lực

| # | Việc | Người phụ trách |
| --- | --- | --- |
| 1 | Cập nhật PRD §5: nêu ngoại lệ ở khoản 7 để lần soát bảo mật sau không gỡ nhầm | Thái Hoài An |
| 2 | Quyết định có cần role `program_editor` không | Thái Hoài An |
| 3 | Rà giao diện: trạng thái rỗng, đang tải, lỗi, và nhãn xung đột | Lê Thị Yến Nhi |
| 4 | ~~Ca kiểm thử khoá nhiều trường và mốc archived~~ — đã có trong `tests/test_api/test_program_calendar_sync_boundaries.py` | Nguyễn Đức Dũng |
