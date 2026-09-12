# Bản giới thiệu ngắn: mondaiy

| Thuộc tính | Giá trị |
| --- | --- |
| Tên sản phẩm | mondaiy |
| Định vị | Trợ lý AI cá nhân làm việc trên nguồn người dùng cho phép |
| Trạng thái | Đang lấy ý kiến để hoàn thiện |
| Người chịu trách nhiệm | Thái Hoài An (PM) |
| Người phản biện | Mentor, Tech Lead, UI/UX Lead, PO/QC |
| Cập nhật lần cuối | 2026-08-04 |
| Nguồn chuẩn | Có, gồm định hướng sản phẩm, ranh giới sáu tuần và tiêu chí thành công |
| Tài liệu liên quan | [PRD](../../product/prd.md) · [User story map](../../product/user-story-map.md) · [Wireframe](../../design/wireframe-ui-flow.md) · [ADR-001](../../engineering/adr/adr-001-platform-core-program-navigator-vertical.md) |

> **Bản đóng băng Gate 1.** Bản sống được cập nhật tại
> [`product/one-page-brief.md`](../../product/one-page-brief.md). Không sửa file này.

## Sản phẩm là gì

mondaiy đọc các nguồn người dùng cấp quyền, gồm Calendar, Jira, Discord, VLearn
và Gmail, rồi làm bốn việc:

1. Lưu thông tin kèm nguồn gốc và lịch sử thay đổi.
2. Chỉ ra việc cần chú ý, việc vừa đổi, chỗ hai nguồn nói khác nhau.
3. Trả lời câu hỏi kèm link nguồn để người dùng tự kiểm chứng.
4. Soạn sẵn lời nhắc hoặc sự kiện lịch, người dùng sửa rồi mới xác nhận.

Không phải chatbot kiến thức tổng quát. mondaiy chỉ nói về những gì nó đọc được
từ nguồn đã cấp quyền, và luôn chỉ ra được nguồn đó.

## Vấn đề

Học viên trong một khóa học sáu tuần nhận thông tin từ nhiều nơi: hạn nộp trên
trang chương trình, yêu cầu mentor nói trong buổi họp, phân công trong tài liệu
nhóm, lịch cá nhân ở ứng dụng khác.

Khó không nằm ở chỗ tìm thông tin, mà ở chỗ phán đoán:

- Bản nào mới nhất?
- Đây là quyết định chính thức hay chỉ là một câu trong Discord?
- Việc này có phải của tôi không?
- Lời nhắc tôi đặt tuần trước theo hạn cũ hay hạn mới?
- Hai nguồn nói khác nhau thì tin nguồn nào?

Chatbot thông thường bắt người dùng dán lại thông tin và trả lời không có nguồn.
Công cụ lưu trữ chỉ giúp tìm lại tài liệu. Công cụ tự động hóa tạo hành động
nhanh nhưng dễ sai khi thông tin chưa rõ.

## Người dùng

Pilot gồm 5–10 học viên và một mentor hoặc quản trị viên, trong một khóa học có
nguồn, nhiệm vụ và hạn chót thật.

| Nhóm | Cần gì |
| --- | --- |
| Học viên | Biết việc của mình tuần này, biết cái gì vừa đổi, không phải rà lại từng nguồn |
| Mentor / ban tổ chức | Giữ nguồn chính thức đúng, thấy chỗ học viên đang vướng |

Hai nhóm còn lại từng nêu trong bản trước, là trưởng nhóm dự án và người dùng
doanh nghiệp, thì đã bỏ khỏi phạm vi vì nhóm chúng em chưa phỏng vấn ai thuộc
hai nhóm đó.

## Năm việc mondaiy làm

| UC | Việc |
| --- | --- |
| UC-01 | Gộp việc và hạn chót từ nhiều nguồn thành một danh sách có dẫn nguồn |
| UC-02 | Chỉ ra mục mới, mục vừa đổi, kèm phiên bản trước và sau |
| UC-03 | Đặt hai nguồn mâu thuẫn cạnh nhau, nêu rõ nguồn nào có thẩm quyền cao hơn |
| UC-04 | Trả lời câu hỏi từ dữ liệu đã kết nối, kèm link về nguồn |
| UC-05 | Soạn sẵn nhiệm vụ hoặc sự kiện lịch để người dùng duyệt |

## Hành trình dùng để trình diễn

```text
Nguồn có dữ liệu mới
  → mondaiy đồng bộ, lưu phiên bản
  → phát hiện thay đổi hoặc mâu thuẫn
  → bản tóm lược hiện đúng phần liên quan tới vai trò người dùng
  → người dùng hỏi, nhận câu trả lời có nguồn
  → soạn bản nháp lịch, sửa, xác nhận
```

## Nguyên tắc

- Không có nguồn thì không khẳng định là sự thật.
- Bằng chứng gốc không bị ghi đè. Thay đổi tạo bản mới.
- Thảo luận, quan sát và suy luận không tự trở thành thông tin đã xác nhận.
- Người dùng tự khai thì tin người dùng, không tin suy luận của hệ thống.
- Hạn chót, người phụ trách, trạng thái hoàn thành: không có bằng chứng thì để
  trống, không đoán.
- Kiểm tra quyền ở cả bốn chỗ: đồng bộ, tìm kiếm, hiển thị, mở nguồn.
- Nguồn lỗi thì phải nói rõ là thông tin chưa đầy đủ.
- Mọi hành động ra bên ngoài đều qua xem trước, sửa, xác nhận.
- Người dùng ngắt được từng nguồn, xóa được thông tin đã ghi nhớ.

## Phạm vi sáu tuần

| Phải chứng minh được | Bằng chứng |
| --- | --- |
| Kết nối chỉ đọc tới Calendar, Jira, Discord, VLearn, Gmail | Người dùng thấy quyền, trạng thái và lần đồng bộ cuối của từng nguồn |
| Đồng bộ tăng dần, chống trùng, lưu phiên bản | Khởi động lại không mất item; gửi lại không tạo bản trùng |
| Lưu bằng chứng và lịch sử thay đổi | Mọi thông tin ghi nhớ chính thức truy được về bằng chứng |
| Bản tóm lược hằng ngày và hỏi đáp có dẫn nguồn | Mọi khẳng định có nguồn; thiếu bằng chứng thì từ chối trả lời |
| Lời nhắc trong ứng dụng và mẫu tạo sự kiện `.ics` | Không tạo hành động trước khi xác nhận; giờ mơ hồ không tự điền |
| Pilot 5–10 học viên, kiểm thử tải 50 người | Có số liệu, phân loại lỗi, phản hồi và quyết định cho giai đoạn sau |

### Không làm trong sáu tuần

- Theo dõi màn hình, lịch sử duyệt web, nội dung trang web bất kỳ.
- Thu thập mật khẩu hoặc cookie đăng nhập.
- Chatbot kiến thức tổng quát, tìm kiếm toàn mạng.
- Bot tham gia họp rồi tự hành động.
- Ghi dữ liệu sang ứng dụng ngoài mà không hỏi.
- Hệ thống nhiều tác nhân tự phối hợp.

### Để sau, khi độ tin cậy đã chứng minh được

Đồng bộ nhiều tài khoản, thêm nguồn mới, nhập transcript họp, kết nối đọc–ghi
trực tiếp với ứng dụng lịch, mở sang tình huống dùng khác, phát hành rộng.

## Đo thế nào

Nhóm chúng em chia làm hai loại chỉ số và **không đặt ngưỡng phần trăm cho loại thứ hai**,
vì pilot chỉ 5–10 người, một người đổi ý thì kết quả nhảy 10–20 điểm phần trăm.

**Loại 1 là loại kiểm chứng được bằng bộ dữ liệu kiểm thử.** Đây là ngưỡng cứng:

| Chỉ số | Ngưỡng |
| --- | --- |
| Khẳng định đã công bố có nguồn mở lại được | 100% |
| Thông tin ghi nhớ chính thức có bằng chứng | 100% |
| Bản ghi trùng sau khi gửi lại | 0 |
| Item bị mất sau khi khởi động lại | 0 |
| Tự tạo hạn chót hoặc người phụ trách không có nguồn | 0 |
| Hành động xảy ra trước khi người dùng xác nhận | 0 |
| Người dùng đọc được dữ liệu của người khác | 0 |

**Loại 2 là loại quan sát trong pilot, báo cáo bằng số tuyệt đối.** Ghi rõ *bao nhiêu
trên tổng bao nhiêu người*, kèm lý do rút ra từ phỏng vấn cuối pilot:

- Tỷ lệ hoàn thành công việc đến hạn trong tuần, so với baseline đo trước pilot.
- Số người mở bản tóm lược, theo ngày.
- Số người xác nhận ít nhất một lời nhắc hoặc bản nháp lịch.
- Đánh giá hữu ích cho từng câu trả lời.

Bản trước đặt các ngưỡng 70%, 60%, 30% cho nhóm chỉ số này. Nhóm chúng em bỏ
các ngưỡng đó vì chưa phỏng vấn người dùng nào nên không có cơ sở chọn con số,
và cỡ mẫu 5–10 người không đủ để một tỷ lệ phần trăm nói lên điều gì.

Chỉ số chính vẫn là **tỷ lệ hoàn thành công việc trong tuần**. Thành công nghĩa
là tỷ lệ này cao hơn baseline, báo cáo kèm số trước, số sau và mức chênh.

## Điều nhóm chúng em đã kiểm chứng và điều chưa

**Nhóm chúng em đã làm:** khảo sát 13 sản phẩm cùng nhóm, đọc tài liệu chính
thức của từng sản phẩm, đối chiếu để tìm khoảng trống. Kết luận rút ra: các sản
phẩm hiện có mạnh ở một trong ba việc là tìm và tóm tắt, quản lý deadline hoặc
vận hành khóa học, nhưng chưa sản phẩm nào đọc nhiều nguồn, hiểu cấu trúc chương
trình, phát hiện thay đổi và chuyển thành việc cá nhân có dẫn nguồn.

**Nhóm chúng em chưa làm:** phỏng vấn hoặc khảo sát người dùng thật. Mọi phát
biểu về nỗi đau của học viên trong tài liệu này là giả định của nhóm chúng em,
dựa trên trải nghiệm chính nhóm chúng em khi tham gia khóa học. Kiểm chứng nằm
trong kế hoạch pilot.

## Quyết định đã chốt

1. mondaiy là trợ lý AI cá nhân; trợ lý hỗ trợ học viên là tình huống dùng đầu
   tiên để kiểm chứng.
2. Pilot dùng một khóa học, múi giờ mặc định `Asia/Ho_Chi_Minh`.
3. P0 chỉ dùng connector chỉ đọc. Không theo dõi màn hình hay lịch sử duyệt web.
4. Nội dung cuộc họp và bot họp nằm ngoài phạm vi sáu tuần.
5. Mẫu tạo sự kiện và tệp `.ics` thuộc P0. Kết nối đọc–ghi trực tiếp với lịch
   thuộc giai đoạn sau.
6. PostgreSQL là nơi lưu chính. Giải pháp ghi nhớ mã nguồn mở đi qua một lớp
   trung gian để thay được mà không sửa toàn bộ sản phẩm.
7. Một thành phần trung tâm điều phối công cụ. Không xây nhiều trợ lý tự phối
   hợp với nhau.

## Quyết định còn mở

1. Khóa học, người thử nghiệm và nguồn thật sẽ dùng.
2. Thời gian lưu dữ liệu nguồn và lịch sử trò chuyện.
3. Mô hình ngôn ngữ và mô hình embedding, chọn theo chất lượng và chi phí đo
   được.
4. Ai xử lý câu hỏi chưa trả lời được, thông tin mâu thuẫn và sự cố trong pilot.
5. Connector nào đủ ổn định để đưa vào pilot.
