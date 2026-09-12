# ADR-009 — Đồng bộ lịch chương trình sang lịch cá nhân, bắt buộc qua duyệt

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Lê Thị Yến Nhi (UI/UX Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-12 |
| Related | [ADR-007](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [ADR-008](adr-008-lich-chuong-trinh-tu-ics-feed.md) · [Discord access and tool contract](../../../discord-access-and-tools.md) |

## Bối cảnh

ADR-008 đưa lịch chương trình vào `program_events` và cho agent đọc qua
`program_schedule`. Nhưng đọc được không có nghĩa là dùng được: học viên vẫn
phải tự chép từng buổi workshop và từng hạn gate sang lịch của mình, hoặc chấp
nhận không có gì nhắc.

Đây đúng là khoảng trống ADR-007 đã chỉ ra — chỉ số chính của PRD là tỷ lệ hoàn
thành việc đến hạn, mà sản phẩm biết hạn nhưng không đưa được nó vào nơi người
dùng thật sự nhìn.

Ràng buộc không được nới:

- **ADR-007 khoản 1**: agent không được ghi thẳng. Ghi phải đi qua đề xuất →
  xem trước → nút Chấp nhận.
- **BR-09**: nguồn đổi không tự sửa hành động người dùng đã xác nhận.
- **ADR-008 khoản 3 và 4**: chỉ mức A đọc được lịch chương trình, và sự kiện
  riêng của một nhóm không nằm trong dữ liệu chung.

## Quyết định

### 1. Hai bước tách rời: xem trước không ghi, ghi cần danh sách tường minh

| Endpoint | Làm gì | Có gọi Google không |
| --- | --- | --- |
| `POST /calendar/program-sync/preview` | Trả bảng mốc kèm `action` và `reason` | Không |
| `POST /calendar/program-sync/apply` | Ghi đúng các `programEventIds` được gửi lên | Có |

`apply` **không nhận bộ lọc**. Nó chỉ nhận danh sách ID. Nếu nó nhận bộ lọc
thì phía máy chủ tự quyết tập mốc, và bước xem trước không còn là sự xác nhận
cho cái gì cụ thể nữa.

Danh sách ID vẫn bị lọc lại phía máy chủ theo cohort và `visibility = program`.
Không tin client: thiếu bước này thì gửi thẳng ID của mốc mentor duty là ghi
lịch trực của nhóm khác vào lịch cá nhân người không thuộc nhóm.

### 2. Bảng ánh xạ, để đồng bộ lần hai không nhân bản

`program_calendar_syncs` giữ `(user_id, program_event_id) → (calendar_id,
event_id)` cùng `approved_content_hash` — bản nội dung user đã nhìn thấy khi
bấm đồng ý. Không có bảng này thì mỗi lần bấm là một bộ event trùng nhau trong
lịch của họ.

### 3. Nguồn đổi thì hỏi lại, không tự sửa

Ban tổ chức dời Workshop 07 sau khi user đã duyệt → hash lệch → mốc đó hiện lại
ở bước xem trước với `action = update` và lý do "Ban tổ chức đã đổi mốc này sau
lần bạn duyệt". **Không** tự sửa event trong lịch của họ.

Đây là BR-09 áp nguyên văn. Tự sửa thì tiện hơn thật, nhưng nó biến lịch cá
nhân thành thứ mondaiy đổi sau lưng người dùng — đúng nỗi sợ mà nguyên tắc sản
phẩm số 6 dựng ra để tránh.

Khi user duyệt lại, hệ thống **cập nhật đúng event cũ** bằng `event_id` đã lưu,
và tăng `reapproved_count` để sau này biết luồng hỏi lại có phiền tới mức nào
trước khi tính chuyện nới.

### 4. Event bị user xóa thì không dựng lại

`CalendarEventNotFoundError` khi cập nhật → đánh dấu `status =
removed_by_user`, báo trong `skipped`, không tạo mới. User xóa một event là một
quyết định; dựng lại im lặng là ghi đè quyết định đó.

### 5. Hạn daily không nằm trong mặc định

Mặc định đồng bộ `custom` (workshop, office hour), `gate_deadline`,
`weekly_deadline`. Hạn daily lặp 40 ngày liên tục — đổ hết vào lịch cá nhân là
phá lịch của user chứ không giúp họ. Muốn có thì chọn tường minh ở bước xem
trước. Trần một lần đồng bộ là 60 mốc, giới hạn của việc "user thật sự nhìn qua
danh sách trước khi bấm", không phải giới hạn kỹ thuật.

### 6. Giữ nguyên cổng mức A

Cả hai endpoint gọi `reconcile_program_access` rồi từ chối 403 nếu không phải
mức A, kèm lý do và cách sửa. Mức B/C không có gì để đồng bộ.

### 7. Ghi có nhãn, và hỏng một mốc không làm hỏng cả lần đồng bộ

Tiêu đề ghi sang Google mang tiền tố `[Chương trình] ` để user phân biệt được
với sự kiện họ tự tạo — cần khi họ muốn dọn hàng loạt. Mốc nào ghi hỏng thì vào
`skipped` kèm lý do; im lặng bỏ qua khiến user tin lịch đã đủ trong khi không
đủ (FR-045).

## Phương án đã cân nhắc và loại

| Phương án | Lý do loại |
| --- | --- |
| Tự động đồng bộ ngay khi user đạt mức A | Ghi vào tài khoản Google của người dùng mà không hỏi — vi phạm ADR-007 khoản 1 và nguyên tắc sản phẩm số 6 |
| Đồng bộ lại tự động khi ban tổ chức đổi lịch | Vi phạm BR-09. Tiện hơn nhưng đánh đổi bằng thứ đắt nhất là niềm tin vào lịch của chính họ |
| Tạo một calendar riêng tên "Chương trình" | Cần scope tạo calendar; ADR-007 khoản 6 đã loại vì rủi ro verification của Google. Phân loại đạt được bằng tiền tố tiêu đề |
| Xuất `.ics` cho user tự import | Rẻ hơn nhưng ban tổ chức dời buổi thì bản đã import không đổi theo, và ta không biết user đang giữ bản nào |
| Cho user subscribe thẳng feed của ban tổ chức | Tươi nhất, gần như không tốn công, nhưng nằm ngoài sản phẩm, không đo được, và token feed là của từng cá nhân |
| Dùng luồng `create_productivity_item` có sẵn | Luồng đó ký HMAC cho **một** đề xuất sinh từ hội thoại. Đồng bộ là thao tác hàng loạt do user chủ động bấm, không phải agent đề xuất — ép vào đó là bóp méo cả hai |

## Hệ quả

- Học viên mức A có lịch khóa học nằm trong lịch họ thật sự dùng, và lớp nhắc
  việc của ADR-007 có dữ liệu để bám vào.
- Thêm một đường ghi vào tài khoản Google → bề mặt rủi ro tăng. Bù lại, đường
  này không có nhánh nào chạy mà không có danh sách ID do user gửi lên.
- Luồng hỏi lại mỗi khi ban tổ chức đổi lịch sẽ gây phiền nếu ban tổ chức đổi
  nhiều. `reapproved_count` là số liệu để quyết định có nới hay không — nới thì
  phải sửa BR-09 bằng ADR mới, không sửa lặng lẽ trong code.
- Chưa có Undo cho thao tác đồng bộ hàng loạt. `/calendar/operations/{id}/undo`
  hiện chỉ phục vụ thao tác đơn lẻ trên lưới lịch. Đây là khoảng trống đã biết,
  ghi ra để không tưởng là đã có.
- Giao diện nằm trong trang Lịch của học viên. Trang đó vẫn còn danh sách sự
  kiện minh hoạ từ bản dựng cũ; panel đồng bộ là phần duy nhất đã nối backend
  thật, và có chú thích ngay trong mã để lần dọn sau không nhầm.

## Đã hiện thực theo quyết định này

| Thành phần | Đường dẫn |
| --- | --- |
| Bảng ánh xạ | `src/models/program_calendar_sync.py` |
| Dựng kế hoạch, kiểm lại phía máy chủ | `src/services/program_calendar_sync.py` |
| Hai endpoint preview/apply | `src/api/calendar.py` |
| Schema request/response | `src/models/schemas.py` |
| Giao diện học viên | `client/web-app/src/components/calendar/ProgramSyncPanel.tsx` · `src/lib/programCalendarApi.ts` · gắn trong `src/pages/CalendarPage.tsx` |
| Chuỗi hiển thị EN/VI | `client/web-app/src/i18n/translations.ts` (`programSync`) |
| Kiểm thử | `tests/test_api/test_program_calendar_sync.py` · `client/web-app/tests/ProgramSyncPanel.test.tsx` · `tests/programSyncI18n.test.ts` |

## Việc phải làm để quyết định này có hiệu lực

| # | Việc | Người phụ trách |
| --- | --- | --- |
| 1 | Cập nhật PRD: thêm hai endpoint vào whitelist, nêu rõ đây là ghi do user khởi tạo | Thái Hoài An |
| 2 | ~~Màn hình xem trước~~ — đã dựng; còn lại là rà thiết kế và kiểm thử với người dùng thật | Lê Thị Yến Nhi |
| 3 | ~~Ca kiểm thử đọc chéo người dùng~~ — đã có trong `tests/test_api/test_program_calendar_sync_boundaries.py` | Nguyễn Đức Dũng |
| 4 | Quyết định có làm Undo cho đồng bộ hàng loạt không | Nguyễn Văn Phong |
