# Đặc tả yêu cầu sản phẩm — mondaiy (bản 0.5)

| Thuộc tính | Giá trị |
| --- | --- |
| Trạng thái | Đang lấy ý kiến để hoàn thiện |
| Người chịu trách nhiệm | Thái Hoài An — Quản lý dự án |
| Tác giả | Thái Hoài An — Quản lý dự án |
| Người phản biện | Người hướng dẫn hoặc nhà tài trợ, Trưởng nhóm kỹ thuật, Trưởng nhóm thiết kế, Chủ sản phẩm và kiểm soát chất lượng |
| Cập nhật lần cuối | 2026-08-18 |
| Định vị | **mondaiy — Trợ lý AI cá nhân thật sự hiểu người dùng** |
| Vai trò của tài liệu | Nguồn chuẩn cho yêu cầu, điều kiện nghiệm thu và chỉ số sản phẩm |
| Tài liệu liên quan | [Bản giới thiệu ngắn](one-page-brief.md) · [Sơ đồ câu chuyện người dùng](user-story-map.md) · [Quyết định kiến trúc số 1](../engineering/adr/adr-001-platform-core-program-navigator-vertical.md) · [Quyết định kiến trúc số 7](../engineering/adr/adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md) · [Luồng giao diện](../design/wireframe-ui-flow.md) · [Kế hoạch đánh giá](../qa/evaluation-plan.md) |

## Mục lục

- [Thuật ngữ cần biết trước khi đọc](#thuật-ngữ-cần-biết-trước-khi-đọc)
- [1. Tóm tắt](#1-tóm-tắt)
- [2. Vấn đề cần giải quyết](#2-vấn-đề-cần-giải-quyết)
- [3. Cách sản phẩm tạo giá trị](#3-cách-sản-phẩm-tạo-giá-trị)
- [4. Mục tiêu, chỉ số và phạm vi loại trừ](#4-mục-tiêu-chỉ-số-và-phạm-vi-loại-trừ)
- [5. Nhóm người dùng và quyền truy cập](#5-nhóm-người-dùng-và-quyền-truy-cập)
- [6. Phạm vi bắt buộc trong sáu tuần](#6-phạm-vi-bắt-buộc-trong-sáu-tuần)
- [7. Hành trình người dùng](#7-hành-trình-người-dùng)
- [8. Yêu cầu chức năng](#8-yêu-cầu-chức-năng)
- [9. Quy tắc nghiệp vụ](#9-quy-tắc-nghiệp-vụ)
- [10. Mô hình dữ liệu tối thiểu](#10-mô-hình-dữ-liệu-tối-thiểu)
- [11. Quy tắc cho phép mondaiy sử dụng công cụ](#11-quy-tắc-cho-phép-mondaiy-sử-dụng-công-cụ)
- [12. Yêu cầu về chất lượng hệ thống](#12-yêu-cầu-về-chất-lượng-hệ-thống)
- [13. Dữ liệu đo lường sản phẩm](#13-dữ-liệu-đo-lường-sản-phẩm)
- [14. Kế hoạch đánh giá](#14-kế-hoạch-đánh-giá)
- [15. Kế hoạch sáu tuần](#15-kế-hoạch-sáu-tuần)
- [16. Phụ thuộc và rủi ro](#16-phụ-thuộc-và-rủi-ro)
- [17. Điều kiện để bắt đầu phát triển một yêu cầu](#17-điều-kiện-để-bắt-đầu-phát-triển-một-yêu-cầu)
- [18. Điều kiện hoàn thành phiên bản sáu tuần](#18-điều-kiện-hoàn-thành-phiên-bản-sáu-tuần)
- [19. Quyết định còn mở](#19-quyết-định-còn-mở)

## Thuật ngữ cần biết trước khi đọc

Tài liệu ưu tiên tiếng Việt. Những tên riêng, tiêu chuẩn hoặc thuật ngữ kỹ thuật
không thể dịch chính xác được giữ nguyên và giải thích dưới đây.

Cột thứ ba là **tên tương ứng trong tài liệu kỹ thuật, Jira và mã nguồn**. Một
khái niệm có thể mang tên tiếng Việt ở tài liệu này và tên tiếng Anh ở nơi khác,
nhưng chỉ là một khái niệm. Gặp một tên lạ thì tra ngược cột này trước khi đặt
thêm tên mới.

### Từ vựng nền tảng

| Thuật ngữ | Giải thích trong tài liệu này | Tên trong tài liệu kỹ thuật và mã nguồn |
| --- | --- | --- |
| **AI** | Trí tuệ nhân tạo. Trong tài liệu này, AI chỉ được dùng để tóm lược, tìm thông tin và đề xuất; không được tự quyết định thay người dùng. | — |
| **P0** | Phạm vi bắt buộc phải hoàn thành để thử nghiệm sản phẩm. Chưa hoàn thành P0 thì chưa đủ điều kiện thử nghiệm với người dùng. | `P0` |
| **Connector** | Thành phần kết nối mondaiy với Calendar, Jira, Discord, VLearn hoặc Gmail theo quyền người dùng cấp. | `src/services/connections/` |
| **Webhook** | Cách một nguồn chủ động báo cho mondaiy khi có dữ liệu mới hoặc thay đổi. | `webhook` |
| **Cookie** | Dữ liệu phiên đăng nhập do trình duyệt lưu. mondaiy không thu thập cookie đăng nhập. | — |
| **`.ics`** | Định dạng tệp lịch phổ biến, có thể mở bằng Google Lịch và nhiều ứng dụng lịch khác. | `.ics` |
| **PostgreSQL** | Hệ quản trị cơ sở dữ liệu chính của sản phẩm. Tên rút gọn `Postgres` có cùng ý nghĩa. | `postgres` |
| **Supabase** | Dịch vụ cung cấp đăng nhập và cơ sở dữ liệu PostgreSQL cho sản phẩm. | `supabase` |
| **OpenRouter** | Dịch vụ trung gian giúp nhóm thử và thay đổi mô hình trí tuệ nhân tạo. | `openrouter` |
| **Mã băm** | Dấu nhận biết được tính từ nội dung, giúp phát hiện nội dung trùng hoặc đã thay đổi. Từ `hash` chỉ xuất hiện trong tên trường kỹ thuật. | `content hash`, `content_hash` — chưa có trong mã |
| **API** | Cách các thành phần phần mềm trao đổi dữ liệu với nhau theo một quy ước đã thống nhất. | `API` |
| **RLS** | Cơ chế của cơ sở dữ liệu giúp bảo đảm mỗi người chỉ đọc và sửa những dòng dữ liệu họ được phép truy cập. | `RLS` |

### Từ vựng của bản tóm lược và nguồn

| Thuật ngữ | Giải thích trong tài liệu này | Tên trong tài liệu kỹ thuật và mã nguồn |
| --- | --- | --- |
| **Khung chương trình** | Bản khai báo khóa học, múi giờ, nhóm, vai trò, sản phẩm bàn giao và mức độ đáng tin của từng nguồn. Là ranh giới để lọc nội dung trước khi AI tham gia. Xem [FR-040](#85-trợ-lý-hỗ-trợ-học-viên-và-bản-tóm-lược). | `Program Frame` — chưa có trong mã |
| **Mức độ đáng tin của nguồn** | Xếp hạng nguồn thành Mức A (nguồn chính thức) và Mức B (nguồn tham khảo). Không được gộp hai mức. | `source level`, `source authority`, `sourceLevel: "A" \| "B"` |
| **Mục thông tin** | Một đơn vị nội dung đã rút ra từ nguồn, kèm nguồn gốc, trạng thái và các phiên bản của nó. | `information item`, `InformationItem` |
| **Bản tóm lược hằng ngày** | Bản tin gồm năm phần `Cần xử lý`, `Thay đổi`, `Việc của bạn`, `Đang chờ` và `Nguồn đã kiểm tra`. Xem [FR-043](#85-trợ-lý-hỗ-trợ-học-viên-và-bản-tóm-lược). | `Daily Brief`, `Daily Briefing`, `BriefResponse` |
| **Bằng chứng và nguồn gốc** | Bản lưu nội dung gốc cùng thông tin nguồn nào, thời điểm nào, lần quét nào. Là lớp canonical đứng trước mọi bước rút trích. | `evidence`, `provenance` — chưa có trong mã |
| **Biên nhận quét nguồn** | Ghi nhận mỗi lần quét một nguồn thành công hay lỗi, để người dùng biết bản tóm lược dựa trên những nguồn nào. | `receipt`, `BriefReceipt` |
| **Trích dẫn** | Link nguồn kèm đoạn nguyên văn và thời điểm, để người dùng tự kiểm chứng. | `citation`, `Citation` |
| **Nguyên văn** | Chép đúng chữ trong nguồn, không diễn giải lại. | `verbatim` — chưa có trong mã |
| **Mức độ đầy đủ** | Bản tóm lược đã quét đủ nguồn hay chưa: đầy đủ, chưa đầy đủ, chưa xác định. Nguồn lỗi thì phải báo, không được báo là đã kiểm tra đủ. Xem [FR-045](#85-trợ-lý-hỗ-trợ-học-viên-và-bản-tóm-lược). | `coverage`, `CoverageStatus: complete \| partial \| unknown` |
| **Độ tin cậy** | Mức chắc chắn hệ thống tự đánh giá cho một thông tin đã rút ra. | `confidence` — chưa có trong mã |
| **Từ chối trả lời** | Không đủ bằng chứng thì nói rõ là không biết, không suy đoán. | `abstain`, `ChatAnswerKind: "abstain"`, `AbstainNotice` |
| **Không xác định** | Ô dữ liệu để trống vì không tìm được bằng chứng. Khác với ô sai. Không được điền bằng phỏng đoán. | `unknown` |

### Từ vựng của phiên bản và thay đổi

| Thuật ngữ | Giải thích trong tài liệu này | Tên trong tài liệu kỹ thuật và mã nguồn |
| --- | --- | --- |
| **Phiên bản** | Một bản của cùng một mục thông tin tại một thời điểm. Nội dung nguồn đổi thì sinh phiên bản mới, không ghi đè bản cũ. | `version`, `source_items`, `source_item_versions` — chưa có trong mã |
| **Không ghi đè** | Đã ghi thì không sửa, không xóa; muốn đổi thì ghi thêm phiên bản mới. Nhờ vậy mới trả lời được câu hỏi "vì sao tuần trước hệ thống báo khác". | `immutable` |
| **Lặp lại không sinh thêm** | Chạy một thao tác một lần hay nhiều lần đều cho cùng một kết quả. Gửi trùng lệnh quét không được tạo thêm bản ghi trùng. | `idempotent`, `Idempotency-Key` |
| **Đã thay thế** | Trạng thái của phiên bản cũ khi đã có phiên bản mới hợp lệ thay thế nó. Là một trong năm trạng thái ở [FR-041](#85-trợ-lý-hỗ-trợ-học-viên-và-bản-tóm-lược). | `superseded`, `supersedes` |
| **Mâu thuẫn** | Hai nguồn nói khác nhau về cùng một việc. Phải hiện cả hai, không được tự chọn một bên rồi trình bày như điều chắc chắn. | `conflict`, `hasConflict`, `conflictVersions`, `disputed` |
| **Rò dữ liệu giữa người dùng** | Một người đọc được dữ liệu của người khác. Đây là lỗi nghiêm trọng nhất, ngưỡng chấp nhận là không có trường hợp nào. | `cross-user leak` |
| **Lát cắt dọc** | Một tính năng duy nhất nhưng chạy thông suốt qua mọi tầng, từ nguồn tới giao diện. Cách làm bắt buộc cho Gate 2. | `vertical slice` |

Các tên nằm trong dấu `` `...` `` là mã cố định dùng trong phần mềm hoặc cơ sở
dữ liệu. Chúng không phải cách diễn đạt dành cho người dùng.

Ghi chú **chưa có trong mã** nghĩa là tên đã được chốt trong tài liệu nhưng phần
mềm chưa hiện thực. Đó là contract cần hiện thực đúng tên này, không đặt tên
khác.

## 1. Tóm tắt

mondaiy đọc Calendar, Jira, Discord, VLearn và Gmail theo quyền người dùng cấp,
lưu lại nguồn gốc cùng lịch sử thay đổi, rồi làm ba việc:

1. **Tóm lược** — nói trước điều cần chú ý, điều vừa đổi, việc đang chờ.
2. **Hỏi** — trả lời không cần người dùng dán lại thông tin, kèm nguồn kiểm tra được.
3. **Hành động** — soạn lời nhắc hoặc sự kiện lịch, người dùng sửa rồi mới xác nhận.

Tình huống dùng đầu tiên là hỗ trợ học viên trong một khóa học có nhóm, vai trò,
sản phẩm bàn giao, hạn chót và nguồn chính thức. Sáu tuần không đủ để làm một
trợ lý vạn năng. Mục tiêu là chứng minh mondaiy hiểu đúng hoàn cảnh của từng học
viên và đưa họ từ thông tin phân mảnh tới hành động mà không bịa.

## 2. Vấn đề cần giải quyết

Học viên và người làm việc tri thức nhận thông tin rải rác: nhiệm vụ trên Jira,
thông báo và hạn nộp trên VLearn, trao đổi trên Discord và Gmail, sự kiện trên
Calendar.

Hệ quả là họ phải tự nhớ những gì đã thấy, tìm lại nguồn trước khi quyết định,
so bản cũ với bản mới, giải thích lại hoàn cảnh mỗi lần hỏi một công cụ AI, và
nhập cùng một thông tin hai lần vào danh sách việc lẫn lịch.

Ba cách làm nửa vời đều hỏng. Chỉ đồng bộ thì được thêm một kho dữ liệu không ai
dùng. Chỉ để AI trả lời thì bịa. Để AI tự hành động thì sai một lần là mất niềm
tin. mondaiy phải làm trọn chuỗi ghi nhận nguồn, hiểu người dùng, tóm lược hoặc
trả lời, chuẩn bị hành động — và giữ quyền quyết định ở người dùng.

## 3. Cách sản phẩm tạo giá trị

### 3.1. Hiểu người dùng nghĩa là gì

mondaiy giữ nguồn gốc và lịch sử thay đổi của mọi thông tin, phân biệt điều đã
xác nhận với điều mới suy ra, và chỉ tìm lại trong phạm vi quyền người dùng còn
cho phép. "Hiểu" ở đây được đo bằng chất lượng tóm lược, câu trả lời và đề xuất
hành động — không phải bằng lượng dữ liệu lưu được.

### 3.2. Trợ lý hỗ trợ học viên

Tình huống dùng bắt buộc trong sáu tuần:

- hiểu khung chương trình và mức độ đáng tin của từng nguồn;
- hiểu nhóm, vai trò và mục tiêu của học viên;
- tạo bản tóm lược hằng ngày;
- trả lời câu hỏi chung hoặc câu hỏi về một nội dung cụ thể;
- chuẩn bị lời nhắc và bản nháp sự kiện lịch.

### 3.3. Nguyên tắc sản phẩm

1. Chỉ ghi nhận nguồn khi người dùng đã đồng ý và luôn cho họ biết trạng thái.
2. Giữ bằng chứng trước khi tạo thông tin ghi nhớ; chỉ dùng thông tin đã lưu để tạo câu trả lời.
3. Chủ động tóm lược trước, trò chuyện khi người dùng cần làm rõ.
4. Không có nguồn thì không khẳng định đó là sự thật.
5. Điều hệ thống suy ra chỉ là đề xuất cho đến khi được xác nhận.
6. Luôn tạo bản nháp trước khi thực hiện hành động.
7. Chỉ xây năng lực dùng chung khi một trường hợp sử dụng thật sự cần đến nó.
8. Đánh giá độ tin cậy trước khi mở rộng phạm vi.

## 4. Mục tiêu, chỉ số và phạm vi loại trừ

### 4.1. Mục tiêu

- Người dùng nhận được giá trị mà không phải sao chép lại thông tin.
- Người dùng xem được vì sao hệ thống ghi nhớ một thông tin.
- Người dùng hỏi được về nhiệm vụ, hạn chót, thay đổi và thông báo, đồng thời kiểm tra được nguồn câu trả lời.
- Người dùng biến một nội dung có nguồn thành hành động trong tối đa ba bước sau khi chọn hành động.
- Sản phẩm phát hiện nguồn thay đổi hoặc mâu thuẫn mà không ghi đè lịch sử.
- Tỷ lệ hoàn thành công việc trong tuần tăng so với trước khi dùng mondaiy.
- Nhóm đánh giá được việc đồng bộ, ghi nhớ, tìm lại và tạo hành động bằng một bộ dữ liệu kiểm thử có thể chạy lại.

### 4.2. Chỉ số quan trọng nhất

**Tỷ lệ hoàn thành công việc trong tuần:** tỷ lệ công việc đến hạn trong tuần
được hoàn thành.

```text
Tỷ lệ hoàn thành công việc trong tuần
= số công việc đến hạn trong tuần đã hoàn thành
÷ tổng số công việc đến hạn trong tuần
```

**Tiêu chí thành công:** tỷ lệ này trong giai đoạn dùng mondaiy cao hơn baseline
đo trước thử nghiệm. Báo cáo phải nêu tỷ lệ trước, tỷ lệ sau và mức tăng theo
điểm phần trăm. Chỉ tính công việc có hạn trong tuần từ các nguồn đã kết nối;
loại công việc đã hủy và tuần không có công việc đến hạn.

**Chỉ công việc bị hủy mới rút khỏi mẫu số.** Bỏ qua một lời nhắc không phải là
hủy công việc: lời nhắc chuyển sang `cancelled` còn công việc vẫn mở và vẫn nằm
trong mẫu số. Nếu gộp hai thao tác này, người dùng bỏ qua càng nhiều thì tỷ lệ
báo cáo càng cao trong khi không có việc nào được hoàn thành. Ranh giới hai tầng
nằm tại [FR-092](#89-nhắc-việc-và-thông-báo) và
[ADR-007](../engineering/adr/adr-007-lich-tuong-tac-truc-tiep-va-lop-nhac-viec.md).

### 4.3. Hệ thống chỉ số

Chỉ số chia làm hai loại. Loại một chạy trên bộ dữ liệu kiểm thử nên đặt được
ngưỡng cứng. Loại hai phụ thuộc hành vi người dùng, mà pilot chỉ 5–10 người —
một người đổi ý làm tỷ lệ nhảy 10–20 điểm phần trăm, nên nhóm báo cáo số tuyệt
đối thay vì đặt ngưỡng.

**Loại 1 — ngưỡng cứng, kiểm chứng bằng bộ dữ liệu kiểm thử:**

| Nhóm | Chỉ số | Ngưỡng |
| --- | --- | --- |
| Đồng bộ nguồn | Item đang chờ bị mất khi nguồn lỗi hoặc worker khởi động lại | 0 |
| Đồng bộ nguồn | Bản ghi trùng sau khi gửi lại | 0 |
| Nguồn dẫn | Khẳng định đã công bố có nguồn mở lại được | 100% |
| Nguồn dẫn | Nguồn dẫn đúng với nội dung được khẳng định | 100% |
| Ghi nhớ | Thông tin ghi nhớ chính thức có bằng chứng | 100% |
| Ghi nhớ | Suy luận bị trình bày như thông tin đã xác nhận | 0 |
| Độ tin cậy | Tìm được thông tin có trong các nguồn đã cam kết hỗ trợ | 100% |
| Trả lời | Tự tạo hạn chót hoặc người phụ trách không có nguồn | 0 |
| Trả lời | Từ chối đúng khi không đủ bằng chứng | 100% trên nhóm case không trả lời được |
| An toàn | Hành động **do hệ thống khởi tạo** xảy ra trước khi người dùng xác nhận | 0 |
| An toàn | Người dùng đọc được dữ liệu của người khác | 0 |

Ngưỡng 100% chỉ áp cho bộ dữ liệu kiểm thử đã công bố phạm vi trước, không phải
lời hứa về mọi nội dung ngoài đời.

Chỉ số an toàn về xác nhận chỉ tính hành động do hệ thống hoặc mondaiy khởi tạo.
Người dùng tự tạo, sửa, kéo đổi giờ hay xóa một sự kiện trên giao diện lịch thì
chính thao tác đó là sự xác nhận, không tính là vi phạm. Ranh giới theo chủ thể
khởi tạo nằm tại [FR-069](#87-hành-động).

**Loại 2 — quan sát trong pilot, báo cáo số tuyệt đối:**

| Nhóm | Chỉ số | Cách báo cáo |
| --- | --- | --- |
| Chỉ số chính | Tỷ lệ hoàn thành công việc đến hạn trong tuần | Số trước pilot, số trong pilot, mức chênh theo điểm phần trăm |
| Thói quen | Số người mở bản tóm lược, theo ngày | `x/n người`, kèm số ngày mở |
| Hành động | Số người xác nhận ít nhất một lời nhắc hoặc bản nháp lịch | `x/n người` |
| Hữu ích | Đánh giá hữu ích trên từng câu trả lời | Số lượt hữu ích trên tổng lượt đánh giá |
| Kết quả | Người nói đã giảm thời gian tìm, kiểm tra, nhập lại | `x/n người`, kèm lý do từ phỏng vấn cuối pilot |

Bản trước đặt ngưỡng 70%, 95%, 60% và 30% cho nhóm loại 2. Đã bỏ vì nhóm chưa
phỏng vấn người dùng nào để chọn con số, và cỡ mẫu không đủ để tỷ lệ phần trăm
có ý nghĩa.

### 4.4. Không thuộc phạm vi sáu tuần

- Tìm kiếm toàn bộ mạng hoặc trả lời kiến thức tổng quát.
- Theo dõi màn hình, lịch sử duyệt web hoặc đọc nội dung trang web bất kỳ.
- Thu thập cookie đăng nhập, mật khẩu hoặc dữ liệu trình duyệt hệ thống.
- Ghi âm, tạo transcript hoặc cho bot tham gia cuộc họp.
- Kết nối đồng thời thư điện tử, Slack, Facebook và Messenger.
- Nhiều trợ lý AI tự phân chia và phối hợp công việc với nhau.
- Xây mạng lưới tri thức cá nhân phức tạp.
- Âm thầm gửi tin nhắn hoặc ghi dữ liệu vào lịch và danh sách việc.
- Ứng dụng riêng cho điện thoại.
- Bảng quản trị theo dõi chi tiết hành vi cá nhân.

## 5. Nhóm người dùng và quyền truy cập

| Nhóm người dùng | Nhu cầu | Quyền trong phạm vi P0 |
| --- | --- | --- |
| Học viên | Được hỗ trợ dựa trên hoàn cảnh cá nhân, xem bản tóm lược, đặt câu hỏi và tạo hành động | Quản lý sự đồng ý, nguồn và thông tin ghi nhớ của mình; xem bản tóm lược; hỏi; tạo hành động |
| Người hướng dẫn hoặc quản trị chương trình | Duy trì khung chương trình và nguồn chính thức | Quản lý nguồn của chương trình; xử lý thông tin mâu thuẫn; xem số liệu chất lượng tổng hợp |
| Người vận hành hệ thống | Theo dõi quá trình nhận dữ liệu và sự cố | Xem trạng thái tổng hợp và nhật ký đã loại thông tin nhạy cảm; không mặc định được xem nội dung cá nhân gốc |

Quy tắc về quyền truy cập:

- Quyền không bắt buộc của trình duyệt chỉ được hỏi sau khi người dùng chủ động chọn một chức năng cần quyền đó.
- Sự đồng ý được quản lý theo từng nguồn hoặc tên miền và có thể thu hồi.
- Khi thu hồi sự đồng ý, hệ thống dừng đồng bộ mới và không dùng dữ liệu đó trong lần tìm kiếm sau; việc xóa dữ liệu tuân theo thời hạn lưu giữ đã công bố.
- Quyền được kiểm tra lại khi tìm kiếm, hiển thị hoặc mở nguồn và khi dùng công cụ tạo hành động.
- Người quản trị không mặc định được xem nội dung nguồn, câu hỏi hoặc lời nhắc cá nhân.
- Khóa có quyền cao của máy chủ không được đưa vào tiện ích trình duyệt.

## 6. Phạm vi bắt buộc trong sáu tuần

### 6.1. Nguồn kết nối

- Kết nối chỉ đọc với Calendar, Jira, Discord, VLearn và Gmail; thử nghiệm có thể giới hạn còn các nguồn ổn định nhất.
- Người dùng chủ động kết nối, xem phạm vi quyền và có thể ngắt từng nguồn.
- Đồng bộ nhiệm vụ, hạn chót, sự kiện, thông báo và metadata cần thiết cho năm trường hợp sử dụng chính.
- Mỗi item giữ mã nguồn, đường dẫn mở lại, thời điểm nguồn cập nhật và thời điểm mondaiy quan sát.
- Giao diện cho biết lần đồng bộ gần nhất, nguồn đang lỗi và mức độ dữ liệu đã đọc được.

P0 không theo dõi màn hình, không đọc nội dung trang web tùy ý, không lấy lịch
sử duyệt web và không thu thập nội dung cuộc họp. Extension, nếu được giữ, chỉ
là bề mặt thao tác và hiển thị trạng thái.

### 6.2. Đồng bộ và bằng chứng

- Đồng bộ tăng dần bằng webhook hoặc kiểm tra định kỳ phù hợp với từng nguồn.
- Gửi lại không tạo item hoặc phiên bản trùng.
- Cùng một item có nội dung mới sẽ tạo phiên bản mới; không ghi đè lịch sử.
- Chuẩn hóa trường chung nhưng luôn giữ nội dung gốc và đường dẫn về nguồn.
- Khi nguồn lỗi, giao diện phải hiển thị dữ liệu chưa đầy đủ hoặc chưa xác định.

### 6.3. Ghi nhớ về người dùng

- Thông tin người dùng tự khai báo: tên, múi giờ, vai trò, mục tiêu và cách họ muốn được hỗ trợ.
- Bằng chứng theo sự kiện: nhiệm vụ, sự kiện, thông báo và email đã được cấp quyền.
- Thông tin được đề xuất: sở thích, dự án, quyết định, cam kết hoặc sự thật mà hệ thống suy ra từ bằng chứng.
- Thông tin ghi nhớ chính thức: đã có bằng chứng, có lịch sử thay đổi, thời hạn hiệu lực và trạng thái rõ ràng.
- Tập thông tin tạm thời dùng cho một bản tóm lược hoặc một câu hỏi.
- Trạng thái hành động và phản hồi của người dùng.

### 6.4. Trợ lý hỗ trợ học viên

- Thử nghiệm trong một khóa học; dữ liệu khung chương trình có thể được nhóm nhập sẵn, chưa cần màn hình quản trị hoàn chỉnh.
- Hiểu nhóm, vai trò, sản phẩm bàn giao, hạn chót và mức độ đáng tin của nguồn.
- Phân biệt hai mức nguồn:
  - **Nguồn chính thức:** thông tin người dùng tự khai báo, khung chương trình, lịch và tài liệu hoặc thông báo chính thức.
  - **Nguồn tham khảo:** thảo luận Discord, email và nguồn chưa được công nhận là chính thức.
- Chọn nội dung phù hợp dựa trên nhóm, vai trò, người phụ trách và mục tiêu người dùng đã khai báo.
- Phán đoán của AI chỉ được dùng để sắp xếp mức liên quan, không được thay đổi mức độ đáng tin của nguồn.

### 6.5. Tóm lược, Hỏi và Hành động

- Bản tóm lược hằng ngày được chuẩn bị trước để mở nhanh.
- Người dùng có thể hỏi trên toàn bộ thông tin đã lưu hoặc hỏi về một nội dung cụ thể.
- Có màn hình xem nguồn và quản lý thông tin hệ thống đang ghi nhớ.
- Có lời nhắc trong sản phẩm.
- Có mẫu tạo sự kiện Google Lịch và tệp lịch `.ics`.
- Có giao diện lịch xem theo tuần, cho người dùng tự tạo, sửa, đổi giờ và xóa sự kiện.
- Có lớp nhắc việc đẩy thông báo qua tiện ích trình duyệt trước hạn chót.
- Hành động đi qua sáu trạng thái cố định: `drafted` — đã tạo bản nháp; `previewed` — đã xem; `confirmed` — đã xác nhận; `handoff_opened` — đã mở trong ứng dụng bên ngoài; `completed` — đã hoàn thành; `cancelled` — đã hủy.

## 7. Hành trình người dùng

### J1. Bắt đầu sử dụng và cấp quyền

1. Người dùng nhập thông tin cá nhân, múi giờ và mục tiêu.
2. Chọn Calendar, Jira, Discord, VLearn hoặc Gmail cần kết nối.
3. Đọc rõ dữ liệu nào được đồng bộ, dữ liệu nào không và được lưu trong bao lâu.
4. Cấp quyền chỉ đọc cho từng nguồn.
5. Ứng dụng hiển thị trạng thái kết nối và kết quả đồng bộ gần nhất.

**Khi bị từ chối quyền:** bỏ qua nguồn đó; các nguồn đã kết nối vẫn hoạt động.

### J2. Đồng bộ nguồn

1. Connector nhận webhook hoặc kiểm tra nguồn theo lịch.
2. Item được chuẩn hóa, tính mã băm và đưa vào hàng chờ xử lý.
3. Máy chủ chỉ báo đã nhận sau khi lưu bằng chứng thành công.
4. Nội dung giống hệt bản cũ không tạo thêm một phiên bản.
5. Nội dung đã thay đổi tạo phiên bản mới và được đối chiếu lại.

**Khi nguồn tạm lỗi:** hệ thống gửi lại, hiển thị dữ liệu chưa đầy đủ và giữ lần
đồng bộ thành công gần nhất.

### J3. Từ thay đổi nguồn đến thông tin ghi nhớ

1. Jira, VLearn, Discord, Gmail hoặc Calendar có item mới hay thay đổi.
2. Connector lưu item và phiên bản mới.
3. Hệ thống đề xuất nhiệm vụ, hạn chót, thay đổi hoặc cam kết có cấu trúc.
4. Mỗi đề xuất dẫn về item gốc và thời điểm nguồn cập nhật.
5. Nếu mâu thuẫn với thông tin hiện tại, hệ thống giữ cả hai phiên bản và đánh dấu cần xác minh.

### J4. Bản tóm lược hằng ngày

1. Hệ thống tìm những thay đổi kể từ bản tóm lược trước.
2. Quy tắc sản phẩm chọn hạn chót, thay đổi, mâu thuẫn, việc đang chờ và nội dung liên quan đến người dùng.
3. AI chỉ diễn đạt lại những nội dung đã được chọn, không tự bổ sung sự thật.
4. Bản tóm lược cho biết nguồn nào đã đọc được và nguồn nào đang thiếu hoặc gặp lỗi.
5. Người dùng mở nguồn, đặt câu hỏi hoặc tạo hành động.

**Khi không có thông tin mới:** hiển thị việc đang chờ, hạn chót sắp tới và
trạng thái nguồn thay vì để màn hình trống.

### J5. Đặt câu hỏi có căn cứ

1. Người dùng hỏi trên toàn bộ thông tin đã lưu hoặc chọn `Hỏi về việc này`.
2. Hệ thống lọc theo người dùng, nguồn, thời gian, dự án và quyền truy cập.
3. Thông tin có cấu trúc được ưu tiên trước khi tìm trong nội dung văn bản.
4. Câu trả lời về sự thật phải dẫn đến đúng bằng chứng.
5. Bộ kiểm tra loại bỏ phần trả lời không có nguồn hoặc không được phép truy cập.

**Khi không thể trả lời:** hiển thị “Chưa tìm thấy trong thông tin đã lưu”, cho
biết phạm vi nguồn đã kiểm tra và gợi ý bước tiếp theo an toàn.

### J6. Quản lý điều hệ thống đang ghi nhớ

1. Người dùng xem riêng thông tin tự khai báo, đã xác nhận, đang được đề xuất, đang mâu thuẫn và đã được thay thế.
2. Mở được bằng chứng tạo ra từng thông tin.
3. Xác nhận, sửa, bác bỏ hoặc xóa một đề xuất.
4. Phản hồi được lưu vào lịch sử thay đổi và ảnh hưởng đến những lần tìm kiếm sau.

### J7. Tạo hành động

1. Người dùng chọn `Nhắc tôi` hoặc `Thêm vào lịch`.
2. Bản nháp lấy tên việc, thời gian, múi giờ, ghi chú và nguồn từ bằng chứng.
3. Trường còn mơ hồ được để trống và yêu cầu người dùng nhập hoặc chọn lại.
4. Người dùng xem, sửa và xác nhận.
5. Lời nhắc được lưu hoặc bản nháp sự kiện được mở trong ứng dụng lịch.

**Khi nguồn thay đổi:** hành động được gắn cảnh báo; hệ thống không tự sửa hoặc
hủy hành động đã được người dùng xác nhận.

## 8. Yêu cầu chức năng

### 8.1. Thông tin cá nhân, sự đồng ý và nguồn

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-001 | P0 | Thông tin người dùng tự khai báo | Người dùng sửa được múi giờ, vai trò, mục tiêu và cách muốn được hỗ trợ; mỗi lần thay đổi đều lưu người thực hiện và thời điểm |
| FR-002 | P0 | Đồng ý cho dùng nguồn | Lưu rõ nguồn, phạm vi, trạng thái và thời hạn giữ dữ liệu; thu hồi đồng ý phải dừng đồng bộ và không dùng dữ liệu đó trong lần tìm kiếm mới |
| FR-003 | P0 | Điều khiển kết nối | Người dùng thấy trạng thái, lần đồng bộ cuối và có thể ngắt từng nguồn |
| FR-004 | P0 | Ranh giới quyền | Khi người dùng từ chối quyền, ứng dụng không bị dừng đột ngột; các nguồn khác vẫn dùng được |
| FR-005 | P0 | Đồng ý chia sẻ dữ liệu với AI trên mobile | Trước lần chatbot mobile gửi câu hỏi, ảnh hoặc ngữ cảnh từ nguồn đã cấp quyền cho AI, người dùng được giải thích mục đích và chọn đồng ý hoặc từ chối; lựa chọn có thể thay đổi trong Cá nhân và từ chối phải chặn lần gửi đó |

### 8.2. Đồng bộ và phiên bản

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-010 | P0 | Nhận item từ nguồn | Lưu nhà cung cấp, mã ngoài, đường dẫn mở lại, nội dung cần thiết, thời điểm nguồn cập nhật, thời điểm quan sát và mã băm |
| FR-011 | P0 | Hàng chờ bền vững | Item đã nhận không bị mất khi worker khởi động lại hoặc nguồn tạm lỗi |
| FR-012 | P0 | Gửi lại an toàn | Gửi lại hoặc gửi hai lần không tạo bằng chứng hay phiên bản trùng |
| FR-013 | P0 | Quản lý phiên bản | Cùng mã ngoài nhưng mã băm mới thì tạo phiên bản mới; mã băm cũ chỉ cập nhật lần quan sát |
| FR-014 | P0 | Trạng thái nguồn | Giao diện hiển thị đã kết nối, đã đồng bộ, gặp lỗi, khoảng thời gian và mức độ đầy đủ |
| FR-015 | P0 | Thời hạn lưu và xóa | Dữ liệu hết hạn hoặc đã xóa không xuất hiện trong lần tìm kiếm mới; thao tác được ghi vào lịch sử |

### 8.3. Connector P0

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-020 | P0 | Calendar chỉ đọc | Đọc sự kiện và hạn chót được cấp quyền; giữ mã nguồn, múi giờ và đường dẫn mở lại |
| FR-021 | P0 | Jira chỉ đọc | Đọc issue, người phụ trách, hạn chót, trạng thái và thời điểm thay đổi trong dự án được cấp quyền |
| FR-022 | P0 | Discord/VLearn chỉ đọc | Chỉ đọc channel, course hoặc feed được người dùng chọn |
| FR-023 | P0 | Gmail chỉ đọc | Chỉ đọc mailbox, label hoặc thread được pilot phê duyệt; không lưu cookie đăng nhập |
| FR-024 | P0 | Connector gặp lỗi | Một connector lỗi không được chặn bản tóm lược, hỏi đáp hoặc các nguồn còn lại |

### 8.4. Vòng đời thông tin ghi nhớ

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-030 | P0 | Tạo đề xuất ghi nhớ | Mỗi đề xuất có loại thông tin, chủ thể, nội dung, mức tin cậy, mã bằng chứng và phiên bản bộ trích xuất |
| FR-031 | P0 | Xác nhận thông tin | Điều người dùng tự khai báo có thể được xác nhận trực tiếp; sở thích do hệ thống suy ra cần người dùng xác nhận hoặc một quy tắc củng cố có lưu phiên bản |
| FR-032 | P0 | Mâu thuẫn và phiên bản | Thông tin mâu thuẫn tạo trạng thái cần xác minh hoặc phiên bản mới; không ghi đè lịch sử đã xác nhận |
| FR-033 | P0 | Thời hạn hiệu lực | Mục tiêu, hạn chót và cam kết có thời điểm bắt đầu, kết thúc hoặc được ghi rõ là chưa biết |
| FR-034 | P0 | Quyền kiểm soát ghi nhớ | Người dùng có thể xác nhận, sửa, bác bỏ, xóa và xem bằng chứng |
| FR-035 | P0 | Phản hồi và giảm ưu tiên | Phản hồi tiêu cực làm giảm mức ưu tiên; việc giảm ưu tiên không xóa bằng chứng gốc trước thời hạn lưu |

### 8.5. Trợ lý hỗ trợ học viên và bản tóm lược

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-040 | P0 | Khung chương trình | Nhập được khóa học, múi giờ, nhóm, vai trò, sản phẩm bàn giao và mức độ đáng tin của nguồn |
| FR-041 | P0 | Vòng đời thông tin | Nội dung hỗ trợ các trạng thái mới, đã cập nhật, đã hủy, đã thay thế và mâu thuẫn; các phiên bản liên kết với nhau |
| FR-042 | P0 | Chọn nội dung phù hợp | Lọc theo nhóm, vai trò và người phụ trách trước khi AI tham gia sắp xếp hoặc diễn đạt |
| FR-043 | P0 | Bản tóm lược hằng ngày | Có năm phần: `Cần xử lý`, `Thay đổi`, `Việc của bạn`, `Đang chờ` và `Nguồn đã kiểm tra` |
| FR-044 | P0 | Chặn nội dung không có nguồn | Nội dung không có bằng chứng người dùng được phép mở thì không được xuất hiện trong bản tóm lược |
| FR-045 | P0 | Báo mức độ đầy đủ | Khi một nguồn gặp lỗi, bản tóm lược phải nói rõ thông tin có thể chưa đầy đủ hoặc chưa xác định; không được báo là đã kiểm tra đủ |

### 8.6. Hỏi và tìm thông tin

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-050 | P0 | Tìm kiếm kết hợp | Lọc theo quyền, thời gian và dự án; kết hợp dữ liệu có cấu trúc với tìm kiếm văn bản và tìm kiếm theo ý nghĩa; kết quả giữ mã bằng chứng |
| FR-051 | P0 | Hỏi về một nội dung | Ưu tiên nội dung được chọn nhưng vẫn kiểm tra nguồn khác và thông tin mâu thuẫn |
| FR-052 | P0 | Khẳng định có cấu trúc | Mỗi phần trả lời về sự thật có mã nguồn dẫn hoặc trạng thái `uncertain` — chưa chắc chắn, `abstained` — từ chối trả lời |
| FR-053 | P0 | Kiểm tra nguồn dẫn | Nếu nguồn không chứng minh được nội dung hoặc người dùng không có quyền mở, phần trả lời bị loại hoặc toàn bộ câu trả lời phải từ chối |
| FR-054 | P0 | Hội thoại nối tiếp | Câu hỏi sau giữ được nội dung phiên trò chuyện; người dùng có thể bắt đầu lại hoặc xóa phiên |
| FR-055 | P0 | Phản hồi câu trả lời | Lưu đánh giá hữu ích, không đúng hoặc thiếu nguồn cùng phiên bản mô hình, chỉ dẫn và cách tìm kiếm đã dùng |

### 8.7. Hành động

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-060 | P0 | Bản nháp hành động | Bản nháp liên kết với nội dung nguồn, câu trả lời và bằng chứng; gửi lại yêu cầu không tạo bản trùng |
| FR-061 | P0 | Trường còn thiếu | Thời gian hoặc người phụ trách còn mơ hồ phải để trống; người dùng bắt buộc nhập hoặc chọn |
| FR-062 | P0 | Xem, sửa và xác nhận | Không tạo lời nhắc hoặc mở ứng dụng lịch trước khi người dùng xác nhận |
| FR-063 | P0 | Lời nhắc trong sản phẩm | Có trạng thái đã lên lịch, đến hạn, hoàn thành và đã hủy; xuất hiện trong bản tóm lược |
| FR-064 | P0 | Chuyển sang ứng dụng lịch | Mẫu tạo sự kiện hoặc tệp `.ics` có tên, thời gian, múi giờ, ghi chú và nguồn |
| FR-065 | P0 | Thông báo đúng trạng thái | Phân biệt “đã xác nhận bản nháp” với “đã mở trong ứng dụng lịch”; không tuyên bố sự kiện đã được lưu nếu chưa có bằng chứng |
| FR-066 | P0 | Nguồn thay đổi | Gắn cảnh báo nhưng không tự sửa hành động đã xác nhận |
| FR-067 | P0 | Đồng bộ lịch tường minh | Chỉ tạo Google Calendar event khi task thuộc người dùng, đã xác nhận, có thời gian rõ ràng và người dùng bấm Sync; retry không tạo event trùng |
| FR-068 | P0 | Tạo event/task/todo bằng hội thoại | Lệnh tạo tường minh dựng preview cho đúng user; event cần title, start và end/duration, task/todo cần title và deadline; thiếu trường phải hỏi lại; chỉ thực thi khi user bấm Chấp nhận |
| FR-069 | P0 | Thao tác trực tiếp trên lịch | Người dùng tự tạo, sửa, kéo đổi giờ hoặc xóa sự kiện thì ghi ngay, không hiện hộp thoại xác nhận; mỗi thao tác có Undo trong 10 giây; máy chủ kiểm lại ownership và scope, không tin field client gửi lên; agent không được gọi hai thao tác sửa và xóa |

Ranh giới giữa FR-068 và FR-069 là **chủ thể khởi tạo**. Agent đề xuất thì phải
qua bản nháp và nút Chấp nhận trong mọi trường hợp. Người dùng thao tác trực
tiếp thì bản thân thao tác là sự xác nhận.

### 8.8. Lịch sử, đánh giá và vận hành

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-070 | P0 | Lịch sử thay đổi | Việc đồng bộ, phân tích, xác nhận, tìm kiếm, dẫn nguồn, nhận phản hồi và đổi trạng thái hành động đều lưu người thực hiện, thời điểm và phiên bản |
| FR-071 | P0 | Số liệu đã loại thông tin nhạy cảm | Dữ liệu đo lường sản phẩm không chứa nội dung gốc của email, tin nhắn, item hoặc câu hỏi |
| FR-072 | P0 | Xuất dữ liệu đánh giá | Xuất được dữ liệu kiểm thử, kết quả dự đoán và phiên bản đã loại thông tin nhạy cảm để kiểm tra lỗi tái diễn |
| FR-073 | P0 | Tình trạng nguồn | Người vận hành xem được số lỗi tổng hợp và độ trễ hàng chờ mà không cần đọc nội dung gốc |

### 8.9. Nhắc việc và thông báo

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-090 | P0 | Mốc nhắc mặc định | Mặc định nhắc trước 1 ngày và trước 30 phút so với hạn chót; người dùng sửa được từng mốc và tắt được từng loại |
| FR-091 | P0 | Đẩy thông báo qua tiện ích | Thông báo hiện được khi trình duyệt mở; mỗi lần giao được ghi lại để khởi động lại tiến trình nền không giao trùng |
| FR-092 | P0 | Bỏ qua khác hủy việc | `Bỏ qua` chỉ chuyển lời nhắc sang đã hủy và không đụng tới công việc; chỉ thao tác hủy việc trong màn hình chi tiết mới chuyển công việc sang đã hủy và rút khỏi mẫu số của chỉ số chính |
| FR-093 | P0 | Nhắc lại | `Nhắc lại` dời thời điểm giao thông báo, không đổi trạng thái công việc; số lần đã nhắc lại được lưu |
| FR-094 | P0 | Mức ưu tiên tính bằng luật | Mức ưu tiên tính từ khoảng cách tới hạn, mức độ đáng tin của nguồn, công việc có thuộc người dùng không và số lần đã bỏ qua; mô hình chỉ được xếp lại thứ tự trong cùng một bậc và không được đổi mức độ đáng tin của nguồn |
| FR-095 | P0 | Chống bão thông báo | Lời nhắc cùng khung giờ được gộp thành một thông báo; có trần số thông báo trong một giờ; có giờ yên lặng và lời nhắc rơi vào giờ yên lặng được dời tới đầu khung giờ hoạt động |
| FR-096 | P0 | Lý do bỏ qua | Khi bỏ qua, người dùng chọn được một lý do trong `không cần nữa`, `đã làm ở chỗ khác`, `hạn chót sai`; lý do làm giảm mức ưu tiên lần sau và được lưu làm dữ liệu đánh giá, không xóa bằng chứng gốc |
| FR-097 | P0 | Mở bằng chứng từ thông báo | Mỗi thông báo mở được nội dung nguồn đã tạo ra công việc đó; thông báo không có bằng chứng người dùng được phép mở thì không được hiển thị |
| FR-098 | P0 | Telegram cho tóm tắt và nhắc việc | User đã liên kết và tự bật nhận được daily brief/reminder qua Telegram; user chưa liên kết nhận 0 nội dung nội bộ |
| FR-099 | P0 | Giao đa kênh không chặn nhau | Receipt tách theo kênh; retry không giao trùng trên cùng kênh và một kênh giao thành công không làm kênh còn lại mất lượt |

### 8.10. Lịch tuần và dữ liệu lịch đã lưu

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-100 | P0 | Lịch xem theo tuần | Hiển thị sự kiện và công việc có hạn theo tuần, kèm trạng thái rỗng, chưa đầy đủ và nguồn lỗi |
| FR-101 | P0 | Nhiều lịch | Liệt kê các lịch người dùng có quyền, cho chọn lịch nào hiển thị và chọn lịch đích khi ghi; sản phẩm không tạo lịch mới |
| FR-102 | P0 | Lưu lại lịch đã đọc | Sự kiện đã đọc được lưu và hiển thị ngay ở lần mở sau, làm mới ở nền, luôn kèm thời điểm cập nhật gần nhất; không trình bày dữ liệu đã lưu như dữ liệu thời gian thực |
| FR-103 | P0 | Đồng bộ tăng dần | Lần đọc sau chỉ lấy phần thay đổi; con trỏ đồng bộ hết hiệu lực thì đọc lại toàn bộ khoảng thời gian thay vì báo lỗi |
| FR-104 | P0 | Sự kiện không còn ở nguồn | Sự kiện đã bị xóa phía nguồn được đánh dấu và không tự tạo lại |
| FR-105 | P0 | Cách ly dữ liệu trong bộ nhớ đệm | Không người dùng nào đọc được sự kiện đã lưu của người dùng khác; có ca kiểm thử đọc chéo người dùng |

### 8.11. Học thích ứng có kiểm soát (P1)

Năng lực mondaiy học từ dữ liệu người dùng để thích ứng và tiến hóa: học thói
quen, cách làm việc và phong cách giao tiếp. Thiết kế chi tiết tại
[ADR-017](../engineering/adr/adr-017-adaptive-learning-p1-hermes.md). Tất cả
mức P1 — không bật production trước khi qua pilot gate.

| Mã | Mức | Yêu cầu | Điều kiện nghiệm thu |
| --- | --- | --- | --- |
| FR-110 | P1 | Đồng ý theo từng năng lực học | Bốn công tắc riêng (học từ chat, phong cách, kỹ năng, thói quen) mặc định tắt; thu hồi dừng quan sát mới ngay và loại dữ liệu khỏi lần học kế tiếp |
| FR-111 | P1 | Xem "Mondaiy đã học gì" | Ba mục Routine · Cách làm việc · Phong cách; mỗi thẻ có tóm tắt bằng chứng, mức tin cậy, phiên bản và trạng thái; người dùng không cần đọc file hay diff |
| FR-112 | P1 | Duyệt đề xuất bằng thẻ chat-native | Thẻ "Mondaiy nhận thấy…" với Chấp nhận · Sửa · Không đúng · Đừng gợi ý lại; đề xuất chưa được chấp nhận không thay đổi câu trả lời |
| FR-113 | P1 | Reset học theo lớp | Xóa riêng từng lớp (phong cách, kỹ năng, thói quen) hoặc tất cả; reset đưa hành vi về chuẩn gốc ngay lượt kế tiếp, không xóa task/lịch/dữ liệu nguồn |
| FR-114 | P1 | Quay về phiên bản trước | Kỹ năng/phong cách đã chấp nhận rollback về phiên bản tốt gần nhất trong một thao tác; mọi thay đổi ghi audit |
| FR-115 | P1 | Tự động hóa bằng ngôn ngữ thường | Tạo routine bằng form các ô dễ hiểu hoặc agent hỏi bù phần thiếu trong chat; người dùng không cần hiểu khái niệm lịch cron |

## 9. Quy tắc nghiệp vụ

| Mã | Quy tắc |
| --- | --- |
| BR-01 | Bằng chứng không tự động trở thành thông tin ghi nhớ chính thức. |
| BR-02 | Thông tin người dùng tự khai báo được ưu tiên hơn điều hệ thống suy ra; sửa thông tin phải tạo phiên bản mới. |
| BR-03 | Mọi thông tin ghi nhớ chính thức và khẳng định về sự thật đều phải truy được về bằng chứng. |
| BR-04 | Trang người dùng đã đọc không được dùng để khẳng định danh tính, sở thích hoặc cam kết khi chưa được xác nhận. |
| BR-05 | Chỉ chuyển hạn chót thành thời gian chuẩn khi có đủ ngày, giờ và múi giờ; luôn giữ câu chữ nguyên bản. |
| BR-06 | Mức độ đáng tin của nguồn ảnh hưởng đến lựa chọn, nhưng thông tin mâu thuẫn vẫn phải được hiển thị. |
| BR-07 | Cảnh báo nguồn chưa đầy đủ hoặc chưa xác định phải xuất hiện trước mọi đề xuất và hành động. |
| BR-08 | Mọi thao tác ghi vào ứng dụng bên ngoài **do hệ thống khởi tạo** cần người dùng xác nhận riêng tại thời điểm thực hiện. Người dùng thao tác trực tiếp trên giao diện lịch thì chính thao tác đó là sự xác nhận. |
| BR-09 | Nguồn thay đổi không tự động sửa hoặc hủy hành động đã xác nhận. |
| BR-10 | Dữ liệu đã bị thu hồi quyền hoặc đã xóa không được xuất hiện trong lần tìm kiếm mới. |
| BR-11 | P0 không theo dõi màn hình, lịch sử duyệt web hoặc nội dung trang web bất kỳ. |
| BR-12 | Khi kết nối ngoài gặp lỗi, hệ thống phải quay về cách lưu trang hoặc nhập nội dung thủ công và không làm ứng dụng ngừng hoạt động. |
| BR-13 | mondaiy không bao giờ tự ghi vào ứng dụng bên ngoài. Đề xuất của mondaiy chỉ thành bản nháp; chỉ thao tác của người dùng mới sinh ra thay đổi thật. |
| BR-14 | Thao tác ghi trực tiếp phải hoàn tác được trong 10 giây. Sự kiện bị xóa vẫn được giữ bản lưu tới hết thời hạn lưu. |
| BR-15 | Bỏ qua một lời nhắc không đổi trạng thái công việc. Chỉ thao tác hủy việc tường minh mới rút công việc khỏi mẫu số của chỉ số chính. |
| BR-16 | Mức ưu tiên do quy tắc quyết định. Mô hình chỉ được xếp lại thứ tự trong cùng một bậc, không được đổi mức độ đáng tin của nguồn. |

## 10. Mô hình dữ liệu tối thiểu

Phần này dành cho nhóm kỹ thuật. Tên bảng và tên trường được giữ bằng tiếng Anh
vì chúng là mã dùng trực tiếp trong cơ sở dữ liệu.

### Người dùng và quyền truy cập

- `users`, `profiles`, `profile_versions`
- `consents`, `source_connections`, `source_permissions`

### Bằng chứng

- `capture_events`
- `documents`, `document_versions`, `chunks`
- `meetings`, `transcript_artifacts`, `transcript_segments`
- `calendar_events` khi chức năng đọc lịch được bật

### Thông tin ghi nhớ

- `memory_candidates`
- `memories`, `memory_versions`
- `memory_evidence`
- `memory_feedback`

Các trường tối thiểu của một phiên bản thông tin ghi nhớ:

`kind`, `subject`, `predicate`, `object_json`, `status`, `confidence`, `importance`, `valid_from`, `valid_to`, `first_observed_at`, `last_reinforced_at`, `supersedes_memory_id`, `extractor_version`.

### Trợ lý hỗ trợ học viên

- `programs`, `program_frames`, `program_frame_versions`
- `teams`, `roles`, `memberships`
- `information_items`, `information_item_versions`
- `briefs`, `brief_items`

### Hỏi và Hành động

- `conversations`, `messages`, `citations`
- `action_drafts`, `reminders`, `calendar_handoffs`
- `feedback`, `audit_events`, `ingestion_jobs`

### Lịch và nhắc việc

- `calendar_events` — sự kiện đã đọc, khóa theo `(user_id, calendar_id, event_id)`, có trạng thái `active`, `deleted`, `stale`
- `calendar_sources` — các lịch người dùng có quyền, cờ hiển thị và cờ lịch đích khi ghi
- `notification_preferences` — mốc nhắc, giờ yên lặng, trần số thông báo mỗi giờ, tắt bật theo nguồn
- `notification_deliveries` — mỗi lần giao một thông báo, phản hồi của người dùng và lý do bỏ qua

`reminders` giữ đúng bốn trạng thái của [FR-063](#87-hành-động). Bỏ qua ghi vào
`reminders` và `notification_deliveries`, không ghi vào `tasks`. Con trỏ đồng bộ
tăng dần dùng `sync_cursors` khóa theo `(user_id, key)`.

Tệp gốc có kích thước lớn được lưu trong kho tệp. PostgreSQL lưu phần chữ đã
được chuẩn hóa, thông tin mô tả và khóa dẫn tới tệp gốc. Mọi dòng dữ liệu thuộc
về người dùng hoặc tổ chức đều phải có chủ sở hữu, phạm vi và quy tắc RLS.

## 11. Quy tắc cho phép mondaiy sử dụng công cụ

Trong phạm vi P0, mondaiy chỉ được phép gọi các công cụ sau. Tên được giữ
nguyên vì đây là mã dùng trong phần mềm:

- `search_evidence`
- `recall_memories`
- `get_user_context`
- `get_program_context`
- `get_meeting_transcript`
- `get_upcoming_actions`
- `create_action_draft`

mondaiy không được phép gọi trực tiếp `send_message`, `create_calendar_event`,
`update_calendar_event`, `delete_calendar_event` hoặc `delete_external_action`.
Điều này ngăn sản phẩm tự gửi tin nhắn, tạo, sửa hoặc xóa hành động bên ngoài
khi người dùng chưa xác nhận.

`update_calendar_event` và `delete_calendar_event` tồn tại trong hệ thống nhưng
**chỉ endpoint thao tác trực tiếp của người dùng mới được gọi**, với ba điều
kiện: `actor_type = user`, máy chủ kiểm lại ownership và scope, và payload thực
thi đọc từ dữ liệu phía máy chủ chứ không nhận field tùy ý từ client. Hai tool
này không được bind vào agent. Danh sách tool của agent giữ nguyên bảy tool ở
trên.

```text
mondaiy đề xuất hành động
→ hệ thống lưu bản nháp
→ giao diện cho người dùng xem và sửa
→ người dùng xác nhận; yêu cầu lặp không tạo bản trùng
→ mở bản nháp trong ứng dụng bên ngoài hoặc thực hiện thao tác đã được phép
```

## 12. Yêu cầu về chất lượng hệ thống

### 12.1. Độ tin cậy

- Chỉ thêm bản ghi mới vào quá trình nhận dữ liệu; gửi lại không tạo bản trùng.
- Tiến trình nền chỉ báo đã nhận sau khi bằng chứng được lưu thành công.
- Hàng chờ hiển thị được số lần gửi lại, độ trễ và các bản ghi cần xử lý thủ công.
- Công cụ bên ngoài quá thời gian không làm mất bản nháp người dùng đã sửa.
- Việc sao lưu, khôi phục và quay lại phiên bản dữ liệu cũ được thử trước khi mời người dùng.

### 12.2. Tốc độ

- Đồng bộ nguồn chạy nền, không làm cản trở thao tác chính của ứng dụng.
- Ít nhất 95% lượt nhận một nhóm dữ liệu phản hồi trong 2 giây khi thử nghiệm.
- Ít nhất 95% lượt mở bản tóm lược hoàn thành trong 2 giây.
- Ít nhất 95% câu hỏi nhận phần trả lời đầu tiên trong 10 giây.
- Ít nhất 95% bản nháp hành động được tạo trong 3 giây.
- Kiểm thử tải tương đương 50 người dùng đang hoạt động.

### 12.3. Quyền riêng tư và an toàn

- Dùng dịch vụ đăng nhập của Supabase kết hợp RLS; khóa có quyền cao chỉ nằm ở máy chủ.
- Khóa OpenRouter không nằm trong tiện ích trình duyệt.
- Nội dung gốc không được ghi vào số liệu sử dụng hoặc nhật ký lỗi.
- Quy trình kiểm tra tự động phải phát hiện khóa bí mật và thông tin nhận dạng cá nhân bị đưa nhầm vào mã hoặc nhật ký.
- Có kiểm thử toàn bộ luồng xóa dữ liệu, thu hồi quyền và hết thời hạn lưu.

### 12.4. Khả năng tiếp cận và ngôn ngữ

- Mọi chức năng chính dùng được bằng bàn phím và luôn thể hiện rõ vị trí đang được chọn.
- Không chỉ dùng màu sắc để biểu thị trạng thái đồng bộ, mâu thuẫn hoặc ghi nhớ.
- Múi giờ luôn xuất hiện khi người dùng xem trước hành động.
- Câu chữ tiếng Việt phải rõ ràng; bằng chứng được giữ nguyên văn khi cần đối chiếu.

### 12.5. Chi phí

- So sánh mã băm và phần thay đổi trước khi dùng AI phân tích lại nội dung.
- Ưu tiên quy tắc và truy vấn dữ liệu có cấu trúc trước khi gọi mô hình AI.
- Gom các công việc nền thành nhóm khi có thể.
- Giới hạn lượng nội dung gửi vào mô hình trong mỗi lượt.
- Mô hình tạo văn bản và mô hình phục vụ tìm kiếm phải có thể thay thế; lựa chọn dựa trên kết quả đo chất lượng và chi phí.

## 13. Dữ liệu đo lường sản phẩm

Phần này dành cho nhóm sản phẩm và kỹ thuật. Tên sự kiện và thuộc tính được giữ
nguyên vì chúng là mã dùng trong hệ thống đo lường.

| Sự kiện | Được ghi khi | Thuộc tính được phép lưu |
| --- | --- | --- |
| `capture_enqueued` | Dữ liệu được đưa vào hàng chờ | `source_type`, `mode`, `size_bucket` |
| `capture_synced` | Đồng bộ thành công | `latency`, `duplicate`, `version_created` |
| `capture_failed` | Đồng bộ thất bại | `source_type`, `error_class`, `retry_count` |
| `memory_candidate_created` | Tạo đề xuất ghi nhớ | `kind`, `confidence_bucket`, `source_type` |
| `memory_status_changed` | Trạng thái ghi nhớ thay đổi | `from`, `to`, `actor_type` |
| `brief_generated` | Tạo bản tóm lược | `coverage`, `item_count`, `source_count` |
| `brief_opened` | Người dùng mở bản tóm lược | `time_since_generated` |
| `ask_submitted` | Người dùng gửi câu hỏi | `intent`, `contextual/global` |
| `answer_rendered` | Hiển thị câu trả lời | `latency`, `citation_count`, `abstained`, `conflict` |
| `answer_feedback` | Người dùng đánh giá câu trả lời | `helpful/incorrect/missing_source` |
| `action_draft_created` | Tạo bản nháp hành động | `origin`, `type`, `missing_fields` |
| `action_confirmed` | Người dùng xác nhận hành động | `type`, `edit_count`, `time_to_confirm` |
| `calendar_handoff_opened` | Mở bản nháp trong ứng dụng lịch | `provider`, `handoff_type` |
| `consent_changed` | Người dùng thay đổi sự đồng ý | `source_type`, `state` |
| `reminder_delivered` | Thông báo được giao tới người dùng | `lead_time_bucket`, `priority_band`, `batched_count` |
| `reminder_acted` | Người dùng phản hồi thông báo | `action: completed/dismissed/snoozed`, `dismiss_reason`, `snooze_count` |
| `calendar_item_edited` | Người dùng tự sửa hoặc xóa trên lịch | `op: create/update/delete`, `undo_used` |

Không ghi nội dung email, tin nhắn, item, câu hỏi hoặc câu trả lời vào dữ liệu
đo lường sản phẩm.

## 14. Kế hoạch đánh giá

Bộ dữ liệu kiểm thử chuẩn gồm:

1. đồng bộ nguồn, quản lý phiên bản và chống bản trùng;
2. trích xuất và xác nhận thông tin ghi nhớ;
3. thay đổi, mâu thuẫn và thời hạn hiệu lực;
4. hỏi đáp trên một nguồn, nhiều nguồn, nguồn cũ, nguồn mâu thuẫn và câu hỏi không đủ bằng chứng;
5. độ chính xác của tên việc, thời gian, múi giờ, trường còn thiếu và nguồn trong hành động;
6. trường hợp người dùng không có quyền hoặc đã thu hồi quyền.

Mỗi mẫu kiểm thử phải có bản chụp nguồn, phiên bản, đáp án chuẩn, người phản
biện và trạng thái xử lý bất đồng. AI không được tự tạo đồng thời cả câu hỏi
kiểm thử và đáp án chuẩn nếu chưa có người phản biện kiểm tra.

Chi tiết tại [kế hoạch đánh giá](../qa/evaluation-plan.md).

## 15. Kế hoạch sáu tuần

Mỗi tuần là một đợt làm việc từ thứ Hai đến Chủ nhật.

| Tuần | Kết quả cần tạo ra | Điều kiện kết thúc tuần |
| --- | --- | --- |
| Tuần 1 | Chốt quyết định kiến trúc, cấu trúc dữ liệu, RLS và bộ dữ liệu kiểm thử; một connector đọc được dữ liệu tới máy chủ | Nguồn gốc dữ liệu đúng; người dùng này không đọc được dữ liệu của người dùng khác |
| Tuần 2 | Ít nhất hai connector, hàng chờ bền vững, phiên bản item và trạng thái nguồn | Khởi động lại không mất dữ liệu; gửi lại không tạo bản trùng |
| Tuần 3 | Đề xuất, xác nhận và quản lý phiên bản ghi nhớ; tìm lại thông tin; nhập khung chương trình | 100% thông tin ghi nhớ chính thức có bằng chứng |
| Tuần 4 | Bản tóm lược, phân tích thay đổi nguồn, hỏi về một nội dung và kiểm tra nguồn | 100% khẳng định có nguồn; không có sự thật tự tạo |
| Tuần 5 | Hành động, mở bản nháp trong ứng dụng lịch, nhóm tự dùng thử và cải thiện độ ổn định | Không có hành động thiếu xác nhận; toàn bộ hành trình chạy đạt |
| Tuần 6 | Thử nghiệm với 5–10 người, xử lý lỗi hằng ngày và lập báo cáo | Đạt nguyên tắc an toàn; tỷ lệ hoàn thành công việc trong tuần tăng so với baseline |

## 16. Phụ thuộc và rủi ro

| Rủi ro | Cách giảm rủi ro |
| --- | --- |
| Phạm vi phình thành trợ lý làm mọi việc | Chỉ xây năng lực dùng chung khi hành trình hỗ trợ học viên thật sự cần |
| Connector hoặc webhook làm mất item | Dùng hàng chờ bền vững, checkpoint và gửi lại không tạo bản trùng |
| Cùng một item ghi đè lịch sử | Lưu phiên bản item không thể sửa theo mã băm nội dung |
| Thông tin ghi nhớ sai bị coi là sự thật | Tách đề xuất khỏi thông tin đã xác nhận; mọi thông tin chính thức có bằng chứng và trạng thái |
| Một connector hoặc OAuth kéo dài | Dùng feature flag; pilot chỉ giữ các connector đạt gate |
| AI bịa thông tin | Giới hạn phạm vi tìm kiếm, bắt buộc nguồn dẫn, kiểm tra câu trả lời và từ chối khi thiếu bằng chứng |
| Người dùng đọc được dữ liệu của người khác | Áp dụng RLS và kiểm thử các trường hợp không có quyền trên mọi loại dữ liệu và nguồn dẫn |
| Bị phụ thuộc vào một giải pháp mã nguồn mở | Kết nối qua lớp trung gian; PostgreSQL vẫn là nơi lưu dữ liệu chính |
| Nhiều người sửa cùng chỗ gây xung đột mã | Chốt giao ước trước, phân người phụ trách tệp, chia thay đổi nhỏ và có một người tích hợp |
| Bắt đầu thử nghiệm quá muộn | Ngừng thêm tính năng vào cuối tuần 5; kết nối chưa đạt tiêu chí phải được tắt |

## 17. Điều kiện để bắt đầu phát triển một yêu cầu

- Thuật ngữ sản phẩm, trường hợp ứng dụng đầu tiên và quyết định kiến trúc đã được duyệt.
- Đã xác nhận khóa học, 5–10 người thử nghiệm, múi giờ và người chịu trách nhiệm phía người hướng dẫn hoặc quản trị.
- Danh sách nguồn được phép, nội dung xin đồng ý và dự thảo thời hạn lưu đã có người phụ trách.
- Quy ước về sự kiện, API, dữ liệu và ghi nhớ đã được phản biện.
- Có dữ liệu mẫu cho các connector được chọn trong Calendar, Jira, Discord, VLearn và Gmail.
- Bộ dữ liệu kiểm thử bản đầu có đồng bộ nguồn, ghi nhớ, hỏi đáp, mâu thuẫn, câu hỏi không thể trả lời và hành động.
- Giao diện đã thiết kế trạng thái thành công, trống, chưa đầy đủ, mâu thuẫn, từ chối trả lời, đã thu hồi quyền và chờ xác nhận.
- Mỗi yêu cầu P0 có người phụ trách, ước lượng, cách đo và cách kiểm thử.

## 18. Điều kiện hoàn thành phiên bản sáu tuần

- Toàn bộ hành trình chạy được: item từ nguồn → phiên bản và mâu thuẫn → bản tóm lược cá nhân → câu hỏi có nguồn → bản nháp hành động → xác nhận.
- 100% nội dung được công bố và phần trả lời về sự thật có nguồn người dùng mở được.
- 100% thông tin ghi nhớ chính thức có bằng chứng.
- Tìm được 100% thông tin có trong các nguồn đã cam kết hỗ trợ trên bộ dữ liệu kiểm thử có phạm vi rõ ràng.
- Không tự tạo hạn chót hoặc người phụ trách.
- Không trình bày sở thích suy ra như thông tin đã xác nhận.
- Không có hành động do hệ thống khởi tạo xảy ra trước khi xác nhận; thời gian mơ hồ không được tự điền.
- Thao tác trực tiếp trên lịch hoàn tác được; không người dùng nào đọc được sự kiện đã lưu của người khác.
- Bỏ qua lời nhắc không làm đổi trạng thái công việc và không rút công việc khỏi mẫu số của chỉ số chính.
- Mất mạng, khởi động lại và gửi lại không làm mất dữ liệu hoặc tạo bản trùng.
- Khi nguồn gặp lỗi, sản phẩm nói rõ thông tin chưa đầy đủ hoặc chưa xác định.
- Kiểm thử RLS, thu hồi và xóa dữ liệu, lịch sử thay đổi và dữ liệu đo lường đều đạt.
- Đạt mục tiêu tốc độ khi kiểm thử tải 50 người dùng.
- Báo cáo thử nghiệm có chỉ số, nhóm lỗi và quyết định cho giai đoạn tiếp theo.
- Tỷ lệ hoàn thành công việc trong tuần cao hơn baseline trước thử nghiệm.

## 19. Quyết định còn mở

| Mã | Quyết định cần chốt | Người chịu trách nhiệm |
| --- | --- | --- |
| OD-01 | Khóa học, người dùng thử và nguồn thật sẽ dùng trong thử nghiệm | Quản lý dự án và người hướng dẫn |
| OD-02 | Thời hạn lưu item từ nguồn và lịch sử trò chuyện | Quản lý dự án và Trưởng nhóm kỹ thuật |
| OD-03 | Mô hình dùng để trò chuyện, phân tích và tìm kiếm qua OpenRouter | Người phụ trách AI và ghi nhớ |
| OD-04 | Connector nào đủ ổn định để bật khi thử nghiệm | Trưởng nhóm kỹ thuật |
| OD-05 | Người xử lý thông tin mâu thuẫn và câu hỏi chưa trả lời được mỗi ngày | Quản lý dự án và người hướng dẫn |
| OD-06 | Giới hạn chi phí cho mỗi người dùng trong một ngày | Quản lý dự án và Trưởng nhóm kỹ thuật |
| OD-07 | Extension có được thu thập nội dung trang web để làm ngữ cảnh cho AI hay không | Quản lý dự án và Trưởng nhóm kỹ thuật |

### OD-07 — phạm vi thu thập của extension

Câu hỏi: extension chỉ hiển thị trạng thái và thao tác, hay được đọc nội dung
trang người dùng đang mở để bổ sung ngữ cảnh cho AI?

Trạng thái hiện tại là **chưa chốt**. Cho tới khi có quyết định:

- P0 giữ nguyên theo [ADR-002](../engineering/adr/adr-002-connector-first-p0-scope.md):
  dữ liệu chỉ vào hệ thống qua connector người dùng chủ động kết nối; không theo
  dõi màn hình, lịch sử duyệt web hay nội dung trang web tùy ý.
- Không đưa năng lực này vào backlog P0, không thiết kế UI cho nó, không viết
  code thu thập nội dung trang.

Muốn mở lại thì phải có ADR mới ghi rõ: allow-list trang được đọc, cách xin và
thu hồi consent, thời hạn lưu, cách người dùng xem và xóa dữ liệu đã thu, và
phương án rollback. Đây là thay đổi trọng yếu về quyền riêng tư nên cần Quản lý
dự án và Trưởng nhóm kỹ thuật phê duyệt, đồng thời cập nhật mục Ngoài phạm vi
của PRD. Hạn xem xét: sau thử nghiệm.
