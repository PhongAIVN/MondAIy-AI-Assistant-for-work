# ADR-001 — Personal Context Engine với Program Navigator là vertical đầu tiên

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Approved |
| Owner | Thái Hoài An (PM) + Nguyễn Văn Phong (Technical Lead) |
| Author | Thái Hoài An (PM) |
| Reviewers | AI/Memory Lead, Extension Lead, Product Designer, QA Lead |
| Last updated | 2026-07-30 |
| Related | [1-page brief](../../product/one-page-brief.md) · [PRD](../../product/prd.md) · [Architecture](../architecture.md) |

## Context

Project bắt đầu như AI Program Navigator cho cohort nhưng prototype và market research cho thấy primitive có giá trị rộng hơn: thu thập browser/meeting context, xây personal memory và biến context thành hành động. Nếu chỉ xây cohort-specific pipeline, phần lõi khó tái sử dụng. Nếu xây trợ lý cá nhân đa năng ngay, scope sáu tuần không thể đạt quality bar.

## Decision

Xây theo hai lớp:

1. **Personal Context Engine**
   - Capture từ browser, meeting và adapter khác.
   - Evidence/provenance/versioning.
   - Personal memory và retrieval.
   - Typed agent tools.
   - Action Draft với human approval.

2. **AI Program Navigator**
   - First vertical dùng engine cho một cohort.
   - Program Frame, team/role personalization.
   - Daily Brief, grounded Ask và Calendar/reminder handoff.

P0 sáu tuần chỉ được coi là thành công khi vertical cohort chạy end-to-end với dữ liệu thật và đạt trust guardrails. Generic platform capability chỉ được xây khi nó phục vụ trực tiếp journey đó.

## Consequences

### Positive

- Capture/memory/action primitives tái sử dụng được cho personal productivity vertical khác.
- Cohort cung cấp bounded corpus, source authority và golden set để đánh giá.
- Có thể thử web, meeting và memory mà không hứa “hiểu mọi thứ”.
- Boundary adapter giảm lock-in với Vexa, Hindsight, OpenRouter và Calendar provider.

### Trade-offs

- Data model và API cần phân biệt platform entity với vertical entity.
- Phải đầu tư provenance/versioning sớm.
- Một số UX platform như Memory Inspector xuất hiện trước khi mở rộng use case.
- P0 không thể đồng thời hoàn thiện live meeting bot, Calendar OAuth và all-web general assistant.

## P0 decisions

- Pilot một cohort, 5–10 users; load test 50 users.
- Browser allow-list mặc định; all-web chỉ internal dogfood.
- Transcript import là meeting fallback bắt buộc; Vexa adapter là feature flag.
- Calendar P0 dùng template URL/`.ics`; OAuth là P1.
- Canonical data/memory nằm trong PostgreSQL; Hindsight không là source of truth.
- Một Pydantic AI orchestrator dùng typed tools; không xây runtime agent swarm.

## Rejected alternatives

### Chỉ xây Program Navigator

Nhanh hơn ngắn hạn nhưng khóa schema/capture/memory vào cohort và bỏ mất product direction cá nhân.

### Xây general personal assistant ngay

Không có bounded evaluation, dễ thành chatbot có nhiều connector và không hoàn thành pilot sáu tuần.

### Dùng memory OSS làm database duy nhất

Giảm code ban đầu nhưng mất quyền kiểm soát provenance, source authority, temporal versioning và audit.
