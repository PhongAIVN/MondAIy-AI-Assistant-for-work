# ADR-003 — Gmail và Discord đi trước trong hai tuần build

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | PM, PO/QC |
| Last updated | 2026-08-05 |
| Related | [ADR-002](adr-002-connector-first-p0-scope.md) · [Roadmap](../../product/roadmap-6-weeks.md) · [PRD](../../product/prd.md) |

## Bối cảnh

Plan hai tuần của Technical Lead chọn Gmail làm connector xây trước nhất, Discord
làm connector thứ hai, và không đụng tới Calendar, Jira hay VLearn.

Điều này ngược với thứ tự cắt phạm vi đã ghi trong
[roadmap](../../product/roadmap-6-weeks.md): nếu trễ đường găng thì **Gmail là
thứ bị cắt đầu tiên**. Thứ tự đó ngầm định Gmail là nguồn ít giá trị nhất, nên
xây nó trước là mâu thuẫn với tài liệu đã duyệt.

Không ghi lại thì sáu tuần nữa không ai nhớ vì sao làm ngược, và lần cắt phạm vi
tiếp theo sẽ cắt nhầm.

## Quyết định

1. Hai tuần build (04/08–16/08) làm Gmail trước, Discord thứ hai. Calendar, Jira
   và VLearn chưa đụng tới.
2. Thứ tự cắt phạm vi trong roadmap **vẫn giữ nguyên** cho các sprint sau. Đây là
   ngoại lệ cho hai tuần này, không phải sửa luật.
3. Nếu đến 15/08 mà pipeline chưa chạy thông hai nguồn, cắt Discord trước, giữ
   Gmail — vì Gmail đã đi qua toàn bộ chín bước pipeline còn Discord thì chưa.

## Lý do

**Gmail cho dữ liệu thật ngay.** Cả bốn người đều có hộp thư thật với nội dung
thật, đủ đa dạng để chạy hết crawl, normalize, filter, extract và cluster. Discord
của cohort thưa tin, có tuần không có gì để rút trích.

**Gmail là nguồn khó nhất về mặt lọc.** Thư quảng cáo, thông báo tự động, chuỗi
trả lời lồng nhau. Nếu bước filter chịu được Gmail thì các nguồn còn lại nhẹ hơn
nhiều. Làm nguồn dễ trước rồi mới gặp nguồn khó là cách chắc chắn phải viết lại.

**Quyền `gmail.readonly` không mở rộng ranh giới riêng tư.** Gmail đã nằm trong
năm nguồn ADR-002 cho phép. Đây không phải thêm nguồn mới, chỉ là đổi thứ tự.

## Hệ quả

**Chấp nhận:** nếu trễ, thứ bị cắt là nguồn nhóm đã bỏ công xây, không phải nguồn
chưa động tới. Rủi ro này có thật, nhưng bù lại pipeline được kiểm chứng bằng dữ
liệu khó ngay từ tuần đầu.

**Phải làm:** khi Calendar và Jira vào sau, chúng dùng lại đúng đường ống này. Nếu
phải sửa schema cho vừa, tức là schema chưa đủ tổng quát và cần sửa ngay ở CP0,
không đợi.

**Không đổi:** phạm vi năm nguồn trong ADR-002, và luật không thêm nguồn mới nếu
chưa có ADR.

## Việc kèm theo

| Việc | Jira | DRI |
| --- | --- | --- |
| Gmail crawl, normalize, filter có provenance | TAPB-121 | Phong |
| Discord fetch ra raw_message đúng shape | TAPB-122 | An |
| Cắm Discord vào pipeline chung | TAPB-130 | An |
