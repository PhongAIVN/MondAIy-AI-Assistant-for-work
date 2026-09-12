# Golden Dataset cho Pipeline Fetch, Normalize và Filter (fetch_norm_filter)

Bộ dữ liệu này được xây dựng nhằm mục đích kiểm tra và đánh giá chất lượng (quality validation) của các tầng thu thập (Fetch), chuẩn hóa (Normalize) và lọc dữ liệu (Filter) cho hai cổng kết nối chính là **Gmail (Google)** và **Discord**.

## 1. Cấu trúc thư mục

```text
eval/golden_dataset/fetch_norm_filter/
├── README.md              # Tài liệu hướng dẫn và mô tả chi tiết 36 test case
├── manifest.jsonl         # Danh mục tổng hợp trỏ tới các tệp fixture và expected tương ứng
├── schema/                # Các JSON Schema định nghĩa cấu trúc dữ liệu kiểm định
│   ├── manifest_schema.json
│   ├── gmail_fixture_schema.json
│   ├── gmail_expected_schema.json
│   ├── discord_fixture_schema.json
│   └── discord_expected_schema.json
├── fixtures/              # Dữ liệu thô (raw payloads) thu hoạch từ API nguồn
│   ├── gml_001.json -> gml_018.json
│   └── dsc_001.json -> dsc_018.json
└── expected/              # Dữ liệu chuẩn hóa và kết quả lọc mong muốn (ground truth)
    ├── gml_001.json -> gml_018.json
    └── dsc_001.json -> dsc_018.json
```

---

## 2. Thống kê phân bổ Test Case

| Nhóm | Số lượng Gmail | Số lượng Discord | Tổng |
| :--- | :---: | :---: | :---: |
| **Fetch happy path** | 3 | 3 | 6 |
| **Permission và scope** | 3 | 3 | 6 |
| **Normalize** | 4 | 4 | 8 |
| **Duplicate và version** | 3 | 3 | 6 |
| **Filter relevance** | 3 | 3 | 6 |
| **Error / partial coverage** | 2 | 2 | 4 |
| **Tổng** | **18** | **18** | **36** |

---

## 3. Danh sách Chi tiết 36 Test Case

### A. Nhóm Gmail (GML-001 -> GML-018)

#### 1. Fetch happy path
* **GML-001 - Email chính thức trong label được phép:** Email nằm trong nhãn `INBOX` chứa thông tin hành động. Kết quả: `accepted`, trích xuất đúng thông tin.
* **GML-002 - Email thread nhiều message:** Đồng bộ luồng email gồm nhiều thư trả lời qua lại. Kết quả: `accepted`, thu thập đầy đủ danh sách thư trong cùng một `thread_id`.
* **GML-003 - Email có attachment metadata:** Thư điện tử kèm tệp tin đính kèm. Kết quả: `accepted`, chuẩn hóa đúng thông tin người gửi kèm theo thông tin chi tiết của tệp đính kèm (tên tệp, loại MIME, dung lượng).

#### 2. Permission và scope
* **GML-004 - Email ngoài label được phép:** Email nằm trong nhãn `SPAM` hoặc `TRASH`. Kết quả: `rejected`, từ chối đưa vào pipeline.
* **GML-005 - Email sau khi consent bị revoke:** Kết nối của người dùng bị thu hồi quyền truy cập. Kết quả: `error`, quăng lỗi `GmailAPIError` báo không lấy được token.
* **GML-006 - Email thuộc mailbox user khác:** Đọc dữ liệu hòm thư không thuộc tài khoản kết nối. Kết quả: `error` chặn rò rỉ thông tin chéo người dùng (cross-user check).

#### 3. Normalize
* **GML-007 - HTML email có signature:** Thư định dạng HTML có chữ ký chân trang. Kết quả: `accepted`, làm sạch HTML và trích xuất phần văn bản thuần túy đầy đủ.
* **GML-008 - Email quoted reply:** Thư phản hồi trích dẫn lại nội dung thư cũ. Kết quả: `accepted`, giữ nguyên văn bản thô đầy đủ, chuẩn hóa phần phản hồi mới nhất.
* **GML-009 - Email timestamp UTC:** Thư sử dụng mốc thời gian chuẩn UTC. Kết quả: `accepted`, chuẩn hóa về đúng giờ ICT nhưng vẫn bảo tồn giá trị gốc trong DB.
* **GML-010 - Email thiếu timezone:** Thư bị thiếu thông tin múi giờ hoặc tiêu đề Date bị lỗi. Kết quả: `accepted`, đánh dấu trường múi giờ/thời gian gửi là `unknown`, tuyệt đối không tự ý phán đoán.

#### 4. Duplicate và version
* **GML-011 - Fetch lại cùng message:** Đọc lại thư điện tử đã tồn tại trong DB. Kết quả: `accepted` nhưng không tạo bản ghi trùng lặp (đảm bảo tính idempotent).
* **GML-012 - Cùng message ID, body đổi:** Nội dung thư bị thay đổi trên máy chủ nhưng vẫn giữ nguyên ID gốc. Kết quả: `accepted`, tạo phiên bản mới trong bảng lưu trữ lịch sử thay đổi.
* **GML-013 - Retry cùng page:** Thử lại thao tác lấy danh sách thư trên cùng một trang phân trang. Kết quả: `accepted` và đảm bảo idempotent.

#### 5. Filter relevance
* **GML-014 - Email mention trực tiếp user:** Thư đề cập trực tiếp tới tên tài khoản hoặc địa chỉ email của người dùng. Kết quả: `accepted`, đánh dấu direct mention.
* **GML-015 - Email toàn cohort:** Thư gửi tới địa chỉ nhóm chung (mailing list). Kết quả: `accepted`.
* **GML-016 - Email marketing không liên quan:** Các thư quảng cáo, ưu đãi không có hành động. Kết quả: `rejected` bị loại ở tầng Filter (score = 0).

#### 6. Error / partial coverage
* **GML-017 - Gmail API timeout giữa pagination:** Đang phân trang thì gặp sự cố mạng/timeout ở trang tiếp theo. Kết quả: `accepted` và ghi nhận một phần dữ liệu đã tải được (partial coverage), báo lỗi.
* **GML-018 - Source URL không mở được:** Đường link dẫn tới thư bị lỗi cấu trúc hoặc không mở được. Kết quả: `rejected` loại khỏi pipeline tin cậy hoặc đánh dấu cần review.

---

### B. Nhóm Discord (DSC-001 -> DSC-018)

#### 1. Fetch happy path
* **DSC-001 - Message trong #announcements:** Tin nhắn trong kênh thông báo chính thức. Kết quả: `accepted`.
* **DSC-002 - Message trong channel team được phép:** Tin nhắn trao đổi công việc trong kênh của đội ngũ được quyền đồng bộ. Kết quả: `accepted`.
* **DSC-003 - Message có attachment và link:** Tin nhắn Discord chứa cả đường dẫn URL bên ngoài lẫn tệp tải lên. Kết quả: `accepted`, trích xuất metadata và liên kết.

#### 2. Permission và scope
* **DSC-004 - Message trong channel ngoài allow-list:** Tin nhắn thuộc kênh chung hoặc kênh giải trí bị loại trừ. Kết quả: `rejected` loại bỏ ngay lập tức.
* **DSC-005 - Message sau khi channel permission bị revoke:** Kênh chat bị khóa quyền xem sau khi đã thiết lập. Kết quả: `error` báo lỗi phân quyền.
* **DSC-006 - Message từ server khác:** Tin nhắn phát sinh từ một máy chủ (guild) lạ ngoài tầm quản lý. Kết quả: `rejected` từ chối lưu trữ.

#### 3. Normalize
* **DSC-007 - Markdown, mention và emoji:** Tin nhắn sử dụng nhiều định dạng chữ in đậm, nhắc nhở `@User` và emoji động. Kết quả: `accepted`, chuyển đổi định dạng và phân giải ID mention về tên hiển thị chuẩn xác.
* **DSC-008 - Message reply:** Tin nhắn dạng trả lời một tin nhắn cụ thể khác. Kết quả: `accepted`, lưu giữ mối liên kết cha-con giữa hai tin nhắn.
* **DSC-009 - Message edited:** Tin nhắn đã qua chỉnh sửa nội dung. Kết quả: `accepted`, cập nhật đúng giá trị trường thời gian chỉnh sửa mới nhất `source_updated_at`.
* **DSC-010 - Message bị deleted:** Tin nhắn nguồn bị xóa bỏ hoàn toàn. Kết quả: `rejected` loại bỏ khỏi factual claim và cập nhật biên nhận quét (receipt).

#### 4. Duplicate và version
* **DSC-011 - Fetch lại cùng message:** Đọc lại tin nhắn cũ từ API. Kết quả: Idempotent, không nhân đôi dòng dữ liệu.
* **DSC-012 - Edited message cùng ID:** Tin nhắn được chỉnh sửa gửi lại cùng một ID. Kết quả: `accepted`, sinh phiên bản mới lưu trữ lịch sử sửa đổi.
* **DSC-013 - Gateway/event retry:** Nhận trùng tin nhắn gửi lại do sự cố kết nối gateway. Kết quả: Idempotent.

#### 5. Filter relevance
* **DSC-014 - User được mention:** Tin nhắn đề cập đích danh ID người dùng. Kết quả: `accepted`, xác định đúng direct mention.
* **DSC-015 - Announcement toàn cohort:** Thông báo nhắc nhở diện rộng sử dụng `@everyone` hoặc `@here`. Kết quả: `accepted`.
* **DSC-016 - Casual chat không liên quan:** Đoạn hội thoại tán gẫu phiếm của học viên. Kết quả: `rejected` do không chứa tín hiệu công việc cần làm (score = 0).

#### 6. Error / partial coverage
* **DSC-017 - Discord rate limit:** Gặp lỗi 429 Too Many Requests khi gọi API. Kết quả: `error`, tạm dừng sync và thực hiện cơ chế retry-after mà không đánh mất dấu con trỏ đồng bộ (cursor).
* **DSC-018 - Một page/channel lỗi, channel khác thành công:** Đồng bộ đa kênh, kênh mật bị lỗi nhưng kênh thường vẫn hoàn thành. Kết quả: `accepted` cho các kênh thành công, đánh dấu `partial coverage` và log chi tiết lỗi kênh hỏng.

---

## 4. Quy tắc Kiểm định (Validation Rules)

Khi viết hoặc cập nhật các tệp tin trong dataset, phải tuân thủ các quy tắc sau:

1. **Schema Validation:** Toàn bộ file JSON trong thư mục `fixtures/` và `expected/` phải khớp 100% với JSON Schema tương ứng nằm ở thư mục `schema/`.
2. **Khớp ID:** Mọi trường `id` trong manifest.jsonl, tên file trong fixtures/expected, và trường `id` bên trong tệp JSON mong đợi phải đồng bộ nhất quán.
3. **Immutability:** Tránh sửa đổi các test case đã ổn định trừ phi logic hệ thống thay đổi lớn. Mỗi thay đổi phải cập nhật lại tài liệu này.
