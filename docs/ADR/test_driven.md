# ADR-003: Kiểm chứng kiến trúc Connector-first, có bằng chứng cho Program Navigator của mondaiy P0

## Status
Proposed

## Date
2026-08-06

## Owner
Nguyễn Đức Dũng

## Reviewers
Team P004
---

## 1. Problem Statement

mondaiy cần một kiến trúc đầu tiên có thể đưa vào thử nghiệm, đủ để chứng minh sản phẩm giúp học viên hành động từ thông tin chương trình bị phân mảnh, nhưng không biến thành một trợ lý giám sát cá nhân quá rộng và thiếu an toàn.

Vấn đề cốt lõi không chỉ là trả lời câu hỏi. Học viên nhận nhiệm vụ, hạn chót, yêu cầu của mentor, cập nhật nhóm, email thông báo và lịch sự kiện ở nhiều nguồn khác nhau. Họ cần biết:

- có gì mới;
- có gì thay đổi từ bản tóm lược gần nhất;
- việc nào cần chú ý trong tuần này;
- nguồn nào có thẩm quyền hơn;
- hai nguồn có đang mâu thuẫn không;
- bước tiếp theo nên làm là gì.

Chatbot thông thường bắt người dùng dán lại ngữ cảnh và có thể trả lời không kèm bằng chứng. Công cụ chỉ đồng bộ dữ liệu thì tạo thêm một kho lưu trữ nhưng không giúp ra quyết định. Trợ lý ưu tiên tự động hóa có thể tạo nhắc việc hoặc sự kiện lịch quá sớm, nhất là khi thông tin nguồn còn thiếu hoặc mâu thuẫn.

Vì vậy, quyết định kiến trúc cần kiểm chứng là:

> mondaiy có thể tạo bản tóm lược hằng ngày, hỏi đáp và bản nháp hành động đủ hữu ích, có căn cứ, chỉ bằng connector chỉ đọc do người dùng cấp quyền, kho dữ liệu đặt bằng chứng lên trước và yêu cầu người dùng xác nhận tường minh cho mọi hành động ra bên ngoài hay không?

---

## 2. Context

mondaiy được định vị là trợ lý AI cá nhân chỉ làm việc trên các nguồn người dùng đã cho phép. Cái đầu tiên là Program Navigator cho một khóa học sáu tuần. Phần lõi dùng lại được là Personal Context Engine.

Trong P0, mondaiy phải đọc từ các nguồn đã cấp quyền, lưu bằng chứng và lịch sử phiên bản, phát hiện thay đổi hoặc mâu thuẫn, trả lời câu hỏi kèm trích dẫn, và chuẩn bị bản nháp nhắc việc hoặc lịch để người dùng xem lại.

### Baseline sản phẩm hiện tại

```text
Nguồn người dùng cấp quyền
  ├── Calendar
  ├── Jira
  ├── Discord
  ├── VLearn
  └── Gmail
        ↓
Connector chỉ đọc
        ↓
Kho bằng chứng và phiên bản
        ↓
Đề xuất ghi nhớ và mục thông tin có cấu trúc
        ↓
Bản tóm lược / hỏi đáp có căn cứ / bản nháp hành động
        ↓
Người dùng xem trước, sửa và xác nhận
```

### Ràng buộc thiết kế và sản phẩm hiện tại

- P0 là trải nghiệm web app, không phải desktop app.
- Connector trong P0 chỉ đọc.
- Mọi khẳng định về sự thật trong bản tóm lược hoặc câu trả lời phải trỏ về bằng chứng mà người dùng có quyền mở.
- Bằng chứng không bị ghi đè; nguồn thay đổi thì tạo phiên bản mới thay vì sửa bản cũ.
- Nguồn mâu thuẫn phải được hiển thị như mâu thuẫn, không được để AI âm thầm tự chọn một bên.
- Tạo hành động phải đi qua bản nháp trước. Người dùng phải xem trước, sửa và xác nhận tường minh trước khi có nhắc việc, `.ics` handoff hoặc calendar handoff.
- P0 không theo dõi màn hình, lịch sử duyệt web, trang web bất kỳ, cookie, mật khẩu hoặc nội dung cuộc họp.
- Việc extension có đọc ngữ cảnh trang web hay không là quyết định mở ngoài P0 và cần ADR riêng nếu mở lại.

---

## 3. Goals

- Chứng minh connector chỉ đọc đủ để tạo bản tóm lược hằng ngày hữu ích cho học viên.
- Chứng minh mọi câu trả lời về sự thật đều có thể dựa trên bằng chứng nguồn và người dùng mở lại được.
- Giữ lịch sử nguồn để mondaiy giải thích được vì sao trước đây từng hiển thị hạn chót, người phụ trách hoặc trạng thái khác.
- Phát hiện thay đổi và mâu thuẫn nguồn mà không ghi đè phiên bản trước.
- Cho phép người dùng đi từ thông tin sang hành động qua luồng an toàn: bản nháp → xem trước → sửa → xác nhận.
- Ngăn rò dữ liệu giữa người dùng bằng owner, scope check và kiểm soát truy cập kiểu RLS.
- Giữ hệ thống thay thế được: mô hình ngôn ngữ, mô hình embedding và lớp memory có thể đổi mà không phải viết lại toàn bộ sản phẩm.
- Tạo dữ liệu đánh giá có thể chạy lại cho đồng bộ, tìm lại, grounding, xử lý mâu thuẫn và tạo bản nháp hành động.

---

## 4. Non-goals

Các mục sau nằm ngoài ADR này và ngoài phạm vi kiểm chứng P0.

- **Customize giao diện riêng cho từng người vượt quá thiết lập cơ bản.** P0 có thể hỗ trợ ngôn ngữ, giao diện sáng/tối/theo hệ thống và tùy chọn accessibility, nhưng không sinh layout, theme system hoặc giao diện cá nhân hóa riêng cho từng người.
- **Hiểu toàn bộ ngữ cảnh trên máy.** mondaiy không quan sát mọi việc người dùng làm trên máy tính, không đọc toàn bộ app đang mở, không kiểm tra file local, không theo dõi cửa sổ đang active và không suy luận hoạt động từ hệ điều hành.
- **Theo dõi màn hình và lịch sử duyệt web.** mondaiy không theo dõi màn hình, browser history hoặc các trang bất kỳ người dùng mở.
- **Thu cookie, mật khẩu hoặc session.** mondaiy không thu thập cookie đăng nhập, mật khẩu hoặc dữ liệu phiên trình duyệt.
- **Desktop application.** P0 không xây app Windows/macOS/Linux hoặc background agent chạy trên máy.
- **Mobile application.** P0 không xây native mobile app.
- **Mở rộng sang nền tảng nhắn tin.** P0 không kết nối Messenger, Zalo, Facebook, Slack hoặc nền tảng chat khác ngoài phạm vi Discord đã duyệt.
- **Tích hợp có quyền ghi.** P0 không trực tiếp gửi tin nhắn, tạo sự kiện lịch bên ngoài, cập nhật sự kiện bên ngoài hoặc xóa hành động bên ngoài nếu không có đường handoff đã xác nhận riêng.
- **Tìm kiếm web tổng quát hoặc chatbot kiến thức tổng quát.** mondaiy chỉ trả lời từ các nguồn đã kết nối và được phép, không mặc định tìm trên internet mở.
- **Meeting bot hoặc thu transcript.** P0 không tham gia họp, ghi âm hoặc tạo transcript cuộc họp.
- **Workflow nhiều agent tự trị.** P0 không xây nhiều agent tự lập kế hoạch và thực thi với nhau.


---

## 5. Constraints

| Constraint | Lý do |
|---|---|
| Thời gian build sáu tuần | Kiến trúc phải hỗ trợ một vertical slice, không phải nền tảng trợ lý quá rộng. |
| Pilot 5–10 học viên và mentor/admin | Chỉ số sản phẩm phải báo bằng số tuyệt đối khi cỡ mẫu quá nhỏ để dùng tỷ lệ ổn định. |
| Connector chỉ đọc trong P0 | Giảm rủi ro quyền riêng tư và niềm tin trước khi kiểm chứng giá trị. |
| Consent theo từng nguồn do người dùng kiểm soát | Người dùng phải kết nối, ngắt kết nối, tạm dừng thu thập và xóa dữ liệu được. |
| Bằng chứng trước ghi nhớ | Không có ghi nhớ chính thức hoặc câu trả lời sự thật nếu không có bằng chứng nguồn. |
| Không hành động ẩn | Nhắc việc và calendar handoff yêu cầu người dùng xác nhận tường minh. |
| PostgreSQL là canonical store | Gom bằng chứng, phiên bản, memory và audit vào một kiến trúc thay thế được. |
| Feature flag cho connector | Connector chưa ổn định có thể bị loại khỏi pilot mà không chặn toàn bộ sản phẩm. |
| UI copy tiếng Việt và tiếng Anh | Tài liệu pilot và thiết kế P0 phải dễ hiểu với người dùng Việt Nam, đồng thời giữ tên kỹ thuật ổn định. |
| Không tuyên bố sản phẩm thiếu căn cứ | Báo cáo pilot phải tách rõ điều đã kiểm chứng và điều còn là giả định. |

---

## 6. Decision Options

### Option A — Ưu tiên đọc ngữ cảnh trình duyệt/hệ điều hành

Xây extension hoặc local agent đọc trang đang mở, lịch sử duyệt web, trạng thái màn hình hoặc ngữ cảnh công việc hiện tại, rồi dùng AI tóm tắt người dùng đang làm gì.

**Pros**

- Có thể tạo cảm giác “cá nhân hóa” nhanh.
- Ban đầu cần ít công việc connector có cấu trúc hơn.
- Có thể trả lời rộng hơn về việc người dùng đang làm.

**Cons**

- Rủi ro quyền riêng tư cao.
- Khó giải thích đã thu gì và vì sao thu.
- Khó tạo citation và xác định thẩm quyền nguồn đáng tin cậy.
- Dễ trượt thành giám sát toàn bộ máy.
- Mâu thuẫn với ranh giới P0 và định vị xây niềm tin.

### Option B — Web app connector-first, có bằng chứng

Chỉ dùng connector chỉ đọc do người dùng cấp quyền cho Calendar, Jira, Discord, VLearn và Gmail. Lưu bằng chứng, phiên bản và metadata nguồn trong PostgreSQL. Tạo bản tóm lược, hỏi đáp và bản nháp hành động chỉ từ bằng chứng được phép.

**Pros**

- Khớp nhất với lời hứa sản phẩm: evidence-first.
- Dễ audit, cite, version và revoke hơn.
- Rủi ro quyền riêng tư thấp hơn so với đọc màn hình hoặc trình duyệt.
- Hỗ trợ phát hiện mâu thuẫn vì danh tính và thẩm quyền nguồn rõ ràng.
- Dễ kiểm thử bằng fixture xác định và golden dataset.

**Cons**

- Làm connector chậm hơn và dễ gặp lỗi phụ thuộc nguồn.
- Một phần ngữ cảnh vẫn thiếu nếu người dùng không kết nối nguồn.
- Cần mô hình dữ liệu đủ chắc trước khi UI tạo cảm giác hữu ích.
- Phải xử lý rõ trạng thái đồng bộ một phần và lỗi nguồn.

### Option C — Desktop assistant với local context engine

Xây desktop app chạy cục bộ, theo dõi file hoặc hoạt động app, rồi đồng bộ ngữ cảnh đã chọn lên cloud.

**Pros**

- Có thể hỗ trợ ngữ cảnh cá nhân giàu hơn về sau.
- Có thể hoạt động trên nhiều app mà không cần connector riêng cho từng app.

**Cons**

- Quá lớn cho sáu tuần.
- Thêm rủi ro về quyền hệ điều hành, installer, cập nhật và bảo mật local.
- Khó hỗ trợ trong pilot học viên.
- Làm lệch trọng tâm khỏi việc kiểm chứng vertical Program Navigator.

### Option D — Trợ lý dạng messaging super-app

Tập trung Messenger, Zalo, Slack, Discord và email để người dùng hỏi mondaiy ngay trong các nền tảng chat.

**Pros**

- Khớp với nơi nhiều người đang giao tiếp.
- Có thể giảm nhu cầu mở web app riêng.

**Cons**

- Bề mặt connector quá rộng.
- Consent và quyền riêng tư phức tạp.
- Hành động ghi trong messaging dễ vô tình gửi nội dung ra ngoài.
- Không trực tiếp giải quyết thẩm quyền nguồn, versioning và truy vết bằng chứng.

---

## 7. Decision

Chọn **Option B: Web app connector-first, có bằng chứng** cho P0.

Quyết định gồm năm phần:

1. **Bề mặt P0:** web app là bề mặt sản phẩm chuẩn.
2. **Ingestion P0:** connector chỉ đọc cho Calendar, Jira, Discord, VLearn và Gmail, có feature flag để chỉ connector ổn định được đưa vào pilot.
3. **Storage P0:** PostgreSQL là kho canonical cho bằng chứng, phiên bản, memory và audit.
4. **Ranh giới AI P0:** AI chỉ được tóm tắt, xếp hạng, tìm lại và tạo bản nháp từ bằng chứng được phép. AI không được trình bày claim thiếu nguồn như sự thật.
5. **Ranh giới hành động P0:** hành động là bản nháp cho tới khi người dùng xem trước, sửa và xác nhận tường minh. Calendar `.ics` hoặc handoff được phép; OAuth ghi trực tiếp để sau.

---

## 8. Hypothesis

### Primary hypothesis

Nếu mondaiy dùng kiến trúc connector-first, có bằng chứng cho vertical Program Navigator,
thì học viên sẽ hoàn thành nhiều công việc đến hạn hơn trong tuần pilot so với baseline,
vì họ nhìn thấy nhiệm vụ hiện tại, thay đổi, mâu thuẫn và bước tiếp theo từ các nguồn chương trình đã kết nối mà không phải tự rà từng nguồn.

### Technical hypothesis

Nếu mọi factual item được lưu cùng bằng chứng, danh tính nguồn, quyền truy cập và phiên bản bất biến,
thì mondaiy có thể trả lời câu hỏi và tạo bản tóm lược với 100% citation mở lại được trên bộ dữ liệu kiểm thử có phạm vi,
vì retrieval và answer generation bị giới hạn vào bằng chứng người dùng có quyền truy cập.

### Safety hypothesis

Nếu mọi hành động ra bên ngoài đều đi qua luồng bản nháp → xem trước → sửa → xác nhận,
thì mondaiy sẽ tạo 0 nhắc việc hoặc calendar handoff trước khi người dùng xác nhận tường minh,
vì AI không được gọi trực tiếp công cụ ghi.

### Privacy hypothesis

Nếu P0 tránh theo dõi màn hình, lịch sử duyệt web, đọc trang bất kỳ, cookie và desktop agent,
thì người dùng có thể hiểu và kiểm soát mondaiy đọc gì,
vì điểm dữ liệu đi vào hệ thống chỉ giới hạn ở các connector được đặt tên, có consent và trạng thái nguồn hiển thị rõ.

---

## 9. Test Plan

### 9.1 Phạm vi thí nghiệm

| Khu vực | Sẽ kiểm thử gì | Bằng chứng tạo ra |
|---|---|---|
| Đồng bộ nguồn | Fixture hoặc nguồn pilot cho Calendar, Jira, Discord, VLearn và Gmail | Biên nhận đồng bộ, số item, log lỗi, kiểm tra trùng |
| Versioning | Gửi lại cùng item, item thay đổi, item bị xóa/hủy | Lịch sử phiên bản và bản ghi supersession |
| Bản tóm lược có căn cứ | Các phần hằng ngày: `Cần xử lý`, `Thay đổi`, `Việc của bạn`, `Đang chờ`, `Nguồn đã kiểm tra` | Output bản tóm lược có citation |
| Hỏi đáp có căn cứ | Câu hỏi về hạn chót, người phụ trách, thay đổi, mâu thuẫn và dữ liệu thiếu | Bản ghi câu trả lời, kiểm tra citation, kiểm tra abstention |
| Xử lý mâu thuẫn | Cùng một task/deadline được biểu diễn khác nhau ở nhiều nguồn | Conflict item hiển thị đủ mọi giá trị nguồn |
| Tạo bản nháp hành động | Reminder và calendar draft từ item có nguồn | Trạng thái bản nháp, xử lý trường thiếu, log xác nhận |
| Kiểm tra quyền | Nguồn đã thu hồi, dữ liệu đã xóa, thử truy cập chéo người dùng | Kết quả access-denied và audit log |
| Usability | 3–5 người dùng hoàn thành task UI lõi trước Gate 2 | Bảng vấn đề UX có severity và priority |
| Kết quả pilot | 5–10 học viên dùng mondaiy trong chương trình thật | Dữ liệu completion baseline vs pilot và phỏng vấn người dùng |

### 9.2 Loại kiểm thử

| Test | Tool / Method | Mục đích |
|---|---|---|
| Unit tests | Vitest / service-level tests | Kiểm tra parser, hash, idempotency và chuyển trạng thái. |
| Integration tests | API và database tests | Kiểm tra connector ingestion, persistence, RLS và bộ lọc quyền. |
| Golden dataset tests | Fixture cố định và expected outputs | Kiểm tra extraction, retrieval, phát hiện mâu thuẫn, citation câu trả lời và abstention. |
| End-to-end tests | Playwright | Kiểm tra onboarding, quản lý nguồn, bản tóm lược, evidence drawer và xác nhận hành động. |
| Load test | k6 hoặc tương đương | Kiểm chứng kịch bản 50 active users và mục tiêu thời gian phản hồi. |
| Security/privacy checks | Scan tự động và review thủ công | Phát hiện secret, PII trong log, rò dữ liệu chéo người dùng và truy cập nguồn trái phép. |
| Usability test | Phiên test có điều phối với 3–5 người dùng | Kiểm tra người dùng có tìm được item cần chú ý, bằng chứng, mâu thuẫn và điều khiển dữ liệu không. |
| Pilot study | 5–10 học viên trong một giai đoạn chương trình | Kiểm chứng tính hữu ích và thay đổi tỷ lệ hoàn thành việc trong tuần. |

### 9.3 Kịch bản kiểm thử lõi

#### Test 1 — Đồng bộ nguồn idempotent

1. Gửi cùng một source item hai lần.
2. Khởi động lại worker giữa hai lần gửi.
3. Xác minh không tạo duplicate evidence hoặc duplicate information item.
4. Xác minh `latest observed timestamp` có thể cập nhật mà không tạo phiên bản mới.

#### Test 2 — Versioning nguồn

1. Gửi một item deadline từ VLearn hoặc Jira.
2. Gửi cùng external item đó với ngày hạn thay đổi.
3. Xác minh phiên bản mới được tạo.
4. Xác minh phiên bản cũ vẫn query được và được đánh dấu superseded hoặc liên kết tới phiên bản mới.

#### Test 3 — Phát hiện mâu thuẫn

1. Gửi Discord announcement với deadline A.
2. Gửi VLearn assignment với deadline B cho cùng deliverable.
3. Xác minh mondaiy hiển thị cả hai giá trị, cả hai nguồn và trạng thái confidence cần xác minh.
4. Xác minh AI không âm thầm chọn một deadline làm kết luận cuối cùng.

#### Test 4 — Bản tóm lược hằng ngày có căn cứ

1. Tạo daily briefing sau nhiều cập nhật nguồn.
2. Xác minh mọi factual statement có citation.
3. Xác minh source coverage cho biết đã kiểm tra đủ nguồn hay chưa.
4. Xác minh lỗi nguồn tạo coverage partial hoặc unknown, không báo sai là `complete`.

#### Test 5 — Hỏi đáp có căn cứ và abstention

1. Hỏi câu có câu trả lời trong connected evidence.
2. Hỏi câu không có câu trả lời trong evidence.
3. Hỏi câu phụ thuộc vào một nguồn đã bị thu hồi.
4. Xác minh câu trả lời được hỗ trợ có citation.
5. Xác minh câu không đủ bằng chứng hoặc không đủ quyền thì abstain.

#### Test 6 — Bản nháp hành động an toàn

1. Yêu cầu mondaiy nhắc người dùng về một deadline có nguồn.
2. Xác minh hệ thống chỉ tạo action draft.
3. Xác minh thời gian, múi giờ hoặc owner mơ hồ vẫn để trống.
4. Xác minh không có reminder hoặc calendar handoff nào được tạo trước khi xác nhận.
5. Xác minh yêu cầu tạo draft lặp lại không tạo duplicate draft.

#### Test 7 — Thu hồi quyền và xóa dữ liệu

1. Kết nối một nguồn và sync item.
2. Thu hồi nguồn đó.
3. Hỏi một câu trước đây phụ thuộc vào nguồn đó.
4. Xác minh nguồn đã thu hồi không được dùng trong retrieval mới.
5. Xóa một captured record và xác minh nó không xuất hiện trong search sau đó.

#### Test 8 — Cô lập dữ liệu giữa người dùng

1. Tạo dữ liệu cho User A và User B.
2. Thử truy xuất evidence của User A khi đang xác thực là User B.
3. Xác minh truy cập bị chặn ở database, API, search, display và lớp mở nguồn.

#### Test 9 — Load và responsiveness

1. Mô phỏng 50 active users.
2. Chạy đồng bộ nguồn, mở briefing, hỏi đáp và tạo action draft.
3. Thu latency và error rate.
4. Xác minh đạt mục tiêu trong Success Criteria.

#### Test 10 — Usability validation

Yêu cầu 3–5 người dùng hoàn thành năm task:

1. Tìm việc cần chú ý.
2. Giải thích vì sao việc đó quan trọng.
3. Mở bằng chứng nguồn và xác định timestamp cùng confidence.
4. Nhận ra một mâu thuẫn và giải thích vì sao mondaiy không chọn một nguồn.
5. Tìm chỗ tạm dừng, ngắt kết nối hoặc xóa dữ liệu nguồn.

---

## 10. Success Criteria

### 10.1 Tiêu chí thành công kỹ thuật cứng

Các tiêu chí này được đánh giá trên bộ dữ liệu kiểm thử có phạm vi được công bố trước.

| Khu vực | Metric | Ngưỡng thành công |
|---|---|---|
| Evidence | Factual claim đã công bố có citation nguồn mở lại được | 100% |
| Evidence | Citation chứng minh đúng nội dung được khẳng định | 100% |
| Memory | Official memory có bằng chứng | 100% |
| Memory | Inferred preference bị trình bày như confirmed fact | 0 case |
| Sync | Duplicate record sau retry hoặc resend | 0 |
| Sync | Pending item bị mất sau worker restart hoặc lỗi nguồn | 0 |
| Retrieval | Thông tin có trong nguồn đã cam kết hỗ trợ tìm lại được | 100% trên scoped test set |
| Q&A | Câu hỏi không đủ bằng chứng được abstain đúng | 100% trên unanswerable test set |
| Q&A | Deadline hoặc owner bị bịa khi không có evidence | 0 case |
| Conflict | Giá trị mâu thuẫn được giữ và hiển thị cùng source evidence | 100% conflict test case |
| Action | Hành động bên ngoài xảy ra trước explicit confirmation | 0 case |
| Action | Thời gian mơ hồ bị tự điền như fact | 0 case |
| Privacy | Rò dữ liệu giữa người dùng | 0 case |
| Privacy | Dữ liệu đã thu hồi hoặc đã xóa xuất hiện trong search mới | 0 case |
| Logs | Nội dung gốc email, message, item, câu hỏi hoặc câu trả lời xuất hiện trong product analytics | 0 case |

### 10.2 Tiêu chí thành công hiệu năng

| Flow | Ngưỡng thành công |
|---|---|
| 95% thao tác nhận một batch nguồn phản hồi | ≤ 2 giây |
| 95% lượt mở daily briefing hoàn thành | ≤ 2 giây |
| 95% câu hỏi nhận phần nội dung trả lời đầu tiên | ≤ 10 giây |
| 95% action draft được tạo | ≤ 3 giây |
| Load test | Tương đương 50 active users |

### 10.3 Tiêu chí thành công pilot

Vì pilot chỉ có 5–10 người dùng, chỉ số hành vi phải báo bằng số tuyệt đối và giá trị trước/sau thay vì tuyên bố quá mức bằng các tỷ lệ không ổn định.

| Metric | Cách hiểu là thành công |
|---|---|
| Tỷ lệ hoàn thành việc trong tuần | Cao hơn trong giai đoạn pilot dùng mondaiy so với baseline trước pilot. Báo số trước, số sau và chênh lệch theo điểm phần trăm. |
| Briefing opened | Báo `x/n người dùng` và số ngày mở. |
| Action draft confirmed | Báo `x/n người dùng` đã xác nhận ít nhất một reminder hoặc calendar draft. |
| Answer usefulness | Báo lượt đánh giá hữu ích trên tổng số câu trả lời được đánh giá. |
| Kết quả phỏng vấn người dùng | Báo `x/n người dùng` nói mondaiy giúp giảm thời gian tìm, kiểm tra hoặc nhập lại thông tin, kèm lý do. |

---

## 11. Failure Criteria

ADR được coi là thất bại hoặc cần thiết kế lại nếu bất kỳ điều kiện nào dưới đây xảy ra trong validation.

### 11.1 Tiêu chí thất bại cứng

- Bất kỳ người dùng nào truy cập được dữ liệu nguồn riêng tư, evidence, memory, câu hỏi, câu trả lời hoặc action draft của người dùng khác.
- Bất kỳ reminder, calendar handoff, message hoặc external write nào xảy ra trước khi người dùng xác nhận tường minh.
- Hệ thống trình bày deadline, owner, requirement hoặc status không có bằng chứng như sự thật.
- Hệ thống âm thầm xử lý mâu thuẫn nguồn và ẩn giá trị còn lại.
- Dữ liệu nguồn đã thu hồi hoặc đã xóa được dùng trong briefing hoặc answer mới.
- Retry nguồn hoặc worker restart làm mất pending item.
- Replay cùng một source event tạo duplicate evidence hoặc duplicate information item.
- Product analytics hoặc log chứa nội dung nguồn riêng tư gốc.

### 11.2 Tiêu chí thất bại validation

- Ít hơn 100% factual claim trong scoped test set có citation mở lại được.
- Ít hơn 100% official memory trong scoped test set có evidence.
- Có nhiều hơn 0 case rò dữ liệu chéo người dùng.
- Có nhiều hơn 0 external action chưa xác nhận.
- Có nhiều hơn 0 deadline hoặc owner bị bịa.
- P95 thời gian mở briefing vượt 2 giây trong test 50 active users.
- P95 thời gian nhận phần trả lời đầu tiên vượt 10 giây trong test 50 active users.
- Tỷ lệ hoàn thành việc trong tuần pilot không cải thiện so với baseline và phỏng vấn cho thấy người dùng không giải thích được mondaiy tạo giá trị gì.

---

## 12. Risks

| Risk | Impact | Likelihood | Mitigation | Owner |
|---|---:|---:|---|---|
| Connector không ổn định làm chặn pilot | High | High | Dùng feature flag; pilot chỉ gồm connector đạt gate test; cho phép import fixture thủ công cho evaluation. | Tech Lead |
| OAuth hoặc permission scope của nguồn chưa rõ | High | Medium | Dùng màn hình source permission rõ ràng; ghi exact scope; test revoke và disconnect path. | Tech Lead / PM |
| AI sinh claim không có nguồn | Critical | Medium | Prompt giới hạn bởi retrieval, citation validator, answer abstention và golden dataset tests. | AI Lead |
| Rò dữ liệu giữa người dùng | Critical | Low–Medium | Bắt buộc owner/scope fields, RLS, API permission checks và adversarial access tests. | Tech Lead |
| Evidence model quá yếu cho nhu cầu memory sau này | High | Medium | Giữ raw evidence, normalized fields, versions và provenance; không khóa chặt vào một memory library. | Tech Lead |
| Người dùng không tin trạng thái nguồn chưa đầy đủ | Medium | Medium | Hiển thị coverage status, lần sync thành công gần nhất và lỗi nguồn trước recommendation. | UI/UX Lead |
| Mẫu pilot quá nhỏ cho tỷ lệ phần trăm mạnh | Medium | High | Dùng số tuyệt đối và phỏng vấn định tính; tránh threshold thiếu căn cứ. | PM / PO-QC |
| Scope phình thành general assistant | High | High | Giữ non-goals P0 rõ ràng; yêu cầu ADR mới cho desktop, Messenger/Zalo, page capture hoặc write integrations. | PM |
| Người dùng hiểu nhầm trạng thái calendar action | High | Medium | Phân biệt `drafted`, `previewed`, `confirmed`, `handoff_opened`, `completed`, `cancelled`. | Tech Lead / UI/UX Lead |
| Chi phí tăng vì AI phân tích lặp lại | Medium | Medium | Hash và diff trước khi gọi AI; ưu tiên structured query; đặt model và daily cost gate. | AI Lead |

---

## 13. Rollback Plan

### 13.1 Rollback triggers

Bắt đầu rollback hoặc rollback một phần nếu xảy ra bất kỳ điều kiện nào sau:

- phát hiện rò dữ liệu giữa người dùng;
- xảy ra hành động bên ngoài chưa xác nhận;
- connector liên tục nhập sai dữ liệu hoặc dữ liệu không được phép;
- citation validator fail với câu trả lời đã công bố;
- xóa dữ liệu hoặc thu hồi consent không ngăn retrieval về sau;
- pilot user không hiểu mondaiy đang đọc dữ liệu gì;
- load test cho thấy hệ thống không hỗ trợ được traffic pilot nếu không mất dữ liệu;
- xử lý mâu thuẫn nguồn ẩn bằng chứng hoặc tạo recommendation không an toàn.

### 13.2 Rollback actions theo mức độ nghiêm trọng

#### Sự cố quyền riêng tư hoặc an toàn nghiêm trọng

1. Tắt ngay connector hoặc feature flag bị ảnh hưởng.
2. Dừng background ingestion worker cho loại nguồn bị ảnh hưởng.
3. Thu hồi hoặc rotate token liên quan.
4. Ẩn evidence bị ảnh hưởng khỏi retrieval và briefing generation.
5. Giữ audit log để điều tra, nhưng loại nội dung riêng tư gốc khỏi analytics.
6. Thông báo phạm vi sự cố cho pilot user và reviewer.
7. Chỉ mở lại sau khi có regression test bao phủ lỗi.

#### Lỗi grounding của AI

1. Tắt answer generation cho intent bị ảnh hưởng.
2. Giữ source search và evidence viewer hoạt động.
3. Thay câu trả lời sinh bởi AI bằng abstention message và source coverage report.
4. Thêm case lỗi vào golden dataset.
5. Chỉ bật lại sau khi citation validation pass.

#### Connector không ổn định

1. Tắt connector không ổn định trong pilot.
2. Giữ evidence hợp lệ đã thu nếu consent vẫn cho phép.
3. Đánh dấu source coverage là partial hoặc unknown.
4. Dùng connector ổn định hoặc fixture đã duyệt cho evaluation.
5. Bật lại sau feature flag khi sync và idempotency tests pass.

#### Lỗi luồng hành động

1. Tắt các entry point `create_action_draft`.
2. Tắt manual copy hoặc `.ics` export cho tới khi state transition tests pass.
3. Xác minh không draft nào có thể bỏ qua preview và confirmation.
4. Chỉ bật lại sau khi E2E tests chứng minh đầy đủ luồng bản nháp → xem trước → sửa → xác nhận.

---

## 14. Follow-up Tasks

| ID | Task | Owner | Due | Blocks validation? |
|---|---|---|---|---|
| ADR3-FU-01 | Chốt danh sách connector hỗ trợ cho pilot và feature flags | Tech Lead | Trước cuối Week 2 | Yes |
| ADR3-FU-02 | Định nghĩa evidence schema và immutable version model trong PostgreSQL | Tech Lead | Week 1 | Yes |
| ADR3-FU-03 | Triển khai RLS và API permission checks cho evidence, memory, conversations và action drafts | Tech Lead | Week 1–2 | Yes |
| ADR3-FU-04 | Xây golden dataset cho sync, conflict, Q&A, abstention và action drafting | PO/QC + AI Lead | Week 1–2 | Yes |
| ADR3-FU-05 | Xây citation validator cho factual answer được sinh | AI Lead | Week 3–4 | Yes |
| ADR3-FU-06 | Triển khai trạng thái source coverage: complete, partial, unknown | Tech Lead + UI/UX Lead | Week 3–4 | Yes |
| ADR3-FU-07 | Triển khai Data & Privacy controls: pause, disconnect, delete, revoke | Tech Lead + UI/UX Lead | Week 4 | Yes |
| ADR3-FU-08 | Triển khai action states và idempotent action draft creation | Tech Lead | Week 5 | Yes |
| ADR3-FU-09 | Tạo Playwright E2E tests cho onboarding, source management, briefing, evidence drawer và action confirmation | QA | Week 5 | Yes |
| ADR3-FU-10 | Chạy load test 50 active users và ghi kết quả latency | QA / Tech Lead | Week 5 | Yes |
| ADR3-FU-11 | Chạy usability test 3–5 người cho Gate 2 readiness | UI/UX Lead | Trước Gate 2 | Yes |
| ADR3-FU-12 | Chạy pilot với 5–10 học viên và thu dữ liệu completion baseline vs pilot | PM / PO-QC | Week 6 | Yes |
| ADR3-FU-13 | Viết ADR riêng nếu mở lại extension page-context capture | PM + Tech Lead | Chỉ sau pilot | No for P0 |
| ADR3-FU-14 | Viết ADR riêng nếu mở lại phạm vi Messenger, Zalo, Slack hoặc desktop app | PM + Tech Lead | Post-P0 only | No for P0 |

---

## 15. Result

Điền sau khi implementation và pilot hoàn tất.

### Validation summary

| Area | Result | Evidence link |
|---|---|---|
| Connector sync | TBD | TBD |
| Evidence and citation grounding | TBD | TBD |
| Versioning and conflict handling | TBD | TBD |
| Q&A abstention | TBD | TBD |
| Action confirmation safety | TBD | TBD |
| Permission and deletion checks | TBD | TBD |
| Load test | TBD | TBD |
| Usability test | TBD | TBD |
| Pilot completion-rate change | TBD | TBD |

### Observed metrics

| Metric | Target | Observed | Pass/Fail |
|---|---:|---:|---|
| Openable citations for factual claims | 100% | TBD | TBD |
| Official memories with evidence | 100% | TBD | TBD |
| Duplicate records after retry | 0 | TBD | TBD |
| Lost pending items after restart | 0 | TBD | TBD |
| Invented deadlines or owners | 0 | TBD | TBD |
| Unconfirmed external actions | 0 | TBD | TBD |
| Cross-user data leakage | 0 | TBD | TBD |
| P95 briefing open time | ≤ 2s | TBD | TBD |
| P95 first answer time | ≤ 10s | TBD | TBD |
| P95 action draft time | ≤ 3s | TBD | TBD |
| Weekly completion rate vs baseline | Higher than baseline | TBD | TBD |

### Outcome

Chọn một trong các kết quả sau sau validation:

- **Validated:** P0 connector-first, có bằng chứng đủ an toàn và hữu ích để tiếp tục.
- **Partially validated:** Core đúng hướng, nhưng cần thu hẹp một hoặc nhiều connector hoặc UX flow trước khi mở rộng.
- **Rejected:** Kiến trúc không tạo kết quả hữu ích hoặc an toàn; cần xem lại ingestion model, evidence model hoặc product scope.
- **Superseded:** ADR sau thay thế quyết định này.

---

## Appendix A — Guardrail quyết định cho ADR tương lai

Bất kỳ đề xuất tương lai nào cũng phải tạo ADR mới nếu thay đổi một trong các ranh giới P0 sau:

- đọc trang web bất kỳ;
- theo dõi màn hình, lịch sử duyệt web hoặc hoạt động hệ điều hành;
- xây desktop app hoặc local background agent;
- kết nối Messenger, Zalo, Slack, Facebook hoặc nền tảng nhắn tin mới;
- thêm tích hợp có quyền ghi;
- cho phép AI hành động mà không qua preview và confirmation;
- cho phép admin xem nội dung nguồn cá nhân chi tiết;
- thay canonical evidence store khỏi PostgreSQL.

## Appendix B — Vị trí file đề xuất

```text
docs/projects/engineering/adr/adr-003-test-driven-connector-first-program-navigator.md
```
