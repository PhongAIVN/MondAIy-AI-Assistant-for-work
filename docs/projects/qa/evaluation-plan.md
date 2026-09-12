# Evaluation plan — Source Sync, Memory, Ask và Act

| Thuộc tính | Giá trị |
| --- | --- |
| Status | In review |
| Owner | Nguyễn Đức Dũng (PO/QC) |
| Reviewers | PM, Tech Lead, Extension Lead |
| Last updated | 2026-08-04 |
| Related | [PRD](../product/prd.md) · [Memory lifecycle](../engineering/memory-lifecycle.md) · [Roadmap](../product/roadmap-6-weeks.md) |

Từ vựng sản phẩm nằm ở [bảng thuật ngữ trong PRD](../product/prd.md#thuật-ngữ-cần-biết-trước-khi-đọc).
Tài liệu này chỉ định nghĩa thêm từ vựng riêng của kiểm thử, xem
[phụ lục](#phụ-lục--thuật-ngữ-kiểm-thử).

## 1. Mục tiêu

Đánh giá toàn pipeline thay vì chỉ chấm chất lượng câu trả lời:

```text
Source sync durability
→ evidence/version correctness
→ extraction/memory safety
→ retrieval/grounding
→ action fidelity
→ user outcome
```

## 2. Test layers

### Unit/property

- Source ID normalization/content hash.
- Date/time/timezone và ambiguous expressions.
- Dedupe/idempotency.
- Memory state transition.
- Permission predicates.
- Priority/rerank rules.
- ICS/template encoding.

### Contract/integration

- Connector ↔ FastAPI OpenAPI/event schema.
- Postgres migrations và RLS trên database thật.
- Worker retry/dead-letter.
- Provider malformed JSON, timeout, 429 và partial response.
- Citation permission recheck sau revoke.
- Delete/retention propagation.

### Product E2E

- Onboarding/permission denied/disconnect.
- Calendar/Jira/Discord/VLearn/Gmail connector scope.
- Connector timeout, worker restart và retry.
- Source item version change.
- Brief success/empty/partial/conflict.
- Ask answerable/unanswerable.
- Memory confirm/edit/reject/delete.
- Action preview/edit/confirm/double-click/source change.

## 3. Golden sets

| Set | Minimum v1 | Categories |
| --- | ---: | --- |
| Source sync/version | 20 fixtures | duplicate, changed, timeout, retry, revoked |
| Extraction/memory | 50 records | fact, preference, goal, decision, commitment, no-memory |
| Temporal/conflict | 20 cases | update, cancel, replaced, stale, disputed |
| Q&A | 30 questions | single, multi-source, conflict, temporal, stale |
| Unanswerable | 10 questions | missing source, revoked, unknown time/assignee |
| Action | 20 cases | title, type, time, timezone, missing fields, duplicate |
| Permission | 15 negative cases | cross-user, cross-program, revoked citation |
| Adaptive learning | 16 fixtures | xem danh sách tối thiểu trong execution plan P1, mục Pre-Registered Evaluation Matrix — lặp lại xuyên phiên, one-off, instruction trái phong cách, injection, secret, counterexample skill, reset |

Mỗi sample chứa:

- Synthetic/redacted source snapshot và version.
- Expected structured output.
- Evidence/citation expectation.
- Reviewer và adjudication status.
- Model/prompt/embedder/retrieval/extractor versions.

Không để agent tự tạo cả fixture và ground truth mà không human adjudication.

## 4. Metrics

### Source sync

- Queued-item durability.
- Duplicate rate.
- Correct source-item version rate.
- Source-to-ACK latency.

### Memory

- Candidate extraction precision/recall theo kind.
- Canonical memory evidence coverage.
- Promotion violation rate.
- Conflict/version accuracy.
- Temporal validity accuracy.
- Revoked-memory retrieval rate.

### Ask

- Citation coverage.
- Citation correctness.
- Grounded claim accuracy.
- Abstention accuracy.
- Conflict answer accuracy.
- Retrieval recall@k.

### Act

- Field accuracy theo title/type/time/timezone/source.
- Missing-field behavior.
- Duplicate action rate.
- Unsafe action rate.
- Source-change warning rate.

### Product

- Brief open ≥4/7 days.
- Helpful answer.
- Confirmed action adoption.
- Context-to-action completion.
- Weekly Task Completion Rate và mức tăng so với baseline.
- Self-reported reduction in search/check/re-entry.

## 5. Release thresholds

| Gate | Threshold |
| --- | --- |
| Event durability | 100% trong controlled restart/offline suite |
| Retry duplicate | 0 |
| Published citation coverage | 100% |
| Reviewed citation correctness | 100% |
| Canonical memory evidence coverage | 100% |
| Inferred-as-confirmed | 0 |
| Source-A recall | 100% trên bounded pilot set |
| Unsupported deadline/assignee | 0 |
| Abstention accuracy | ≥95% |
| Unsafe action | 0 |
| Cross-user leak | 0 |
| Adaptive learning: unsafe activation, revoked-evidence use, retry duplicate | 0 (blocker) |
| Adaptive learning: style candidate precision / adherence | ≥90% / ≥90%, safety-citation-permission delta = 0 |
| Adaptive learning: skill precision; security + counterexample pass | ≥85%; 100% bắt buộc trước activation |
| Adaptive learning: candidate volume | ≤3 đề xuất mới/user/tuần; ≤5 pending |

Behavior thresholds với 5–10 users mang tính directional; trust/safety thresholds là blockers. Ngưỡng adaptive learning là pre-register theo [ADR-017](../engineering/adr/adr-017-adaptive-learning-p1-hermes.md): chốt số cuối trước khi chạy model trên golden set.

## 6. Regression policy

- Unit/contract/static tests chạy mọi PR.
- AI golden subset chạy mọi PR thay prompt/retrieval/memory.
- Full golden set chạy nightly và trước release.
- Live OpenRouter smoke tách khỏi deterministic CI.
- Mọi pilot failure được phân loại và thêm regression fixture sau adjudication.
- Model/prompt/version thay đổi không deploy nếu không có before/after report.

## 7. Failure taxonomy

- Source item missed/lost/duplicated.
- Wrong source-item version.
- Wrong/no provenance.
- Incorrect candidate extraction.
- Unsafe promotion.
- Conflict overwritten.
- Permission leak/revoked data retrieved.
- Retrieval miss.
- Unsupported/hallucinated claim.
- Wrong/inaccessible citation.
- Failed abstention.
- Ambiguous time normalized incorrectly.
- Action before confirm/duplicate.
- Source changed without warning.
- False complete coverage.

## 8. Pilot quality review

Mỗi ngày pilot:

1. Chạy golden regression.
2. Review source health, queue lag và provider errors.
3. Review all incorrect/missing-source feedback.
4. Adjudicate new failure.
5. Chỉ ship P0/regression fix.
6. Ghi model/prompt/retrieval version.
7. Cập nhật blocker/rollback decision.

## Phụ lục — Thuật ngữ kiểm thử

Bảng này chỉ giải thích từ vựng riêng của kiểm thử. Từ vựng sản phẩm tra ở
[bảng thuật ngữ trong PRD](../product/prd.md#thuật-ngữ-cần-biết-trước-khi-đọc),
không định nghĩa lại ở đây.

| Thuật ngữ | Giải thích | Ghi chú |
| --- | --- | --- |
| **Fixture** | Bộ dữ liệu giả, viết tay, đóng băng, dùng làm đề bài khi chạy thử. Dữ liệu đứng yên nên test đỏ chắc chắn là do mã sai, không phải do nguồn thật vừa đổi. | Phải là synthetic hoặc đã redact, không bao giờ là dữ liệu thật |
| **Ground truth** | Đáp án đúng của một fixture, do người chốt. Kết quả máy chạy ra được đem so với đáp án này. | Người soạn fixture không được là người chốt đáp án |
| **Adjudication** | Việc một người xem xét và chốt đáp án đúng cho một case, nhất là khi case gây tranh cãi. | Bắt buộc trước khi một case được tính là hợp lệ |
| **Golden set** | Bộ đề chuẩn gồm fixture kèm ground truth, cố định, chạy lại mỗi lần sửa mã. Điểm tụt nghĩa là vừa làm hỏng thứ đang chạy đúng. | Ngưỡng tối thiểu ở [mục 3](#3-golden-sets) |
| **Golden subset** | Một phần của golden set, dùng khi chưa đủ thời gian chạy toàn bộ. | Sprint 2 dùng subset tối thiểu 12 case |
| **Manifest** | Danh mục đi kèm bộ fixture: mã case, kiểm tra điều gì, đáp án, ai chốt, ngày nào. | Không có manifest thì bộ fixture không dùng làm bằng chứng được |
| **Unit test** | Thử một mảnh mã nhỏ tách rời khỏi phần còn lại. | [Mục 2](#2-test-layers) |
| **Contract test** | Thử hai thành phần có khớp đúng hình dạng dữ liệu đã cam kết với nhau không. | Bắt lệch giữa backend và extension trước khi tích hợp |
| **E2E** | Thử xuyên suốt từ đầu tới cuối như người dùng thật: nạp nguồn, rút trích, hiện lên giao diện. | Khác unit test ở chỗ chạy qua mọi tầng |
| **Regression test** | Chạy lại bộ đề cũ để chắc thay đổi mới không làm hỏng thứ trước đó đã đúng. | [Mục 6](#6-regression-policy) |
| **Mock** | Bản giả thay cho thành phần thật đắt, chậm hoặc không ổn định, ví dụ mô hình AI. | Không dùng mock ở tầng E2E |
| **Chế độ dữ liệu giả** | Công tắc trong extension: bật thì giao diện đọc dữ liệu giả tại chỗ, tắt thì gọi API thật. Cho phép làm giao diện trước khi backend xong. | `mock mode`, `WXT_MOCK_MODE` |
| **Coverage của mã** | Tỷ lệ dòng mã được test chạy qua. Khác hoàn toàn với **mức độ đầy đủ** của bản tóm lược trong PRD. | Hai khái niệm cùng gọi là `coverage`, đọc kỹ ngữ cảnh |
| **Negative case** | Case cố tình sai hoặc không được phép, để kiểm hệ thống có chặn đúng không. | Ví dụ: đọc dữ liệu của người khác |
| **Severity** | Mức nghiêm trọng của một lỗi, quyết định lỗi đó có chặn phát hành hay không. | [Mục 7](#7-failure-taxonomy) |
| **Repro** | Các bước tái lập lỗi, đủ để người khác làm lại y hệt. | Thiếu repro thì lỗi không được nhận |
