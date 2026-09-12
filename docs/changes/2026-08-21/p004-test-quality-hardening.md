# WHAT_CHANGED — P-004 test quality hardening

| Field | Value |
| --- | --- |
| Task ID | `p004-test-quality-hardening-20260821` |
| Status | Integrated into clean deploy candidate |
| Date | `2026-08-21` |
| Lead | `Codex/Tatejo` |
| Agents / lanes | `Codex: implementation/integration; Antigravity: read-only review` |
| Base SHA | `97bd89649c3e7c6b060828870354c684fb8d6019` |
| Head / merge SHA | `9acd3ac` lane commit; `67a05a9` integration commit; `4eef2a8` clean-checkout test fix |
| PR / issue / ADR | `none` |

## Intent and acceptance criteria

- Intent: xử lý các finding P1/P2 đã được reviewer xác nhận về CI coverage, Ruff, secret-shaped placeholders và test assertions.
- Observable acceptance criteria:
  - `ruff check src/ tests/` không còn E402 từ bootstrap test.
  - CI phân biệt smoke/full đúng với thay đổi config/observability và PR `develop` được trigger.
  - `.env.example` không chứa giá trị key-shaped non-empty.
  - Các test được bổ sung assertion kiểm chứng hành vi, không chỉ status/timing.
- Non-goals: không deploy, không merge main, không xoá hàng loạt test duplicate trước khi có inventory và canonical ownership rõ ràng.

## Changes

- Observable behavior: Ruff bootstrap imports được allowlist có chủ đích; PR config/observability changes chạy full backend mode; PR `develop` được trigger; OAuth test kiểm tra Google host/state; quota event test không còn sleep cứng; env template không chứa key-shaped non-empty values.
- Components/files: CI workflow, path classifier, test bootstrap, OAuth assertions, timezone normalization, account deletion cleanup, routine/Slack classifiers, env template và regression tests.
- Config/migration/API compatibility: không đổi API/database schema.

## Agent handoffs and integration

- Ownership boundaries: Codex là writer duy nhất trên checkout hiện tại; reviewer read-only.
- Integration order/conflicts: sửa blocker/lane classifier trước, rồi assertions và cleanup an toàn.
- Independent review: Tatejo reviewed the complete diff and duplicate-test removal; no extra lane because quota was TIẾT KIỆM.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `ruff check src/ tests/ --output-format concise --cache-dir /tmp/p004-ruff` | `pass` | `2026-08-21` |
| `.venv/bin/pytest -q tests/test_scripts/v1/test_ci_changed_components.py tests/test_api/v1/test_google_login.py tests/test_api/test_conversations.py tests/test_api/v1/test_conversations.py` | `68 passed, 1 warning in 72.58s` | `2026-08-21` |
| `.venv/bin/pytest -q --tb=short <8 PR smoke paths>` | `88 passed, 1 warning in 29.77s` | `2026-08-21` |
| `python3` YAML parse for `.github/workflows/ci.yml`, `.github/workflows/checks.yml` | `pass` | `2026-08-21` |
| `git diff --check` | `pass` | `2026-08-21` |
| `.venv/bin/pytest -q --tb=short <12 affected suites>` | `246 passed` | `2026-08-21` |
| `.venv/bin/ruff check src/ tests/ --output-format concise --cache-dir /tmp/p004-ruff` | `pass` | `2026-08-21` |
| Python YAML parse for CI workflows | `pass` | `2026-08-21` |
| Full clean integration suite: `pytest tests/ -q --tb=short` | `1958 passed, 7 skipped in 206.59s` | `2026-08-21` |

Tests not run and reason: no frontend diff, therefore frontend test/build is not required for this backend deployment.

## Risk, rollback and follow-up

- Risks: thay đổi trigger/mode CI có thể làm tăng số job ở các PR sửa config; duplicate test cleanup ngoài file LangSmith canonical cần review riêng.
- Rollback: revert các commit của task này sau khi có head SHA.
- Follow-up: inventory và loại test duplicate theo canonical tree; xử lý docs stale và routine catch-up semantics.

## Merge and deployment

- Merge status: integrated on clean branch; pending fast-forward to main.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: none.
- Previous known-good / rollback verification: base SHA ở trên.

| Item | Value |
| --- | --- |
| Batch / date | `p004-test-quality-hardening-20260821` / `2026-08-21` |
| User-visible update | `CI và test gate đáng tin cậy hơn` |
| Scope | `backend tests + GitHub Actions; none deployed` |
| Source | `67a05a9` + clean-checkout fix `4eef2a8` |
| Validation | `ruff pass; targeted 246 pass; full integration 1958 pass / 7 skip; YAML/diff checks pass` |
| Status | `Integrated` |
| Rollback | `revert task changes to base SHA` |
