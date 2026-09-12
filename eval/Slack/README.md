# Golden Dataset cho Slack rule engine (src/services/slack_rules.py)

Bộ case cho `hard_filter()`/`score_message()`/`decide_from_score()`/
`extract_title()`/`extract_evidence()`/`extract_deadline_phrase()`, gọi qua
`evaluate_message()` — rule engine **100% rule-based, KHÔNG gọi LLM** cho
Slack, theo `docs/projects/engineering/slack-detail.drawio` (Normalization ->
Hard Filter -> Slack Rules + Common Rules -> Scoring -> Extraction ->
Decision). Dùng chung cho:

- Gate CI: `tests/test_services/v1/test_slack_rules_golden.py` đọc trực tiếp
  `cases.json`, assert từng case qua `evaluate_message()`/
  `extract_deadline_phrase()` thật, gate ở **100%** (khác
  `ml/model for extension/data/` gate 90% vì `is_task_like()` có sai
  số — slack_rules.py tất định nên sai lệch bất kỳ case nào cũng là
  regression thật).
- `eval_slack_rules.py`: chạy độc lập, in bảng accuracy theo từng nhóm tín
  hiệu, dùng khi muốn xem nhanh case nào sai mà không cần chạy pytest.

Không phải fixture "mồ côi" — mỗi case trong `cases.json` đều được
`test_slack_rules_golden.py` đọc và assert thật.

## Cấu trúc

```text
eval/Slack/
├── README.md
├── gen_cases.py          # sinh cases.json — KHÔNG sửa tay JSON, sửa ở đây
├── cases.json            # 201 case, tự chứa input/expected
└── eval_slack_rules.py   # chạy độc lập, in bảng accuracy theo nhóm
```

## Vì sao expected được sinh bằng cách CHẠY code thật, không đoán tay

`gen_cases.py` dựng `NormalizedMessage` (+ `RuleConfig` nếu case cần override
threshold/weight), gọi `evaluate_message()`/`extract_deadline_phrase()` **thật**
ngay lúc sinh, rồi mới ghi `expected` xuống JSON — cùng tinh thần
`scripts/gen_outlook_pipeline_cases.py` (xem `eval/outlook/README.md`).

Cách này đúng cho `slack_rules.py` vì nó là rule engine tất định (không LLM,
không phụ thuộc dữ liệu ngoài) — golden dataset ở đây có vai trò **khoá lại
hành vi hiện tại** (regression test), không phải oracle độc lập để "chấm điểm"
độ chính xác của rule như `task_extraction_cases.json` (nhãn do kỹ sư gán tay
vì `is_task_like()` có sai số thật so với hiểu ngữ nghĩa). Nhờ chạy code thật
lúc sinh, dataset còn bắt được vài hành vi thật không lường trước khi viết tay
(vd `PROGRAM_RE` cũng chứa từ khoá `deadline` trùng với `DEADLINE_RE`, hay
`URGENCY_RE` khớp thuần chuỗi con "gấp" trong "không gấp đâu" dù câu đang phủ
định — xem case `SLK-124`).

## Danh sách nhóm case (201 case, SLK-001..SLK-201)

| Nhóm | Số lượng | Mục tiêu kiểm |
| --- | --- | --- |
| `hard_filter_system_subtype` | 14 | 7 subtype hệ thống (channel_join/leave/topic/purpose/name/archive/unarchive) — DROP trước khi chấm điểm dù text có tín hiệu mạnh |
| `hard_filter_message_changed` | 6 | subtype=`message_changed` luôn DROP (đơn giản hoá có chủ đích, không giữ bản sửa mới nhất) |
| `hard_filter_empty_text` | 10 | Text chỉ còn mention/emoji/khoảng trắng sau khi strip -> `EMPTY_TEXT` |
| `score_mentioned_current_user` | 10 | Cô lập `MENTIONED_CURRENT_USER` (+30), có/không mention cùng nội dung |
| `score_direct_message` | 10 | `DIRECT_MESSAGE` (+15) chỉ cộng cho im/mpim, bị treo khi text là newsletter/automated |
| `score_thread_reply_to_self` | 6 | Cô lập `THREAD_REPLY_TO_SELF` (+15) |
| `score_pinned` | 6 | Cô lập `PINNED` (+10) |
| `score_action` | 10 | 10 từ khoá `ACTION_RE` khác nhau (please/reply/submit/.../vui lòng/xác nhận...) |
| `score_deadline_inferred` | 10 | 10 biểu thức `DEADLINE_RE` khác nhau (deadline/by/before/hạn chót/thứ Sáu/dd-mm...) |
| `score_urgency` | 8 | `URGENCY_RE`, bao gồm nhánh CJK (至急) không dùng `\b` |
| `score_program_relevance` | 6 | `PROGRAM_RE`, gồm case loại trừ đặc biệt "nhóm" (không cộng điểm) |
| `score_newsletter_or_automated` | 4 | Penalty -40 áp 1 lần dù khớp cả `NEWSLETTER_RE` lẫn `AUTOMATED_RE`, có thể lấn át tín hiệu dương |
| `decision_keep_realistic` | 24 | Tin nhắn công sở thực tế nhiều tín hiệu cộng dồn -> KEEP (bao gồm case giới hạn phủ định "không gấp đâu") |
| `decision_review_realistic` | 17 | 1-2 tín hiệu, điểm nằm giữa review_threshold(15) và keep_threshold(35) -> REVIEW |
| `decision_drop_realistic` | 20 | Chat đời thường/quảng cáo, không tín hiệu hoặc bị treo bởi newsletter -> DROP |
| `decision_threshold_boundary` | 8 | Điểm đúng bằng 35/30/15/10 (bội số 5 — mọi weight trong `RuleConfig` đều là bội 5) |
| `extract_title_prefers_signal_sentence` | 8 | `extract_title()` ưu tiên câu khớp ACTION/DEADLINE, bỏ câu chào/kết |
| `extract_title_fallback_first_sentence` | 6 | Không câu nào khớp -> lấy câu đầu, gồm case "Câu thứ hai" (ordinal, bị `_is_signal_sentence` loại trừ dù `DEADLINE_RE` khớp toàn văn bản) |
| `extract_title_truncation` | 4 | Câu dài hơn 80 ký tự bị cắt + dấu "…" |
| `extract_evidence_fallback_full_text` | 4 | `extract_evidence()` fallback lấy **nguyên text** khi không câu nào khớp — khác `extract_title()` chỉ lấy câu đầu (bất đối xứng có chủ đích, xem case SLK-188..191) |
| `extract_deadline_phrase` | 4 | Câu khớp riêng `DEADLINE_RE` (khác câu chỉ khớp `ACTION_RE`) — action-only trả `""` |
| `config_override` | 6 | `RuleConfig` configurable — override từng weight/threshold đổi hẳn quyết định |

## Quy tắc

1. **Không sửa tay `cases.json`.** Sửa `gen_cases.py` rồi chạy lại
   `.venv/Scripts/python.exe eval/Slack/gen_cases.py` để sinh lại — mọi
   `expected` đến từ code thật, sửa tay JSON dễ tạo case tự mâu thuẫn với rule
   engine hiện tại.
2. Đổi `RULE_CONFIG`/regex trong `slack_rules.py`/`filter_classify.py` thì
   chạy lại gen script để xác nhận diff `cases.json` đúng như kỳ vọng (đổi có
   chủ đích), rồi chạy `eval_slack_rules.py`/pytest để xác nhận gate xanh.
3. Thêm case mới khi tìm ra edge case chưa cover — thêm vào nhóm phù hợp
   trong `gen_cases.py`, không tự chỉnh JSON.
4. Đây là bộ case kỹ sư soạn khi implement, chưa phải fixture chính thức QA —
   cùng tinh thần `eval/golden_dataset/resolve_make_batches/README.md`.

## Chạy

```bash
# Sinh lại cases.json từ gen_cases.py
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe eval/Slack/gen_cases.py

# Xem bảng accuracy theo nhóm (độc lập, không cần pytest)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe eval/Slack/eval_slack_rules.py

# Gate CI thật
.venv/Scripts/python.exe -m pytest tests/test_services/v1/test_slack_rules_golden.py -q
```
