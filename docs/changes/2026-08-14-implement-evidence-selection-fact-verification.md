# Implement Evidence Selection + Fact Verification (theo diagram outlook-detail.drawio)

## Mục tiêu

Implement 2 stage mới vào pipeline task-extraction thật, theo đúng kiến trúc
đã thiết kế trong `docs/projects/engineering/outlook-detail.drawio`: Evidence
Selection và Fact Verification. Theo lựa chọn của user (Technical Lead):
**bắt đầu nhẹ, deterministic, không thêm dependency mới** — không dùng
embedding/NLI model, tái dùng regex đã có trong `filter_classify.py`.

Output Verification trong diagram **đã tồn tại sẵn** — `reduce_node` +
`ground_candidate()` (lexical overlap ≥20%, fallback nối quote nguyên văn nếu
không đủ căn cứ) đã làm đúng việc này từ trước, không cần thêm code mới cho
stage này.

## Agent/lane và ownership

1 agent, sửa trực tiếp trên `main` checkout.

## Base/head

Base: đầu phiên hiện tại (sau commit fix `cluster_messages` duplicate key,
chưa commit). Thay đổi đang ở working tree, chưa commit.

## Hành vi thay đổi

Pipeline task-extraction thêm 2 node mới vào graph (`src/agents/pipeline/graph.py`):

```
fetch -> normalize -> filter -> evidence -> make_batches -> extract_batch
      -> verify -> resolve -> cluster -> reduce -> persist
```

### Evidence Selection (`src/agents/pipeline/nodes/evidence.py`, node mới `evidence`)

- Email/tin nhắn >= 400 ký tự: tách câu, chấm điểm mỗi câu bằng `ACTION_RE`/
  `DEADLINE_RE`/`URGENCY_RE` (tái dùng từ `src/services/filter_classify.py`,
  không tạo bộ từ khóa mới), chọn tối đa 6 câu điểm cao nhất, giữ nguyên thứ
  tự xuất hiện gốc.
- Email ngắn hơn 400 ký tự: giữ nguyên toàn bộ, không cắt.
- Ghi vào field mới `evidence_text`, **không ghi đè** `text` gốc.
- `extract_batch_node._format_batch()` dùng `evidence_text` khi có (fallback
  `text` khi không) làm nội dung gửi cho LLM — giảm token gửi LLM, đúng tinh
  thần "không đưa cả email vào LLM" trong diagram.
  `deterministic_action_hint` vẫn đọc `text` gốc (không đổi, giữ độ chính xác
  hint hiện có).

### Fact Verification (`src/agents/pipeline/nodes/verify.py`, node mới `verify`,
chạy giữa `extract_batch` và `resolve`)

- Với item nguồn LLM (Gmail/Outlook, không phải Jira): kiểm `time_expression`
  và `assignee_hint` (2 field LLM tự sinh, chưa từng được verify) có thực sự
  xuất hiện trong `message.text` gốc hay không (so khớp substring sau chuẩn
  hóa dấu tiếng Việt + hoa/thường).
- Field không xuất hiện trong text gốc → **xóa field đó** (coi như "không có
  thông tin"), **không loại bỏ cả item** — quyết định có chủ đích: loại cả
  item vì 1 field lệch sẽ giảm recall, trong khi field đó không phải điều
  kiện quyết định email có phải việc-cần-làm (đã quyết ở `filter_node`).
- Jira: bỏ qua, đi qua nguyên vẹn — evidence Jira lấy trực tiếp từ description
  bằng regex match (`jira_rules.py`), grounded theo thiết kế.
- Trả thêm `verification_stats` (đếm số field bị xóa) vào state, phục vụ audit
  sau này nếu cần.

## File chính

- `src/agents/pipeline/nodes/evidence.py` — mới.
- `src/agents/pipeline/nodes/verify.py` — mới.
- `src/agents/pipeline/nodes/extract_batch.py` — `_format_batch()` dùng
  `evidence_text`.
- `src/agents/pipeline/graph.py` — wire 2 node mới vào graph.
- `src/agents/pipeline/state.py` — thêm `verification_stats: dict`.
- `tests/test_agents/v1/pipeline/nodes/test_evidence.py` — mới.
- `tests/test_agents/v1/pipeline/nodes/test_verify.py` — mới.
- `tests/test_agents/v1/pipeline/test_graph_e2e.py` — cập nhật thứ tự node kỳ
  vọng trong `test_task_graph_runs_every_stage_with_mock_nodes`.
- `eval/golden_dataset/evidence_verification/` — mới (README, 2 file case).
- `tests/test_agents/v1/test_evidence_verification_golden.py` — mới.
- `eval/outlook/` — mới (README, 1 file case).
- `tests/test_agents/v1/test_outlook_pipeline_golden.py` — mới.

## Test đã chạy

```
.venv/Scripts/python -m pytest tests/test_agents/ -q
# 248 passed, 1 skipped
```

```
.venv/Scripts/python -m pytest -q --ignore=tests/mail_filter
# 8 failed, 1104 passed, 6 skipped
```

Đã xác nhận 8 test fail đều **pre-existing, không liên quan thay đổi này** —
chạy lại đúng 8 test đó sau khi `git stash` (bỏ toàn bộ thay đổi của task
này) vẫn fail y hệt: `test_gmail_filter_gold_cases` (golden dataset drift có
sẵn), `test_claude_hooks_return_to_project_root_before_running`,
`test_update_proposed_task_before_confirmation` (lệch timezone format có
sẵn), `test_chunk_from_mic_appends_one_line` +
`test_silent_chunk_is_not_appended` (audio, không liên quan pipeline),
3 test `test_observability_langsmith.py` (`KeyError: 'targets'` — fixture
dashboard Grafana hỏng có sẵn, không liên quan pipeline).

## Golden dataset (bổ sung sau)

Thêm `eval/golden_dataset/evidence_verification/` (6 case Evidence Selection
+ 7 case Fact Verification, tự chứa input/expected, theo đúng convention
`resolve_make_batches/`) + test parametrize thật
`tests/test_agents/v1/test_evidence_verification_golden.py` chạy qua
`select_evidence()`/`verify_node()` thật — không phải fixture "mồ côi" như
18 fixture Gmail cũ chưa từng được code đọc. Đây là bộ case kỹ sư soạn khi
implement, chưa phải fixture chính thức QA (ghi rõ trong README của thư mục).

13/13 case pass.

## Golden dataset riêng cho Outlook (bổ sung sau)

Thêm `eval/outlook/` (7 case) — end-to-end thật cho
`OutlookConnector`: raw payload đúng hình dạng Microsoft Graph API ->
`OutlookConnector.normalize()` thật -> `filter_and_classify()` thật ->
`select_evidence()` thật. Khác `evidence_verification/` (test hàm thuần,
input dựng tay) — bộ này bắt lỗi cụ thể của connector Outlook: HTML
`<script>/<style>` còn sót trong text, `receivedDateTime` thiếu -> `sent_at
= "unknown"` (lệch đã biết), `hasAttachments=true` nhưng `attachments` vẫn
rỗng (giới hạn P0 đã biết), `is_self` so khớp khác hoa/thường, nội dung
tiếng Việt có dấu.

Test: `tests/test_agents/v1/test_outlook_pipeline_golden.py`. 7/7 case pass.

Phát hiện phụ trong lúc viết case: `_extract_body_text()` (outlook.py) để lại
khoảng trắng thừa khi thay thẻ HTML bằng `" "` (field `text` chưa collapse
whitespace, khác `normalized_text` đã collapse) — `evidence_node`/
`extract_batch_node` đọc field `text` thô nên khoảng trắng thừa này lọt cả
vào nội dung gửi LLM. Không ảnh hưởng chất lượng extract (LLM không quan tâm
khoảng trắng kép), ghi nhận làm follow-up, không sửa trong task này (ngoài
scope, không phải lỗi liên quan Evidence Selection/Fact Verification).

## Mở rộng golden dataset lên 100+ case/file

Theo yêu cầu sau đó — sinh bằng script (`scripts/gen_evidence_selection_cases.py`,
`scripts/gen_fact_verification_cases.py`, `scripts/gen_outlook_pipeline_cases.py`,
giữ lại trong repo để chạy lại/mở rộng sau), mỗi case tự validate bằng chính
hàm thật (`_is_grounded`, `OutlookConnector.normalize`, `filter_and_classify`)
ngay lúc sinh, không phải gõ tay:

- `evidence_selection_cases.json`: 6 -> **100 case**.
- `fact_verification_cases.json`: 7 -> **103 case**.
- `outlook_pipeline/cases.json`: 7 -> 100 -> **102 case** (dời từ
  `eval/golden_dataset/outlook_pipeline/` sang `eval/outlook/` theo yêu cầu
  user; sau đó viết lại nội dung mail cho giống thật hơn — chào hỏi, đoạn
  ngữ cảnh, chữ ký, sender/công ty đa dạng, thêm nhóm case mail RE: có lịch
  sử quoted-reply — thay vì câu 1 dòng trần trụi kiểu template ban đầu).

`tests/test_agents/`: **551 passed, 1 skipped**.

## Xác nhận end-to-end tới frontend

Chạy `scripts/verify_pipeline_end_to_end.py` — pipeline THẬT (`filter ->
evidence -> make_batches -> extract_batch(mock_llm) -> verify -> resolve ->
cluster -> reduce -> persist`) với 1 case golden Outlook thật, persist vào
DB, rồi serialize qua đúng hàm API frontend dùng (`_to_response` trong
`src/api/tasks.py`). Kết quả: `TaskResponse` có `title`/`detail`/`evidence`
đầy đủ, đúng shape.

Đối chiếu `client/web-app/src/pages/TasksPage.tsx:792`:
`task.detail || task.evidence[0]?.evidenceQuote || fallback` — payload pipeline
mới tạo khớp đúng field frontend đã tiêu thụ sẵn, **không cần sửa frontend**.
Xác nhận theo đúng lựa chọn user: verify pipeline mới không vỡ UI hiện có,
không thêm UI mới.

## Phần chưa chạy

- Chưa chạy pipeline thật với LLM thật (chỉ chạy unit test + mock + golden
  dataset).
- Chưa lint/typecheck riêng (ruff/mypy).

## Risk

Trung bình-thấp:

- `evidence_node`: chỉ ảnh hưởng nội dung gửi LLM (giảm token), không đổi
  cấu trúc dữ liệu downstream — field mới, không ghi đè field cũ.
- `verify_node`: chỉ xóa field khi không grounded, không loại task — rủi ro
  regression thấp hơn nhiều so với phương án loại bỏ cả item (đã cân nhắc và
  loại phương án đó).
- Rủi ro thật: nếu LLM diễn đạt `time_expression`/`assignee_hint` khác quá xa
  câu chữ gốc (paraphrase nặng thay vì trích gần nguyên văn như prompt yêu
  cầu), field đó sẽ bị xóa dù đúng — chấp nhận được vì prompt đã yêu cầu rõ
  "time_expression giữ nguyên câu chữ gốc", đây là guardrail chặn trường hợp
  LLM không tuân prompt.

## Migration/config

Không.

## Merge/deploy status

Chưa commit, chưa deploy.

## Rollback

Chưa commit — `git checkout` các file liệt kê ở trên nếu cần revert.

## Follow-up

- Golden dataset riêng cho Evidence Selection (gold evidence spans) và Fact
  Verification (supported/unsupported labels) theo đúng thiết kế trong
  diagram — chưa làm, cần case thật.
- Cân nhắc thêm field `evidence_selected` audit (câu nào bị bỏ) nếu cần debug
  sau này.
