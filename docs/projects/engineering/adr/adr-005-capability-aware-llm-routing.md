# ADR-005 — Routing LLM theo loại câu hỏi, capability và provider failover

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Backend Lead, AI/Memory Lead, QA Lead, PO/QC |
| Last updated | 2026-08-10 |
| Related | [LLM routing](../llm-routing.md) · [Architecture](../architecture.md) · [PRD](../../product/prd.md) · [AI usage log](../ai-usage-log.md) |

## Bối cảnh

Hệ thống hiện dựng một chuỗi provider/model chung cho hai việc khác nhau:

- trò chuyện hoặc sinh câu trả lời không cần tool;
- phân tích câu hỏi thực tế và gọi Gmail, Calendar, retrieval, task, calculator
  hoặc web search.

Model mặc định miễn phí có thể trả lời small talk nhưng chưa được chứng minh hỗ
trợ function calling ổn định. Trong incident hội thoại 8 ngày 2026-08-10, model
sinh malformed `web_search` call; provider trả HTTP 400 `tool_use_failed`. Cơ
chế failover chỉ nhận transient/auth/quota/5xx nên request dừng ở 502 dù còn
provider khác.

Một model/provider duy nhất cho mọi intent tạo ba vấn đề:

1. small talk phải chịu latency và tool overhead không cần thiết;
2. work request có thể rơi vào model rẻ nhưng thiếu capability;
3. failover theo provider mà không xét capability có thể đổi lỗi này thành lỗi
   khác hoặc làm mất tool binding.

## Lựa chọn đã cân nhắc

| Phương án | Kết luận |
| --- | --- |
| Một model mạnh cho mọi request | Không chọn cho P0: đơn giản nhưng tốn chi phí/latency và phụ thuộc một candidate |
| Một model free cho mọi request | Loại: giá rẻ không chứng minh function calling hoặc grounded accuracy |
| Dùng LLM riêng để classify mọi query | Không chọn làm mặc định: thêm latency, cost và một failure point chỉ để chọn lane |
| Chỉ failover theo provider | Loại: provider khác không đồng nghĩa model có cùng capability |
| Deterministic lane router + capability registry + provider failover | Chọn: dễ test, free-first có điều kiện và giữ được tool/security contract |

## Quyết định

1. Hệ thống có hai lane canonical: `small_talk` và `work`.
2. Query router deterministic chỉ đưa câu rõ ràng là xã giao vào `small_talk`;
   câu thực tế hoặc mơ hồ mặc định vào `work`.
3. `small_talk` dùng model nhỏ/free, không bind tool và prompt trả lời ngắn,
   tự nhiên, hóm hỉnh vừa đủ.
4. `work` chỉ xét candidate đã khai báo và smoke-test `supports_tools=true` khi
   intent có thể cần function calling.
5. Candidate được lọc theo capability trước, sau đó mới ưu tiên free trước paid.
6. Failover giữ nguyên lane, tool schemas, authenticated scope và trace ID.
7. HTTP 400 chỉ failover khi được nhận diện là lỗi capability của provider/model,
   trước mắt gồm `code=tool_use_failed`; các 400 schema/request khác không retry
   mù.
8. Paid fallback mặc định tắt và chỉ bật khi có budget owner/alert.
9. Routing/fallback được quan sát bằng metadata, không log secret hoặc raw source.

Chi tiết implementation contract, decision table và runbook nằm tại
[LLM routing](../llm-routing.md).

## Lý do

**Capability trước cost.** Free-first chỉ an toàn nếu danh sách đã loại model
không làm được công việc. Đây là khác biệt giữa tối ưu chi phí và đánh cược độ
chính xác.

**Deterministic default dễ kiểm chứng.** Small-talk allowlist có thể parametrize
bằng fixture; mọi câu không chắc quay về work lane an toàn hơn. Không phát sinh
một lượt LLM classifier và không cho model can thiệp security scope.

**Failover có ngữ nghĩa.** Lỗi `tool_use_failed` không chứng minh prompt người
dùng sai; nó chứng minh candidate hiện tại không hoàn thành tool contract. Đổi
sang candidate cùng capability hợp lý hơn trả 502 ngay.

**Không phá guard hiện có.** Gmail/Calendar time bounds, web-search feature flag
và retrieval scope vẫn do backend áp đặt. Routing chỉ chọn execution lane và
candidate, không nới quyền.

## Hệ quả

### Chấp nhận

- Thêm registry/config và test matrix cho nhiều candidate.
- Phải duy trì capability smoke test vì model free có thể đổi hoặc biến mất.
- Cùng một user query có thể dùng hai model: analyze/tool và response.
- Observability cần phân biệt lane, candidate và fallback thay vì chỉ provider.

### Phải làm

- Tách `get_llm()` thành API chọn candidate theo lane/capability.
- Tách graph path để small talk không chạy auto `discord_search_program`.
- Bổ sung failover classifier cho `tool_use_failed` và giữ tool binding.
- Thêm feature flag, env templates, regression tests và trace metadata.
- Ghi model/provider/version khi thay candidate production.

### Không đổi

- User scope lấy từ authenticated session, không từ model.
- Tool đọc vẫn bị giới hạn nguồn, quyền và cửa sổ thời gian.
- External write vẫn cần preview/confirm theo guardrail hiện hành.
- Empty evidence vẫn dẫn tới abstain/empty state, không dùng model memory bù vào.

## Rollback

Tắt feature flag capability routing và đưa mọi query về work path hiện tại.
Rollback không được route mọi query sang small-talk model. Candidate registry
và metadata mới có thể giữ lại vì không đổi data contract hoặc schema nghiệp vụ.

## Điều kiện chuyển sang `Accepted`

- [ ] Technical Lead và AI/Memory Lead duyệt decision table/capability contract.
- [ ] QA có regression test cho incident `tool_use_failed` hội thoại 8.
- [ ] Small-talk false-positive test gồm câu vừa chào vừa hỏi việc.
- [ ] Work candidate live smoke-test function calling trên staging.
- [ ] Free-first, paid fallback và rollback được cấu hình, không hardcode secret.
- [ ] LangSmith/telemetry hiển thị lane/model/provider/fallback reason.
