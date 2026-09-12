# Golden Dataset cho Evidence Selection + Fact Verification

Bộ case cho 2 stage mới trong pipeline task-extraction:
`src/agents/pipeline/nodes/evidence.py` (Evidence Selection) và
`src/agents/pipeline/nodes/verify.py` (Fact Verification) — theo kiến trúc mô
tả trong `docs/projects/engineering/outlook-detail.drawio`.

Test chạy trực tiếp bộ case này qua code thật:
`tests/test_agents/v1/test_evidence_verification_golden.py`. Không phải
fixture "mồ côi" — mỗi case đều được 1 test thật đọc và assert (khác lỗ hổng
đã ghi nhận ở `eval/golden_dataset/fetch_norm_filter/`: 18 fixture Gmail
chưa từng được code nào đọc).

## Cấu trúc

```text
eval/golden_dataset/evidence_verification/
├── README.md
├── evidence_selection_cases.json   # 6 case cho select_evidence()
└── fact_verification_cases.json    # 7 case cho verify_node()
```

Mỗi file là 1 list case tự chứa `{id, description, input, expected}` —
không tách fixture/expected riêng, theo đúng convention
`eval/golden_dataset/resolve_make_batches/`.

## evidence_selection_cases.json (100 case)

Sinh bằng `scripts/gen_evidence_selection_cases.py` (chạy lại được, tự verify
filler bank không dính từ khóa tín hiệu trước khi build case). Nhóm case:

| Nhóm | Số lượng | Mục tiêu kiểm |
| --- | --- | --- |
| EVD-001..025 | 25 | Email ngắn (<400 ký tự, EN+VI) giữ nguyên, không cắt |
| EVD-026..055 | 30 | Email dài, 1 câu tín hiệu giữa filler (EN/VI/urgency) — chọn đúng, loại filler |
| EVD-056..080 | 25 | 2 câu tín hiệu mạnh/yếu + filler, vượt `max_sentences=2` — giữ đúng câu điểm cao |
| EVD-081..090 | 10 | Toàn câu filler (không tín hiệu nào) — không crash |
| EVD-091..100 | 10 | Câu tín hiệu ở đầu VÀ cuối — giữ đúng thứ tự gốc, không sắp theo điểm |

## fact_verification_cases.json (103 case)

Sinh bằng `scripts/gen_fact_verification_cases.py` — mỗi case tự validate
bằng chính `_is_grounded()` thật ngay lúc sinh (bắt collision kiểu tên ngắn
vô tình là substring của từ khác, đã gặp thật với case "An"/"handle").

| Nhóm | Số lượng | Mục tiêu kiểm |
| --- | --- | --- |
| VER-001..022 | 22 | `time_expression` khớp text gốc (EN+VI) — giữ nguyên |
| VER-023..044 | 22 | `time_expression` không có trong text (LLM bịa) — bị xóa |
| VER-045..062 | 18 | `assignee_hint` khớp sau chuẩn hóa hoa/thường — giữ |
| VER-063..077 | 15 | `assignee_hint` không có trong text — bị xóa |
| VER-078..085 | 8 | Cả 2 field rỗng — không có gì để verify, hợp lệ |
| VER-086..095 | 10 | Jira — bỏ qua verify hoàn toàn (rule-based, đã grounded theo thiết kế) |
| VER-096..103 | 8 | Claim có dấu khớp text không dấu — chuẩn hóa 2 chiều vẫn khớp |

## Quy tắc

1. Case đã ổn định thì không sửa ngầm — sửa logic thật thay đổi thì cập nhật
   case + README cùng lúc.
2. Thêm case mới khi tìm ra edge case chưa cover, không xóa case cũ để "cho
   test pass".
3. Đây là bộ case do kỹ sư soạn khi implement, **không phải** bộ case QA
   chính thức của Dũng (PO/QC) — cùng tinh thần ghi chú ở
   `eval/golden_dataset/resolve_make_batches/README.md`.
