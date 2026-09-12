# WHAT_CHANGED — LangSmith PII redaction

| Field | Value |
| --- | --- |
| Task ID | `langsmith-pii-redaction` |
| Record schema | `v2` |
| Status | Validated, uncommitted |
| Date | `2026-08-27` |
| Lead | Codex |
| Agents / lanes | `Existing uncommitted production implementation; Codex: regression-test validation, full-suite proof, reporting` |
| Base SHA | `960a47037bd5221a32a4add58e0a7926d9b9aec8` after fetch/rebase |
| Head / merge SHA | not merged |
| PR / issue / ADR | `BRIEF.md`; `docs/projects/engineering/llm-routing.md` §7 |

## Intent and acceptance criteria

- Intent: Mask stable email/phone identifiers only at the outbound LangSmith boundary and allow complete input/output hiding.
- Observable acceptance criteria: all eight BRIEF privacy tests pass; nested trace payloads contain no raw email; missing salt fails loudly when redaction is initialized.
- Non-goals: old trace deletion, production config, DB/LLM prompt redaction, frontend, person-name detection.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: outbound observability contains raw private content although architecture forbids it.
- Root cause and shared fix boundary: the SDK-created global client has no anonymizer; fix the single global LangSmith client boundary.
- Dossier: not applicable; BRIEF supplies the verified incident and complete privacy invariant.
- Sibling cases and counterexample: inputs, outputs, metadata, errors, nested values; non-PII text must remain byte-for-byte unchanged.

## Changes

- Observable behavior: outbound LangSmith payloads replace email/phone values with stable HMAC tokens; URL context and non-PII text remain intact; nested objects are copied and recursively redacted; empty salt raises `ValueError`.
- Components/files: `src/guardrail/pii.py`, `src/langsmith_tracing.py`, startup wiring/config templates, and `tests/v1/test_pii.py`.
- Config/migration/API compatibility: config-only addition; no schema/API migration.

## Agent handoffs and integration

- Ownership boundaries: production diff was preserved; Codex completed validation/reporting for `tests/v1/test_pii.py` without changing production behavior.
- Integration order/conflicts: production implementation then test/review; no overlapping writer.
- Regression sensitivity: a temporary bypass of `redact_text` made 6/8 tests fail; the mutation was immediately reverted and all 8 passed again.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID=test-client GOOGLE_CLIENT_SECRET=test-secret PYTHONPATH=. <repo-venv>/python -m pytest -q -p no:randomly --ignore=tests/v1/test_pii.py` | `2830 passed, 7 skipped, 0 failed` on rebased `origin/main@960a470` | 2026-08-27 |
| `PYTHONPATH=. <repo-venv>/python -m pytest -q -p no:randomly tests/v1/test_pii.py` | `8 passed, 0 failed` | 2026-08-27 |
| Temporary mutation: `redact_text` returns input unchanged; same focused pytest | `6 failed, 2 passed`; mutation reverted, then `8 passed` | 2026-08-27 |
| `<repo-venv>/ruff check` on all changed Python files | `All checks passed!` | 2026-08-27 |
| `<repo-venv>/ruff check src/ tests/` | `1` pre-existing/upstream import-order failure at `src/api/connections.py:1`; no PII file failed | 2026-08-27 |
| `GOOGLE_CLIENT_ID=test-client GOOGLE_CLIENT_SECRET=test-secret PYTHONPATH=. <repo-venv>/python -m pytest -q -p no:randomly` after tests | `2838 passed, 7 skipped, 0 failed`; exact delta `+8` | 2026-08-27 |

Proof level / claim ceiling: local targeted, negative mutation proof, scoped Ruff and full-suite before/after passed; CI and branch protection remain unverified.

Tests not run and reason: no test skipped by this task; repository reported 7 existing skips in both baseline and after. CI/current branch protection were not invoked or externally verified. Dummy Google client credentials were required for two unrelated mocked refresh-token tests because the clean worktree has no credential fixture.

Enforcement levels: local owner is `pytest tests/` / `make test`; no checked-in pre-commit hook was found; `.github/workflows/checks.yml` invokes full pytest and Ruff when its backend/full input is selected, but no run for this uncommitted revision exists; branch-protection enforcement is unverified.

## Risk, rollback and follow-up

- Risks: phone false positives; alternate percent-encoding forms are outside this brief; unconfigured production salt intentionally blocks tracing initialization.
- Rollback: disable `LANGSMITH_PII_REDACTION_ENABLED` only as an incident response, or revert this uncommitted diff.
- Follow-up: Thái decides whether to delete historical LangSmith traces and whether to add person-name NER later; upstream should make the two Google refresh tests self-contained instead of relying on ambient client credentials. The measured baseline moved from the stated `2829@0396e6f` to `2830@960a470` because `origin/main` advanced during the required fetch.

## Merge and deployment

- Merge status: not committed per brief.
- Environment / deployed SHA or artifact: none.
- Health/log evidence: not applicable.
- Previous known-good / rollback verification: base SHA above.

| Item | Value |
| --- | --- |
| Batch / date | `langsmith-pii-redaction` / `2026-08-27` |
| User-visible update | LangSmith traces redact stable email/phone identifiers when configured. |
| Scope | backend and worker source only; no deploy |
| Source | uncommitted worktree based on `960a470` |
| Validation | baseline `2830` → full `2838` (`+8`, 0 failed); focused `8 passed`; scoped Ruff passed |
| Status | Validated locally, not integrated |
| Rollback | revert uncommitted diff |
