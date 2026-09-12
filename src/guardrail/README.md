# Guardrail

Guardrail là lớp kiểm soát deterministic nằm quanh LLM. Mục tiêu là:

1. Dữ liệu không thuộc user hoặc không còn quyền truy cập không được đưa vào model.
2. Nội dung email/tin nhắn được xem là dữ liệu không tin cậy, không phải instruction.
3. Model chỉ được tạo claim dựa trên evidence đã được cấp.
4. Output thiếu bằng chứng, citation giả hoặc vi phạm permission phải bị loại/abstain.
5. Conflict được giữ nguyên để UI hiển thị không chắc chắn, không tự chọn một phía.

Guardrail không thay thế authorization ở API/database. Đây là lớp phòng vệ bổ sung; ownership và permission vẫn phải được kiểm tra ở query/retrieval layer.

## Luồng xử lý

```text
raw source
   ↓
input validation
   ├─ classify query scope
   ├─ check owner / permission / retention
   ├─ remove revoked or deleted evidence
   └─ minimize context
   ↓
safe context pack
   ├─ evidence is explicitly untrusted
   └─ source content is never merged into system policy
   ↓
LLM structured generation
   ↓
output grounding
   ├─ citation exists
   ├─ citation belongs to current context
   ├─ permission is re-checked
   ├─ conflict is preserved
   └─ unsupported output becomes abstain
```

## Các module

### `input.py`

Chứa các lớp và hàm cho input guardrail:

- `Evidence`: contract tối thiểu của một evidence.
- `QueryIntent`: các intent trong scope sản phẩm như deadline, task, conflict, summary và action.
- `classify_query(query)`: phân loại query deterministic.
- `build_context_pack(query, items)`: lọc evidence theo user, connection, permission, status và retention; đồng thời giới hạn số item/kích thước text.
- `sanitize_untrusted_text(text)`: thay thế các mẫu prompt injection phổ biến mà không xóa toàn bộ nội dung hữu ích.
- `scan_prompt_injection(text)`: phát hiện direct override, role-play, delimiter smuggling, zero-width Unicode và payload URL/base64/hex đã encode.
- `evidence_block(items)`: bọc source content thành block `<evidence>` để model hiểu đây là dữ liệu.

Ví dụ:

```python
from src.guardrail.input import Evidence, build_context_pack

decision, context = build_context_pack(
    "Deadline proposal khi nào?",
    [
        Evidence(
            evidence_id="gmail-123",
            text="Please submit the proposal before Friday.",
            user_id="user-1",
            current_user_id="user-1",
            source="gmail",
        )
    ],
)

if decision.decision == "allow":
    # Chỉ đưa `context` đã lọc vào prompt.
    ...
```

`decision.decision` có thể là:

- `allow`: có thể tiếp tục.
- `abstain`: query ngoài scope hoặc không còn evidence hợp lệ.

Query casual như `hi` vẫn là `allow` ở lớp security guardrail. Scope router có thể chọn trả lời thân thiện hoặc hướng người dùng về các câu hỏi dựa trên nguồn; đó không phải là security block.

Detector không mặc định cấm mọi text đáng ngờ. Nó trả về `none`, `medium` hoặc `high` cùng danh sách finding. Source content sẽ được sanitize; user query có thể được đưa sang flow clarify/review khi có tín hiệu `high`. Cách tách severity khỏi decision giúp không phá UX và vẫn không để model làm theo instruction trong dữ liệu.

Ngoài quyết định chính, `InputDecision` còn trả về `coverage`, `evidence_ids`, `excluded_sources` và `risk_flags` để UI/log hiển thị trạng thái rõ ràng.

### `policy.py`

Allowlist tool cho agent:

- Nhóm `read`: chỉ đọc evidence/context.
- Nhóm `draft`: chỉ tạo bản nháp action.
- Nhóm `write`: cố ý để trống.

```python
from src.guardrail.policy import is_tool_allowed

is_tool_allowed("search_evidence")  # True
is_tool_allowed("create_action_draft", phase="draft")  # True
is_tool_allowed("send_message")  # False
is_tool_allowed("create_calendar_event")  # False
```

Các action bên ngoài phải đi theo lifecycle:

```text
drafted → previewed → confirmed → handoff_opened → completed
```

Guardrail không tự gửi email, tạo event hoặc cập nhật hệ thống bên ngoài.

### `output.py`

Chứa output grounding:

- `ground_candidate(...)`: kiểm tra candidate có evidence hợp lệ hay không.
- kiểm tra evidence ID tồn tại.
- kiểm tra permission lần cuối trước render.
- chuyển output thành `uncertain` nếu có conflict.
- chuyển output thành `abstain` nếu không có hoặc không đủ evidence.

Các trạng thái kết quả:

- `grounded`: có thể render.
- `uncertain`: có conflict, cần hiển thị các phía hoặc hỏi mentor.
- `abstain`: chưa đủ evidence.
- `reject`: citation không tồn tại hoặc permission đã bị revoke.

Ví dụ:

```python
from src.guardrail.output import ground_candidate

result = ground_candidate(
    "Deadline là thứ Sáu.",
    {"e1": "Deadline là thứ Sáu."},
    ["e1"],
    permission_check={"e1": True},
)

if result.status == "grounded":
    render(result.claims)
else:
    show_uncertainty_or_abstention(result.reason)
```

## Đã tích hợp vào Gmail pipeline

Guardrail hiện được nối ở ba điểm:

### Extraction

`src/agents/pipeline/nodes/extract_batch.py`:

- Nội dung email được bọc như untrusted evidence.
- Prompt injection trong source bị neutralize.
- Model trả về message ID không thuộc batch sẽ bị bỏ qua.
- `evidence_quote` phải là đoạn trích nguyên văn trong message gốc **hoặc**
  trong nội dung attachment đã trích (`attachment_text`) — cùng 1 evidence_id
  theo message, không có citation riêng cho attachment.

### Reduce

`src/agents/pipeline/nodes/reduce.py`:

- Chỉ gửi evidence quote vào bước tóm tắt.
- Source quote vẫn được coi là untrusted data.
- Candidate có grounding yếu sẽ fallback về phần quote gốc thay vì render nội dung model tự nghĩ thêm.

### Attachment extraction

`src/agents/pipeline/nodes/attachment_extract.py` (Gmail pdf/docx/xlsx/ảnh),
đứng sau `evidence_node`, trước `make_batches_node`. Đây là threat class
khác hai mục trên: không chỉ phòng LLM-input text, mà còn phòng **chính file
đính kèm bị dùng để khai thác parser** trước khi có text để đưa vào guardrail
input. Module riêng: `src/guardrail/attachment_safety.py`.

- Allow-list mimeType (pdf/docx/xlsx/png/jpeg) + trần kích thước file gốc —
  chặn trước khi gọi Gmail API tải bytes.
- Zip-bomb: docx/xlsx là file zip — đọc kích thước sau giải nén từ
  `ZipInfo` trước khi cho `python-docx`/`openpyxl` giải nén thật.
- XXE: `python-docx` tự dựng parser lxml với `resolve_entities=False` sẵn;
  `openpyxl` tự chuyển sang `defusedxml` khi thấy package có cài — cả hai đã
  verify bằng cách đọc source, không phải patch tay của guardrail này.
- Ảnh: `Image.MAX_IMAGE_PIXELS` tightening (chặn decompression bomb, Pillow
  đã có cơ chế này sẵn ở mức mặc định lỏng hơn) + `Image.verify()` trước khi
  forward bytes cho vision LLM.
- Mọi bước extract có timeout riêng (`run_with_timeout`) — file méo/cố ý ác ý
  không được làm treo cả node.
- Text trích được đi qua **cùng** `sanitize_untrusted_text` như thân mail —
  nội dung file cũng là untrusted content, không có ngoại lệ.
- Cost-gate: chỉ mail `importance` thuộc `critical`/`important` mới được xử
  lý attachment; tối đa N attachment/mail (`attachment_max_per_message`).
- Công tắc tổng `attachment_extraction_enabled` mặc định **tắt** — mở rộng
  phạm vi dữ liệu đọc từ Gmail (nội dung file, không chỉ metadata), phải bật
  có chủ đích sau khi review.
- Chỉ lưu text đã trích (`pipeline_attachment_extracts`, ephemeral theo run,
  cascade-delete theo `runs.id`) — không lưu bytes gốc của file.
- KHÔNG OCR fallback cho PDF chỉ là ảnh scan (không có text layer thật) —
  ngoài scope hiện tại.

## Nguyên tắc sử dụng

### Không dùng prompt để thay thế permission

Không làm:

```python
prompt = f"Bạn chỉ được dùng dữ liệu của user hiện tại: {raw_data}"
```

Phải lọc trước bằng code/database, sau đó mới tạo context pack.

### Không nối source content vào system prompt

System policy và source evidence phải là hai message/khối riêng biệt. Source content luôn có thể chứa câu giả instruction.

### Không đoán field quan trọng

Nếu không có evidence cho deadline, assignee, status, timezone hoặc thời gian họp thì để `null`/`unknown`; không tự suy diễn.

### Partial coverage không đồng nghĩa complete

Khi một nguồn lỗi hoặc chỉ tải được một phần, câu trả lời phải dùng cách diễn đạt như:

> Trong các nguồn hiện truy cập được, mình tìm thấy...

Không được kết luận tuyệt đối rằng không còn item nào khác.

## Test

Test guardrail nằm ở:

```text
tests/v1/test_guardrail.py
tests/v1/test_attachment_safety.py
```

Chạy:

```powershell
pytest -q tests/v1/test_guardrail.py tests/v1/test_attachment_safety.py
```

Các case quan trọng gồm:

- cross-user evidence;
- revoked permission;
- partial coverage;
- prompt injection;
- citation không tồn tại;
- conflict;
- permission bị revoke ngay trước lúc render;
- tool write bị chặn.

Nếu full test suite lỗi từ dependency hoặc infrastructure, vẫn có thể kiểm tra cú pháp và import:

```powershell
python -m compileall -q src\guardrail
python -c "from src.guardrail import classify_query, ground_candidate; print('guardrail import ok')"
```

## Giới hạn hiện tại

- `classify_query` là classifier heuristic, chưa dùng model phân loại.
- `ground_candidate` dùng lexical overlap cho prose; với production nên bổ sung claim schema và validator theo field trước khi cần semantic/NLI verifier.
- Việc kiểm tra permission ở database/retrieval phải tiếp tục được duy trì; module này không tự cấp quyền.
- Tool runtime thực tế cần gọi `is_tool_allowed` trước khi execute tool, không chỉ dùng allowlist để tham khảo.

## HITL và tool call nguy hiểm

HITL nằm trong `hitl.py`. Trước khi executor chạy bất kỳ side effect nào, gọi:

```python
from src.guardrail.hitl import HITLAuditLog, route_tool_call

audit = HITLAuditLog()
decision = route_tool_call(
    "create_calendar_event",
    confidence=0.99,
    request_id="req-123",
    audit=audit,
)

# Chỉ executor có reviewer approval mới được chạy.
if decision.route.value == "escalate":
    enqueue_for_human(decision)
```

### Confidence routing

| Điều kiện | Route | Reviewer |
|---|---|---|
| confidence `>= 0.90`, action thường | `auto_send` | Không cần HITL |
| `0.70 <= confidence < 0.90` | `queue_review` | Cần reviewer |
| confidence `< 0.70` | `escalate` | Cần reviewer/operator |
| action thuộc `HIGH_RISK_ACTIONS` | `escalate` | Luôn cần reviewer, kể cả `0.99` |

`HIGH_RISK_ACTIONS` hiện gồm gửi message/email, tạo/sửa/xóa calendar event, xóa dữ liệu, đổi permission, publish external, execute code, payment/refund, invite user và revoke access.

`hitl_decision_points` định nghĩa ba điểm kiểm soát:

1. `dangerous_tool_call`: review tên tool, arguments đã redact, evidence, permission và diff.
2. `medium_confidence_action`: review intent, payload, citations, confidence và diff.
3. `grounding_or_permission_failure`: review conflict hoặc permission race trước render/execute.

Approve chỉ cho phép đúng request/idempotency scope đã review. Reject không execute và ghi audit. Timeout mặc định deny/escalate; không bao giờ tự approve sau timeout.

### Audit

`HITLAuditLog.record()` lưu `request_id`, `event_type`, `layer`, `reviewer_decision`, action và metadata/diff đã redact. Không được ghi raw prompt, raw email, raw source text hoặc content. Mỗi event có `previous_hash` và `event_hash`; dùng `verify_integrity()` để phát hiện sửa/xóa event trong chuỗi.

### Monitoring

`MetricsCollector` ghi counter cho request blocked, rate-limit hit và judge pass/fail. `MonitoringAlert.check_metrics()` tạo alert khi:

- block rate vượt `block_rate_threshold` (mặc định `20%`);
- rate-limit hits vượt `rate_limit_hits_threshold` (mặc định `20`);
- judge fail rate vượt `judge_fail_rate_threshold` (mặc định `10%`).

Các ngưỡng có thể truyền vào constructor, không hard-code trong dashboard.

## Hướng mở rộng

1. Thêm `evidence_version`, `observed_at`, `valid_from`, `valid_to` vào contract.
2. Thêm freshness check trước render.
3. Chuẩn hóa structured answer gồm `claims`, `conflicts`, `coverage`, `recommended_actions`.
4. Thêm audit event cho các trạng thái `reject`, `abstain` và `uncertain` nhưng không log raw email.
5. Tách action preview/confirm thành endpoint riêng với idempotency key.

## Tool classification theo impact level

Tool không phân theo Gmail/Discord/Jira mà phân theo mức ảnh hưởng:

| Level | Loại | Quyết định |
|---|---|---|
| 0 | Safe read | `allow`, permission/scope vẫn phải pass |
| 1 | Internal computation | `allow`, không side effect |
| 2 | Draft | `draft_only`, chỉ preview; user có Approve/Edit/Reject |
| 3 | External write | luôn `require_approval`, kể cả confidence `1.0` |
| 4 | Destructive | `require_double_confirmation`, timeout là deny/escalate |

Dùng `classify_tool()` và `evaluate_tool()` trong [policy.py](./policy.py). Tool không nằm trong allowlist được fail-closed thành Level 3. Các domain `bank`, `payment`, `HR`, `grading`, `medical` luôn là high-risk và không autonomous.

## Confidence và decision matrix

Confidence được chia thành `high (>=.95)`, `medium (.85-.95)`, `low (.70-.85)`, `very_low (.50-.70)` và `unknown (<.50)`. Quyết định cuối còn xét permission, scope, evidence, citation, conflict và coverage:

| Điều kiện | Kết quả |
|---|---|
| permission/scope fail | `block` |
| citation fail | không cho execute |
| thiếu evidence | `abstain` |
| conflict | `uncertain`, không tự chọn nguồn |
| coverage partial | hiển thị warning |
| confidence thấp | review/escalate |

Confidence `0.99` vẫn không được tự gửi email, tạo calendar event hoặc thực hiện destructive action.

## Gmail filter/classify service

Service [filter_classify.py](../services/filter_classify.py) chạy trước LLM trong pipeline:

```text
Gmail fetch → filter_classify → importance score → thread/dedupe → LLM extraction → grounding
```

Service này:

- giới hạn lookback mặc định 14 ngày;
- lọc label đã được phê duyệt;
- chấm sender, To/Cc, action, deadline, urgency, unread, program relevance, newsletter/automation noise và thread change;
- phân loại `critical`, `important`, `relevant`, `ignore`;
- phân loại Daily Brief thành `needs_action`, `changes`, `reference`, `ignore`;
- giữ email nếu có tín hiệu “must not miss”, kể cả score chưa cao;
- deduplicate message trùng và gắn `thread_size` trước khi batching cho LLM.

Các field `importance_score`, `importance`, `brief_section`, `must_not_miss`, `classification_reasons` và `component_scores` được gắn vào normalized item để downstream dùng. Service không tự điền deadline/owner và không thay thế grounding.
