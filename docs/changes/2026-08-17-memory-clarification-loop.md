# WHAT_CHANGED — Memory conflict và tool clarification loop

| Field | Value |
| --- | --- |
| Task ID | `docs-memory-clarification-loop` |
| Status | Planned |
| Date | `2026-08-17` |
| Lead | Codex |
| Agents / lanes | `single docs lane: memory/action clarification contract` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` |
| Head / merge SHA | not committed |
| PR / issue / ADR | Proposed implementation contract; no new ADR approved |

## Intent and acceptance criteria

- Intent: ghi rõ luồng hỏi lại user khi memory conflict hoặc tool/action thiếu
  thông tin.
- Observable acceptance criteria:
  - Không gọi tool bằng dữ liệu đoán khi required field thiếu.
  - Không tự overwrite memory khi user input mâu thuẫn.
  - Có `clarification_request`, resolution và expiry contract.
  - Zep chỉ nhận event đã resolve sau PostgreSQL commit.
- Non-goals: thay đổi runtime, schema migration, API implementation hoặc UI.

## Changes

- Observable behavior: tài liệu yêu cầu pipeline dừng và hỏi lại trước tool/action.
- Components/files: `memory-lifecycle.md`, `zep-memory-provider-proposal.md`.
- Config/migration/API compatibility: chưa thay đổi; implementation cần contract
  review trước khi tạo migration/API.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `rg -n -i "clarification|missing|required field" docs/projects/engineering/memory-lifecycle.md docs/projects/engineering/zep-memory-provider-proposal.md` | pass; contract sections found | 2026-08-17 |
| `git diff --check` | pass; no whitespace errors | 2026-08-17 |

Tests not run and reason: docs-only change, không có code/runtime thay đổi.

## Risk, rollback and follow-up

- Risks: clarification contract cần được map vào API/state hiện tại; không tự
  coi tài liệu là approval của PRD/ADR.
- Rollback: revert tài liệu; runtime không bị ảnh hưởng.
- Follow-up: Technical Lead chốt state/schema, PO/QC chốt acceptance, frontend
  chốt UI cho conflict/missing/expired/confirmed.

## Merge and deployment

- Merge status: chưa commit/merge.
- Environment / deployed SHA or artifact: không áp dụng.
- Health/log evidence: không áp dụng.
- Previous known-good / rollback verification: runtime không thay đổi.
