# Golden Dataset cho Outlook — theo pipeline outlook-detail.drawio

Bộ case end-to-end riêng cho `OutlookConnector`, chạy qua đúng 3 stage đầu
deterministic của pipeline mô tả trong
`docs/projects/engineering/outlook-detail.drawio`:

```
RAW OUTLOOK EMAIL (Microsoft Graph API shape)
  -> NORMALIZATION   (OutlookConnector.normalize(), thật)
  -> RELEVANCE FILTER (filter_and_classify(), thật)
  -> EVIDENCE SELECTION (select_evidence(), thật)
```

Không cover Structured Extraction/Fact Verification/Group-Resolution/
Verified Work Context/Summary/Output Verification trong bộ này — 3 stage đó
cần LLM thật hoặc đã có golden dataset provider-agnostic riêng
(`eval/golden_dataset/evidence_verification/` cho Evidence Selection dạng
thuần + Fact Verification; Structured Extraction cần LLM nên không golden-test
được deterministic).

## Vì sao tách riêng khỏi `evidence_verification/`

`evidence_verification/` test hàm thuần (`select_evidence`, `verify_node`)
với input dựng tay, không đi qua connector thật. Bộ này ngược lại: input là
raw payload **đúng hình dạng Microsoft Graph API** (`from.emailAddress`,
`toRecipients`, `body.contentType`...), chạy qua `OutlookConnector.normalize()`
thật — bắt được lỗi cụ thể của Outlook (vd HTML `<script>/<style>` bị dính lại,
`receivedDateTime` thiếu tự ý đoán giờ, `hasAttachments` bị hiểu nhầm thành có
danh sách file) mà test hàm thuần không thấy được.

## Cấu trúc

```text
eval/outlook/
├── README.md
└── cases.json   # 102 case, tự chứa input/expected
```

Test chạy thật: `tests/test_agents/v1/test_outlook_pipeline_golden.py`.

## Danh sách case (102 case)

Sinh bằng `scripts/gen_outlook_pipeline_cases.py` — mỗi case tự validate
bằng chính `OutlookConnector.normalize()`/`filter_and_classify()` thật ngay
lúc sinh, không phải đoán tay. Nội dung mail dựng như mail thật: có chào hỏi,
đoạn ngữ cảnh, câu yêu cầu, lời kết, chữ ký — không phải 1 câu trần trụi kiểu
"Please submit X before Y." Sender/tên/công ty lấy từ ngân hàng tên thật
(Northwind, Contoso, Fabrikam, VietSoft...), không lặp lại "sender@example.edu".

| Nhóm | Số lượng | Mục tiêu kiểm |
| --- | --- | --- |
| OTL-001..035 | 35 | Mail thật nhiều đoạn (5 kịch bản EN + 3 kịch bản VI, xen kẽ HTML/text, đọc/chưa đọc) chứa action+deadline — filter accepted, `must_not_miss=true` |
| OTL-036..060 | 25 | Newsletter HTML thật (heading, list, nhiều section, footer unsubscribe) từ 3 mẫu công ty khác nhau, đã đọc — filter rejected |
| OTL-061..070 | 10 | `from` khớp/không khớp `provider_user_id` khác hoa/thường — `is_self` đúng cả 2 chiều |
| OTL-071..080 | 10 | `receivedDateTime` hợp lệ/thiếu/lỗi xen kẽ — `sent_at` resolved đúng theo từng case |
| OTL-081..090 | 10 | HTML có `<style>/<script>` xen giữa nội dung thật nhiều đoạn — bị loại khỏi text, giữ nguyên nội dung |
| OTL-091..102 | 12 | Mail RE: có lịch sử quoted-reply thật bên dưới (From/Sent/To/Subject) — text giữ nguyên cả phần quote, đúng hành vi thật của connector |

## Lưu ý khi thêm case mới

- Case "accepted" phải rơi vào nhánh `must_not_miss` hoặc `score >= 50` của
  `triage_email()` — 2 nhánh này quyết định thuần rule/score, KHÔNG gọi model
  classifier. Case rơi vào vùng `llm_judge` (score 15-49, hoặc unread mà điểm
  thấp) sẽ gọi `hf_mail_classifier` thật → test không còn deterministic.
- Case "rejected" nên dùng tín hiệu newsletter/automated/negative_state rõ
  ràng — nhánh `drop` cũng thuần rule, không gọi model.
- Đây là bộ case kỹ sư soạn khi implement, chưa phải fixture chính thức QA —
  cùng tinh thần `eval/golden_dataset/resolve_make_batches/README.md`.
