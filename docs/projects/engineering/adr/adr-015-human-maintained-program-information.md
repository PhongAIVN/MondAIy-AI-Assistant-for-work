# ADR-015 — Kho thông tin chương trình do đội ngũ duyệt và hàng chờ trả lời có đồng ý

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Coding agent, theo yêu cầu ngày 2026-08-16 của Thái Hoài An |
| Reviewers | Nguyễn Văn Phong (Technical Lead), Lê Thị Yến Nhi (UI/UX Lead), Nguyễn Đức Dũng (PO/QC) |
| Last updated | 2026-08-16 |
| Related | [ADR-007](adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [ADR-008](adr-008-lich-chuong-trinh-tu-ics-feed.md) · [ADR-010](adr-010-trang-quan-tri-lich-chuong-trinh.md) · [PRD](../../product/prd.md) |

## Bối cảnh

Agent hiện đọc được lịch ICS và Discord, nhưng hai nguồn này không thay thế một
kho câu trả lời mà đội ngũ có thể sửa ngay. Khi AI chưa có bằng chứng, người
dùng cũng chưa có đường chủ động chuyển đúng câu hỏi cho đội ngũ; cách gửi toàn
bộ hội thoại sẽ vượt nhu cầu và tăng rủi ro riêng tư.

Nhu cầu vận hành là: đội ngũ soạn, duyệt và phát hành thông tin; agent ưu tiên
bản đã duyệt; người dùng có thể tự sửa câu hỏi rồi đồng ý chia sẻ; sau khi đội
ngũ trả lời, yêu cầu được nối tới đúng phiên bản đã phát hành.

## Quyết định đề xuất

### 1. Đầu mục ổn định, nội dung có phiên bản bất biến

`ProgramInformationItem` giữ cohort, category, visibility, trạng thái và hai
con trỏ `latest_version`/`published_version`. Mỗi lần sửa tạo một
`ProgramInformationVersion` mới; không sửa hoặc xoá dòng phiên bản bằng ORM.

Tách hai con trỏ để đội ngũ soạn bản tiếp theo mà bản đang phục vụ người dùng
không thay đổi. Phát hành là thao tác rõ ràng đưa `published_version` tới bản
mới nhất. Update và publish/archive đều dùng `expectedVersion`; bản cũ nhận 409
thay vì âm thầm ghi đè công việc của người khác.

### 2. Phạm vi do server cấp, không lấy từ prompt hoặc client

- Cohort quản trị và tra cứu lấy từ `PROGRAM_COHORT_SLUG`.
- Nội dung `public` đọc được không đăng nhập; truy vấn này không bao giờ trả
  `program`.
- Nội dung `program` chỉ cho tài khoản active, access level A.
- Tool agent giữ access level/cohort trong ContextVar, không đưa hai giá trị đó
  vào chữ ký tool. Câu lệnh trong prompt vì vậy không thể tự mở cohort khác.
- Chỉ bản `published`, đúng `published_version` và còn trong cửa sổ hiệu lực
  được đưa vào Q&A.

### 3. Nội dung lưu dưới dạng văn bản thuần và có bằng chứng

Title, body và aliases được loại markup trước khi lưu. Source URL chỉ nhận HTTPS.
Mỗi phiên bản có SHA-256 của nội dung chuẩn hoá. Tool trả source, version,
updatedAt và contentHash để câu trả lời có thể chỉ rõ bằng chứng đã dùng.

### 4. Chuyển người xử lý phải có đồng ý tường minh

Endpoint fallback chỉ nhận `sharedQuestion` người dùng đang nhìn thấy/chỉnh sửa
và `consentToShare=true`. Không nhận conversation id, lịch sử chat, prompt hệ
thống hay hồ sơ. DB vẫn giữ requester id để sau này báo đúng người, nhưng hàng
chờ admin không trả requester id, email, profile hoặc hội thoại.

Admin xử lý yêu cầu bằng cách nối nó tới một item đang phát hành ở cùng cohort.
Audit chung chỉ ghi trạng thái, id item và version; không chép câu hỏi/nội dung.

### 5. Thông báo là bước sau phát hành, không nằm trong transaction nội dung

Khi bản mới được phát hành hoặc yêu cầu được giải quyết, lớp notification sẽ
nhận một sự kiện chỉ chứa item id/version/category/cohort và tự lọc người nhận.
Không gửi body câu hỏi vào payload notification. Dedupe phải theo
`user + item + version + channel`, tôn trọng preference/quiet hours của ADR-007.

Lane hiện tại chưa nối notification để tránh tự chọn recipient policy khi chưa
có mô hình membership cohort ngoài access level A.

## Phương án đã cân nhắc

| Phương án | Lý do không chọn |
| --- | --- |
| Dùng Discord làm nguồn trả lời duy nhất | Thảo luận không phải bản đội ngũ duyệt và khó sửa tức thời |
| Ghi đè một dòng nội dung | Không dựng lại được bản AI đã dùng; hai admin dễ mất thay đổi |
| Tự lưu câu AI không trả lời được | Không có đồng ý, có thể chép PII hoặc toàn bộ hội thoại |
| Cho client truyền cohort/access level | Prompt hoặc request giả có thể mở rộng phạm vi |
| Phát hành xong gửi push ngay trong request | Lỗi kênh gửi có thể rollback nội dung hoặc gửi lặp |

## Hệ quả

- Admin có quy trình nháp/phát hành và lịch sử nội dung thật.
- Q&A có nguồn ổn định hơn, nhưng cần đăng ký router/model/scope trong composition
  root trước khi chạy production.
- Bảng phiên bản tăng theo mỗi lần sửa; không hard-delete giúp audit nhưng cần
  chính sách retention nếu quy mô lớn.
- Search SQL `ILIKE` phù hợp pilot; cần FTS/hybrid retrieval nếu số mục tăng lớn.
- Việc giữ requester id là dữ liệu cá nhân tối thiểu có mục đích; cần đưa vào
  delete/export account lifecycle trước khi ADR được Approved.

## Open decisions cần Technical Lead/DRI chốt

1. Recipient của thông báo là mọi user level A ở cohort cấu hình hay membership
   tường minh; access level A hiện chưa mang cohort id trên từng user.
2. Khi một câu hỏi được resolve, chỉ báo requester hay cho phép admin chọn báo
   rộng hơn cho cả cohort.
3. Có cần role `program_editor` nhỏ hơn `admin` hay không.
4. Chọn outbox/job hiện có nào để publish event và retry đa kênh mà không gửi lặp.
5. Chính sách retention/delete/export cho `ProgramInformationRequest.requester_id`.

## Điều kiện để chuyển Approved

- Technical Lead chốt năm open decision trên và contract notification.
- PM cập nhật PRD về ngoại lệ nội dung chương trình và consent fallback.
- UI/UX Lead duyệt trạng thái draft/published/conflict và wording đồng ý.
- QC có test xuyên suốt: draft không lọt, B/C bị từ chối, stale update 409,
  không conversation/profile trong request/admin/audit, notification dedupe.
