# WHAT_CHANGED — Đề xuất dùng Zep làm Memory Provider

| Field | Value |
| --- | --- |
| Task ID | `docs-zep-memory-provider-proposal` |
| Status | Planned |
| Date | `2026-08-17` |
| Lead | Codex |
| Agents / lanes | `single docs lane: memory architecture proposal` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | not committed |
| PR / issue / ADR | Proposed direction; no ADR approved |

## Intent and acceptance criteria

- Intent: ghi lại hướng tích hợp Zep có kiểm soát cho P-004.
- Observable acceptance criteria:
  - Engineering index liên kết tới proposal.
  - Proposal phân định PostgreSQL authoritative store và Zep derived provider.
  - Có contract adapter, fallback, privacy/delete, rollout và rollback.
  - Không tự thay đổi PRD, schema hoặc production architecture.
- Non-goals: cài SDK, thay code runtime, tạo Zep resource hoặc bật production.

## Changes

- Observable behavior: không thay đổi runtime; chỉ bổ sung tài liệu triển khai.
- Components/files: `docs/projects/engineering/zep-memory-provider-proposal.md`,
  `docs/projects/engineering/README.md`.
- Config/migration/API compatibility: không thay đổi.

## Agent handoffs and integration

- Ownership boundaries: docs-only; implementation cần Technical Lead/QA/Privacy
  review trước khi mở ADR hoặc Jira work items.
- Integration order/conflicts: proposal → contract/fixture → shadow benchmark →
  pilot; không merge runtime trước acceptance.
- Independent review: chưa chạy; cần review theo bảng DRI trong AGENTS.md.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `sed -n '1,320p' docs/projects/engineering/zep-memory-provider-proposal.md` | pass; proposal rendered and reviewed | 2026-08-17 |
| `rg -n "Zep|zep" docs/projects/engineering/README.md docs/projects/engineering/zep-memory-provider-proposal.md` | pass; index and proposal references found | 2026-08-17 |
| `git diff --check` | pass; no whitespace errors | 2026-08-17 |

Tests not run and reason: docs-only change, không có code/runtime thay đổi.

## Risk, rollback and follow-up

- Risks: proposal có thể bị hiểu nhầm là quyết định đã duyệt; Zep tạo dual-write,
  privacy và deletion obligations.
- Rollback: xóa link/proposal hoặc giữ ở trạng thái Proposed; runtime không bị ảnh hưởng.
- Follow-up: Technical Lead chốt ADR, QA chốt golden set/threshold, Privacy chốt
  consent/retention/data residency.

## Merge and deployment

- Merge status: chưa commit/merge.
- Environment / deployed SHA or artifact: không áp dụng.
- Health/log evidence: không áp dụng.
- Previous known-good / rollback verification: runtime không thay đổi.
