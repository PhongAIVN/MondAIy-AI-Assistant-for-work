# Phân tích use case bộ golden dataset mondAIy v2

## 1. Vấn đề của bộ cũ

Bộ cũ có 60 email nhưng `user_input` bị cố định ở một intent: “tóm tắt email và trích xuất task”. Như vậy RAGAS đo được khả năng đọc email, nhưng chưa đo được mondAIy có hoạt động như một thư ký AI cá nhân hay không.

## 2. Mô hình use case cần kiểm thử

| Nhóm use case | Câu hỏi đại diện | Năng lực cần đo |
|---|---|---|
| Daily overview | Hôm nay tôi cần chú ý gì? | Gộp nhiều bằng chứng thành danh sách việc |
| My tasks | Các nhiệm vụ đang giao cho tôi là gì? | Lọc đúng owner, không nhầm người nhận |
| Deadline | Việc nào sắp đến hạn? | Trích xuất và sắp thứ tự theo mốc thời gian |
| Priority | Việc nào làm trước? | Hiểu urgency, deadline, dependency |
| Next action | Bước tiếp theo là gì? | Chuyển thông tin thành hành động cụ thể |
| Waiting/dependency | Tôi đang chờ ai hoặc dữ liệu gì? | Nhận diện dependency và việc có thể làm trong lúc chờ |
| Constraints | Được làm gì, không được làm gì? | Giữ nguyên scope, điều kiện và prohibited action |
| Scope | Phần việc của tôi đến đâu? | Phân biệt trách nhiệm và phần của người khác |
| Changes | Có yêu cầu nào bị thay đổi/ghi đè? | Chọn instruction mới nhất, giữ phần không đổi |
| Action brief | Checklist thực thi là gì? | Tạo checklist bám evidence, không tự thêm việc |

## 3. Cấu trúc mỗi case

- `user_input`: câu hỏi tự nhiên theo intent của trợ lý cá nhân.
- `retrieved_contexts`: bằng chứng mà hệ thống truy xuất được.
- `reference_contexts`: bằng chứng chuẩn để đánh giá retrieval.
- `reference`: task chuẩn hóa, owner, deadline, priority, scope, dependency và chính sách abstain.
- `metadata.use_case`: nhãn intent để phân tích lỗi theo nhóm.
- `metadata.source_item_ids`: các email được phép dùng để trả lời.

## 4. Coverage hiện tại

Bộ v2 có 60 case, trong đó 20 case là truy vấn tổng hợp nhiều email và 40 case là truy vấn theo một email với nhiều intent khác nhau. Evidence vẫn lấy nguyên từ CSV Gmail chuẩn, không bịa nội dung email mới.

Các metric RAGAS được bật cho mọi case: `faithfulness`, `context_precision`, `context_recall`, `answer_relevancy`, `answer_correctness`.

## 5. Giới hạn cần bổ sung ở vòng tiếp theo

Vì nguồn đầu vào hiện chỉ là Gmail, bộ này chưa kiểm thử được dữ liệu Calendar, Jira, Discord và VLearn. Muốn đánh giá đầy đủ thư ký AI cá nhân cần bổ sung golden contexts cho:

1. Lịch hôm nay và lịch trống.
2. Nhiệm vụ Jira theo trạng thái/assignee.
3. Thông báo Discord có mức chính thức khác nhau.
4. Deadline trong VLearn hoặc khung chương trình.
5. Xung đột giữa nguồn chính thức và nguồn tham khảo.

Khi có các fixture đó, giữ nguyên taxonomy và thêm `source`, `authority`, `event_time`, `observed_at`, `coverage` và `citation` vào reference để kiểm tra provenance đúng với PRD.

## 6. Nguyên tắc chấm bắt buộc

- Không có bằng chứng thì trả lời “chưa xác định”, không đoán owner hoặc deadline.
- Không biến câu hỏi “hôm nay có gì” thành bản tóm tắt từng email rời rạc.
- Không làm mất điều kiện, ngoại lệ, dependency hoặc hành động bị cấm.
- Không tự gửi email, tạo lịch hoặc ghi dữ liệu bên ngoài; chỉ đề xuất/draft và chờ xác nhận.
