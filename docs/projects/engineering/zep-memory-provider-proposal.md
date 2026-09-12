# Đề xuất dùng Zep làm Memory Provider cho P-004

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Proposed — chưa thay đổi production architecture |
| Owner | Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | Technical Lead, AI/Memory Lead, QA Lead, PO/QC |
| Last updated | 2026-08-17 |
| Related | [Memory lifecycle](memory-lifecycle.md) · [ADR-006](adr/adr-006-pgvector-cho-lop-memory-dai-han.md) · [Evaluation plan](../qa/evaluation-plan.md) |

## 1. Mục đích

Đánh giá và triển khai có kiểm soát Zep cho các phần memory mà P-004 chưa có
đủ, chủ yếu là episodic memory, progressive summarization và semantic
relationship retrieval.

Tài liệu này là hướng triển khai đề xuất. Nó không cấp cho Zep quyền quyết định
canonical fact, source authority, consent, permission hoặc deletion.

## 2. Quyết định kiến trúc đề xuất

PostgreSQL tiếp tục là nguồn sự thật cho:

- profile và canonical memory;
- evidence, version, status và temporal validity;
- consent, scope và permission;
- audit, feedback, rejection và deletion;
- memory cần chứng minh nguồn gốc.

Zep là lớp derived provider cho:

- episodic memory: task, trajectory, outcome, reflection;
- user/session context đã được tổng hợp;
- semantic graph và quan hệ giữa entity;
- candidate retrieval để đưa vào context pack.

Luồng tổng thể:

```text
User input
  → PostgreSQL transaction
  → outbox / background sync
  → Zep derived memory
  → MemoryProvider adapter
  → ContextBudgetManager
  → Agent
```

Không gọi Zep trực tiếp trong transaction critical của request chat. Zep lỗi
không được làm mất user input, assistant response hoặc canonical memory.

## 3. Phạm vi dữ liệu được phép gửi sang Zep

### Được phép trong pilot

- Synthetic hoặc redacted task trajectory.
- Episode đã có source reference ở PostgreSQL.
- Candidate fact không chứa PII không cần thiết.
- Semantic document đã được kiểm tra scope và retention.
- Metadata tối thiểu: `user_id` nội bộ, `conversation_id`, `source_id`,
  `memory_type`, `observed_at`, `extractor_version`.

### Không gửi mặc định

- Raw email, raw Discord message hoặc transcript đầy đủ nếu không cần.
- Secret, access token, OAuth credential.
- PII ngoài mục đích sản phẩm.
- Canonical status mà không kèm authority/evidence mapping.
- Nội dung đã bị user revoke hoặc đã đến hạn retention.

Mọi payload phải đi qua privacy minimization và consent check trước khi enqueue.

## 4. Hợp đồng MemoryProvider

Backend cần bao quanh Zep bằng adapter nội bộ, không để node LangGraph gọi SDK
trực tiếp:

```python
class MemoryProvider(Protocol):
    async def retain(self, event: MemoryEvent) -> None: ...
    async def recall(self, query: MemoryQuery) -> list[MemoryItem]: ...
    async def forget(self, scope: MemoryScope) -> None: ...
    async def health(self) -> ProviderHealth: ...
```

Provider phải trả được provenance tối thiểu:

```json
{
  "provider": "zep",
  "memory_type": "episodic",
  "record_id": "provider-record-id",
  "source_ids": ["conversation:123:message:456"],
  "scope": "user:42",
  "status": "candidate",
  "score": 0.82
}
```

Adapter phải kiểm tra lại `user_id`, consent, status và source scope ở
PostgreSQL trước khi memory được đưa vào prompt. Kết quả Zep không tự động trở
thành `confirmed`.

Zep cũng không được tự xử lý conflict hoặc clarification. Conflict giữa user
input và memory hiện tại phải được adjudicate ở PostgreSQL; thiếu required field
phải dừng ở `clarification_request` trước khi gọi tool. Chỉ event đã resolve mới
được đưa vào outbox để đồng bộ sang Zep.

## 5. Chế độ vận hành

### Shadow

Gọi Zep để đo nhưng không đưa kết quả vào câu trả lời. So sánh với
PostgreSQL retrieval trên cùng query và cùng fixture.

### Fallback

Zep được dùng cho episodic/semantic context. Nếu timeout, quota hoặc provider
error thì quay về PostgreSQL retrieval; lỗi không được làm hỏng request.

### Active

Chỉ bật sau khi shadow và fallback đạt acceptance criteria. Zep có thể cung cấp
derived context, nhưng mọi kết quả vẫn đi qua context budget, scope filter và
grounding validator.

## 6. Đồng bộ và idempotency

Sử dụng outbox hoặc job queue cho các event:

- `memory_candidate_created`;
- `memory_confirmed`;
- `episode_completed`;
- `memory_superseded`;
- `memory_forgotten`;
- `memory_deleted`;
- `source_revoked`.
- `clarification_resolved`.
- `clarification_expired`.

Mỗi event cần có:

- `event_id` bất biến;
- `source_id` và `source_version`;
- `provider`;
- `attempt_count`;
- `next_attempt_at`;
- `synced_at` hoặc `dead_lettered_at`.

Retry phải idempotent. Không retry vô hạn và không ghi đè record mới hơn bằng
event cũ.

## 7. Forget, revoke và delete

Delete contract phải bao phủ cả hai kho:

```text
PostgreSQL delete/forget
  → enqueue provider deletion
  → Zep user/thread/episode/graph deletion
  → verification read
  → audit completion
```

Sau khi user revoke hoặc delete, retrieval mới phải loại dữ liệu ngay cả khi
Zep deletion đang chờ. Cách thực hiện là PostgreSQL scope/deny list chặn trước;
không chờ Zep phản hồi mới ngăn record đi vào prompt.

Nếu không chứng minh được deletion verification hoặc data retention của provider,
không bật Zep cho production data.

## 8. Context assembly khi dùng Zep

Context phải được route theo memory type:

```text
working memory       → current conversation
PostgreSQL profile   → explicit user facts
PostgreSQL memory    → canonical/current facts
Zep episodic         → past trajectory and reflection
semantic retrieval   → domain/source knowledge
tool observations    → current verified evidence
```

Tất cả layer đi qua một budget manager trước khi gọi model. Budget manager phải
ghi lại `raw_tokens`, `allocated_tokens`, `used_tokens`, `trimmed` và
`drop_reason` cho từng layer. Không dùng character budget riêng lẻ như tổng
ngân sách duy nhất.

Thứ tự ưu tiên mặc định:

1. Policy và system constraints.
2. Current task và verified tool observations.
3. Working memory.
4. Explicit profile/canonical facts.
5. Relevant episodic memory.
6. Semantic retrieval.

Zep không được làm mất policy context hoặc evidence hiện tại chỉ vì context
đã gần đầy.

### Clarification gate

Trước khi `action` node chạy, pipeline phải kiểm tra:

```text
required fields complete?
  no → create clarification_request, stop before tool call
  yes
    conflict with memory?
      yes → ask user to update/use-once/keep/cancel
      no  → continue to tool planner
```

Clarification là state của request, không phải long-term memory. Câu trả lời
của user chỉ được ghi thành memory khi user chọn rõ `update_memory`; chọn
`use_once` chỉ có hiệu lực trong `action_request_id` hiện tại.

## 9. Rollout plan

### Phase 0 — Contract và fixture

- Chốt `MemoryProvider` adapter.
- Chốt scope mapping giữa PostgreSQL và Zep.
- Thêm synthetic fixtures cho profile, episode, semantic và mixed query.
- Định nghĩa deletion verification.

### Phase 1 — Shadow benchmark

- Seed Zep bằng dữ liệu synthetic/redacted.
- Chạy bộ evaluation 11 case của memory lab và bộ golden P-004.
- Không dùng Zep để tạo response.
- Ghi hit rate, forbidden retrieval, latency và token reduction.

### Phase 2 — Episodic pilot

- Chỉ bật Zep cho `episode` và `reflection`.
- PostgreSQL vẫn authoritative cho profile và canonical memory.
- Bật fallback bắt buộc.
- Kiểm tra deletion/revoke trên từng scope.

### Phase 3 — Active mixed retrieval

- Bật Zep cho nhóm user/pilot đã consent.
- Có feature flag và kill switch theo provider.
- So sánh với baseline PostgreSQL theo cohort.
- Chỉ mở rộng sau khi QA và Technical Lead duyệt evidence.

## 10. Acceptance criteria

Không chuyển sang Active nếu chưa đạt:

- Memory hit rate không thấp hơn baseline PostgreSQL trên golden set.
- Không có cross-user hoặc cross-scope retrieval.
- Không có revoked/deleted memory trong retrieval mới.
- Candidate không xuất hiện như confirmed fact.
- Zep timeout/error luôn fallback thành công.
- Có provenance cho mọi memory được đưa vào prompt.
- Conflict với memory phải tạo clarification trước khi tool/action chạy.
- Thiếu required field phải tạo clarification thay vì đoán hoặc gọi tool sớm.
- `use_once` không làm thay đổi long-term memory.
- `update_memory` tạo version/evidence mới ở PostgreSQL trước khi sync sang Zep.
- Có idempotent retry và dead-letter evidence.
- Có đo p95 latency và token reduction.
- Có runbook rollback bằng feature flag.

Các ngưỡng số cụ thể phải được QA/Technical Lead chốt trên golden set; tài liệu
này không tự đặt ngưỡng thay cho acceptance decision của PO/QC.

## 11. Rollback

Kill switch tắt Zep retrieval và Zep write-back. Agent quay về:

- working memory hiện tại;
- PostgreSQL profile/canonical retrieval;
- PostgreSQL chunk retrieval;
- tool observations hiện tại.

Rollback không xóa PostgreSQL memory và không thay đổi authority/status. Các job
Zep đang chờ được pause hoặc dead-letter theo runbook, không retry vô hạn.

## 12. Các quyết định cần duyệt

- Technical Lead: có chấp nhận Zep làm derived provider không.
- PM/PO: scope user và loại dữ liệu được pilot.
- QA: golden set, deletion verification và acceptance thresholds.
- Security/Privacy owner: consent, PII minimization, retention và data residency.

Cho tới khi các quyết định này được ghi nhận, Zep chỉ ở trạng thái proposal hoặc
shadow experiment; không coi là production source of truth.
