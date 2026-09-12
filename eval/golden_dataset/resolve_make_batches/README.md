# Golden dataset nháp — make_batches và resolve (CP2, TAPB-121)

> **DRAFT — chưa phải fixture chính thức.** Kỹ sư (Phong) soạn để có gì đó chạy
> được ngay, không thay cho việc Dũng (PO/QC) tự soạn hoặc duyệt lại theo đúng
> quy trình CP2. Coi bộ này là điểm khởi đầu để sửa, không phải điều kiện dừng
> đã chốt. Trước khi dùng để tick "Done" trên Jira, cần Dũng review từng case,
> thêm case còn thiếu theo góc nhìn QC, và ký tên duyệt trong PR.

## Vì sao tách riêng khỏi `fetch_norm_filter/`

`fetch_norm_filter/` kiểm connector (raw payload thật của Gmail/Discord).
`make_batches` và `resolve` không nhận raw payload — chúng nhận `filtered_message`
và `extracted_item` (dữ liệu đã qua nhiều bước biến đổi), nên fixture ở đây là
input dạng dict đã chuẩn hoá, không phải JSON thô từ API. Theo đúng format nhẹ
mà `filter_cases.json` đã dùng (mảng case phẳng), không dựng lại cây
`fixtures/`+`expected/`+`schema/` đầy đủ vì input/output ở 2 node này đơn giản
hơn nhiều so với normalize/filter connector.

## Cấu trúc

```text
resolve_make_batches/
├── README.md              # file này
├── resolve_cases.json     # case cho resolve_due_at() + resolve_assignee()
└── make_batches_cases.json  # case cho phép chia lô của make_batches_node
```

## Quy tắc đối chiếu (khớp code hiện tại)

**Thời gian** — `src/agents/pipeline/time_resolve.py::resolve_due_at()`:
chỉ trả `due_at` khi `time_expression` có đủ CẢ BA — token ngày, token giờ,
token timezone tường minh. Thiếu 1 trong 3 → `due_at=null`, `ambiguous=true`.
Không đoán (BR-05, PRD §9).

**Danh tính** — `src/agents/pipeline/identity_resolve.py::resolve_assignee()`:
chỉ xác nhận `assignee` là chính người dùng khi họ là người nhận trực tiếp
(`user_email` nằm trong `message.to`) VÀ gợi ý (`assignee_hint`) không chỉ đích
danh ai khác. Không có danh bạ đối chiếu tên người thứ ba — mọi trường hợp còn
lại để `assignee=null`, `assignee_ambiguous=true` (FR-061 áp dụng tương tự
BR-05 cho người phụ trách).

**make_batches** — `src/agents/pipeline/nodes/make_batches.py`: chia
`filtered_message` thành lô 6 phần tử/lô (`_BATCH_SIZE`, giảm từ 18 —
batch to làm LLM dilution, dễ bỏ sót tín hiệu rõ ràng), lô cuối có thể ít
hơn 6, không có lô rỗng thừa.

## Case còn thiếu, cần Dũng bổ sung (góc nhìn QC, kỹ sư chưa nghĩ tới)

- Múi giờ ghi bằng tên viết tắt hiếm gặp ngoài `ICT/GMT+7/UTC/GMT`
  (`_TZ_ABBREVIATIONS` trong `time_resolve.py` chỉ có 4 giá trị).
- `assignee_hint` là email cụ thể (không phải tên) trùng đúng `user_email`
  nhưng khác hoa/thường.
- Message có nhiều địa chỉ trong `to` (mailing list) — user nằm trong đó
  nhưng không phải người nhận duy nhất.
- Batch với đúng 0 filtered message (đã có unit test kỹ thuật, nhưng QC có
  thể muốn case riêng cho luồng "sync không có gì mới").
