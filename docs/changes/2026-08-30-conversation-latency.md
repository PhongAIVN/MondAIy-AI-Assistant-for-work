# WHAT_CHANGED — Giảm latency planning conversation

| Field | Value |
| --- | --- |
| Task ID | `p004-conversation-latency-20260830` |
| Record schema | `v2` |
| Status | Deployed |
| Date | `2026-08-30` |
| Lead | `Codex` |
| Agents / lanes | `Codex: production/integration; Antigravity: test matrix, test-only regressions, independent review` |
| Base SHA | `92bc51e40ec52982611ae69900b8cc84ee45e634` |
| Head / merge SHA | `a6904181470bca0557407f527bbfc4ac006715ca` (`main`) |
| PR / issue / ADR | `Latency brief; PRD 12.5, FR-068, FR-071` |

## Intent and acceptance criteria

- Intent: loại bỏ re-plan tuần tự và context lặp cho batch tool độc lập, vẫn giữ tool dependency và không lặp side effect.
- Observable acceptance criteria: normal path không quá 2 think rounds; dependency không quá 3; planner prompt growth giữa các round dưới 15%; read tools chạy parallel trong slowest+50ms; SSE không phát reasoning.
- Non-goals: schema/migration, frontend, config/secret production, quota/billing LangSmith.

## Bug-fix generalization

- Change kind: behavior bug.
- Bug class and violated invariant: graph re-plans một batch evidence đã hoàn tất thay vì chỉ re-plan khi có dependency thực.
- Root cause and shared fix boundary: cạnh `observe → think` vô điều kiện và planning/classification chạy tuần tự; sửa tại shared graph/node boundary.
- Dossier: `docs/changes/2026-08-30-conversation-latency.bugfix.json`.
- Sibling cases and counterexample: dependency A→B, approval-mediated action, một read đơn lẻ.

## Changes

- Observable behavior: batch nhiều read độc lập chạy song song rồi có nhiều nhất một follow-up `think`; chain dừng trước action batch thứ ba; intent classification chạy song song planning; stream result loại `analysis`.
- Components/files: `src/agents/nodes/core_nodes.py`, `src/agents/graph.py`, `src/services/agent_stream.py`, targeted agent/stream tests.
- Config/migration/API compatibility: không migration/config; `analysis` không còn đi qua stream result, nên stream conversation không persist hoặc gửi reasoning nội bộ.

## Agent handoffs and integration

- Ownership boundaries: Codex là production writer; Antigravity chỉ sửa test, không production/commit/push.
- Integration order/conflicts: test-only diff không chồng production files; reviewed sau candidate.
- Independent review: Antigravity caught and rejected the first shortcut-read candidate, then returned PASS on exact SHA `a6904181`; lead reran the narrowed matrix with `59 passed`.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `rtk pytest -q tests/test_agents/v1/test_conversation_agent_nodes.py tests/test_agents/v1/test_graph.py tests/test_agents/v1/test_agent_loop_hardening.py tests/test_services/v1/test_agent_stream.py tests/test_observability_agent_metrics.py tests/test_services/v1/test_telemetry.py tests/test_services/v1/test_llm_observability.py tests/v1/test_pii.py` | `101 passed, 1 skipped` corrected candidate (baseline before test additions: `92 passed, 1 skipped`) | 2026-08-30 |
| Antigravity pre-amend matrix | `59 passed`; caught and rejected prior shortcut read regression, then verified the narrowed test matrix | 2026-08-30 |
| `rtk pytest -q tests/test_api/test_conversations.py` | `40 passed` | 2026-08-30 |
| `rtk pytest -q tests/test_api/v1/test_conversations.py tests/test_observability_langsmith.py` | `45 passed` | 2026-08-30 |
| `rtk ruff check src/agents/graph.py src/agents/nodes/core_nodes.py src/services/agent_stream.py tests/test_agents/v1/test_conversation_agent_nodes.py tests/test_agents/v1/test_agent_loop_hardening.py tests/test_services/v1/test_agent_stream.py` | pass | 2026-08-30 |
| `git diff --check` | pass | 2026-08-30 |
| `python3 scripts/validate_bug_fix_harness.py docs/changes/2026-08-30-conversation-latency.bugfix.json` | not run: validator script is absent from this checkout | 2026-08-30 |

Proof level / claim ceiling: deployed behavior + production health. Offline timing/call-count invariants are verified; production latency improvement and LangSmith quota recovery are not yet measurable because the external monthly trace limit remains exhausted.

Tests not run and reason: full repository suite is not run; scope is agent/stream/observability and targeted regressions passed. No production trace because quota is externally exhausted and production data is out of scope.

## Risk, rollback and follow-up

- Risks: stream turns no longer persist internal `analysis`; mọi read batch giữ follow-up think để không bỏ `gmail_read_email` hay `suggest_tasks` từ evidence.
- Rollback: revert the candidate commit; no data/config/migration mutation.
- Follow-up: LangSmith SDK 429 happens outside the application boundary in the background tracing client. No safe quota interceptor or runtime `telemetry.start_trace()` wiring exists in scope, so no billing/fallback policy was invented. Existing local agent metrics remain available, but correlated per-turn telemetry needs separately authorized API/telemetry contract work.

## Merge and deployment

- Merge status: fast-forwarded and pushed to `origin/main`.
- Environment / deployed SHA or artifact: production VM, `p004-backend:a6904181`.
- Health/log evidence: backend healthy; worker started on `p004-backend:a6904181`; public `/health` returned `{"status":"ok","env":"production"}`; no startup error/exception in the five-minute log window.
- Previous known-good / rollback verification: `p004-backend:rollback-a6904181` resolves to the retained `92bc51e4` image.

| Item | Value |
| --- | --- |
| Batch / date | `conversation-latency` / `2026-08-30` |
| User-visible update | Faster multi-source conversation turns; no reasoning in stream result |
| Scope | Backend agent + stream contract; backend/worker rollout |
| Source | `a6904181470bca0557407f527bbfc4ac006715ca` |
| Validation | 101 passed, 1 skipped; API 40 + 45 passed; Antigravity PASS; lead 59 passed; health/log smoke pass |
| Status | Deployed |
| Rollback | `p004-backend:rollback-a6904181` (`92bc51e4`) |
