# Golden dataset cho bước tóm tắt

Repo đã có 8 bộ golden, nhưng tất cả đều chấm phần **lọc/trích** — phần
rule-based. Không bộ nào chấm `reduce_node`, tức là chỗ LLM viết ra đúng câu chữ
người dùng đọc trên thẻ công việc. Bộ này lấp chỗ đó.

## Chạy

```bash
python -m scripts.eval_summary_arms --repeat 4        # cả bốn nhánh, cần LLM thật
python -m scripts.eval_summary_arms --arms rule       # không tốn tiền
python -m scripts.eval_summary_arms --rescore eval/golden_dataset/summary/last_run.json
pytest tests/test_services/test_summary_scoring.py    # phần tất định, chạy trong CI
```

`--rescore` chấm lại output đã lưu: sửa tiêu chí chấm không phải trả tiền gọi
model lại. Mỗi lượt gọi LLM **một lần** cho mỗi case rồi hậu xử lý ra từng
nhánh, nên chênh lệch giữa các nhánh là chênh lệch của cổng grounding, không
phải nhiễu lấy mẫu của model.

## Bốn nhánh

| nhánh | là gì |
|---|---|
| `rule` | `_mock_reduce` — nối `evidence_quote` kèm dòng nguồn. Không gọi LLM. |
| `llm` | Prompt production, **bỏ** cổng `ground_candidate`. |
| `hybrid` | `reduce` đang chạy thật: LLM, trượt grounding thì rơi về rule. |

## Kết quả (4 lượt, 12 case)

Trước khi vá cổng grounding:

| nhánh | PASS trung bình | biên độ |
|---|---|---|
| rule | 0.67 | 0.67–0.67 |
| llm | 0.98 | 0.92–1.00 |
| hybrid | 0.83 | 0.75–0.92 |

Sau khi vá:

| nhánh | PASS trung bình | biên độ | attribution | coverage | faithful | language | paraphrase |
|---|---|---|---|---|---|---|---|
| rule | 0.67 | 0.67–0.67 | 1.00 | 0.83 | 1.00 | 0.83 | 0.17 |
| llm | 1.00 | 1.00–1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 |
| **hybrid** | **1.00** | **1.00–1.00** | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 |

`hybrid` giờ ngang `llm` về điểm nhưng vẫn giữ lưới an toàn: bản nào không
grounded thì rơi về rule thay vì đi thẳng ra UI. Đó là lý do chọn `hybrid`.

Nhánh `rule` kém không phải vì sai sự thật — faithful 1.00 — mà vì nó chỉ nối
câu trích: paraphrase 0.17, và không đổi được ngôn ngữ theo giao diện.

## Hai lỗi cổng grounding mà bộ này bắt được (đã vá)

Cả hai nằm ở `src/guardrail/output.py`, đường `_script_bucket`:

1. **Nhãn tự sinh làm lệch nhận dạng hệ chữ.** `source_header()` thêm `[Từ:]`,
   `[Đến:]` — chữ tiếng Việt. `_script_bucket(source_text)` do đó đọc mọi nguồn
   là tiếng Việt, kể cả mail thuần tiếng Anh. Mọi bản tóm tắt tiếng Anh vì thế
   rơi vào nhánh so anchor thay vì so từ vựng.
2. **Ngày viết lại bị chấm là bịa.** Nguồn ghi `21/08`, bản tóm tắt viết
   `August 21` — anchor `21` không có trong nguồn, cổng kết luận bịa đặt và
   loại. Kết quả: người dùng để giao diện tiếng Anh nhận lại nguyên câu tiếng
   Việt của nhánh rule.

Hai lỗi này khiến `hybrid` trượt đúng hai case ngôn ngữ mà `llm` làm được, và
đánh sập chính yêu cầu "tóm tắt theo ngôn ngữ giao diện".

Bản vá đã vào `src/guardrail/output.py`. Nới **chỉ ở phía nguồn**: thành phần
ngày của nguồn được tính là neo hợp lệ, còn neo trong bản tóm tắt vẫn phải tìm
thấy trong nguồn — model bịa ra số mới vẫn bị chặn. Hai test hồi quy ở
`tests/v1/test_guardrail.py`.
