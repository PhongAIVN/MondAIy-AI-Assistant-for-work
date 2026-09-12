# LLM cost observability

## Objective

Hoàn tất quan sát usage LLM theo model/lane/user nội bộ: token, estimated cost,
latency, terminal status và các agent outcome đo được; không đưa raw user ID,
email, prompt hay response vào Prometheus/LangSmith.

## Research and authority

- `AGENTS.md`, `BRIEF.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`.
- Source thật: `src/observability.py`, `src/services/llm.py`, mọi điểm dựng
  `ChatOpenAI`, agent graph, scope ContextVar, model/account deletion và Alembic.
- Tests thật: observability regressions, graph state tests, failover tests và
  `tests/test_alembic/test_migrations.py`.
- Main được fetch/rebase và xác nhận tại `1d46314` ngày 2026-08-27.

## Scope and ownership

- Một writer: main Codex; không delegate agent/lane khác.
- Base SHA = head SHA `1d46314`; toàn bộ feature còn là uncommitted worktree diff
  theo yêu cầu của Thái.
- Runtime: callback dùng chung cho các đường LangChain và sensor riêng cho
  provider không expose usage; ledger `llm_usage_events`; `/metrics` aggregate.
- Privacy: DB nội bộ giữ user ID để query/deletion; Prometheus chỉ xuất HMAC có
  `app_secret_key`. Không có secret hoặc scope thì chỉ xuất missing reason.
- System metrics: guardrail outcome/reason allowlist, grounding allowlist,
  tool-loop histogram và intent backend allowlist.

## Observable behavior

- Response có `usage_metadata` tăng token/cost/latency/call và ghi ledger.
- Thiếu usage tăng `p004_llm_usage_metadata_missing_total`, không tạo token 0 giả.
- Thiếu price vẫn đếm token, tăng `p004_llm_pricing_unknown_total`, không tạo cost.
- Error/timeout có status bounded và latency, không bị tính là missing usage.
- `current_agent_user_id` đọc ContextVar tại thời điểm call bắt đầu; `_pop_start`
  không evaluate fallback clock khi run đã có start event.
- Alembic chỉ có một head: `f6b9d12e4a70`, nối `d7e2a9c1f4b8`.

## Files

- Runtime/config/model/migration: `src/config.py`, `src/observability.py`,
  `src/models/llm_usage.py`, `src/models/__init__.py`,
  `src/services/llm_observability.py`, `src/services/llm_usage_scope.py`,
  `src/services/scope.py`, `src/services/account_deletion.py`,
  `alembic/versions/f6b9d12e4a70_llm_usage_observability.py`.
- Instrumented callers: `src/services/{llm,conversation_title,document_extraction,
  google_sheet_task_extraction,memory_intent,task_breakdown,vision}.py`,
  `src/agents/briefing/llm_intent.py`, `src/agents/nodes/core_nodes.py`,
  `src/agents/graph.py`.
- Proof: `tests/test_services/v1/test_llm_observability.py`,
  `tests/test_observability_agent_metrics.py`, Alembic/agent/failover test updates,
  `BAOCAO.md`.

## Commands and real results

- `git fetch origin && git rebase origin/main`: pass; stash restored without conflict.
- Focused failing set after implementation: `6 passed`.
- Broader focused suite (observability, Alembic, graph, failover): `39 passed`.
- Full `pytest -q -p no:randomly`: `2818 passed, 0 failed, 7 skipped`.
  Before baseline `2814 passed` was supplied by Thái for the same environment;
  failure-name set after the final run is empty.
- `ruff check src/ tests/`: `All checks passed!`.
- `git diff --check`: pass.
- Isolated uvicorn with temp SQLite, embedded worker off; real `curl /metrics`:
  HTTP 200, tokens 100/50, cost 0.0004, missing usage 1, unknown pricing 1,
  pseudonymous user hash only. Instance shut down cleanly.

## Risk, migration, config and rollback

- Migration/config impact: one nullable usage ledger with two indexes; model price
  map in config. Production schema/config were not inspected or changed; no deploy.
- Known drift remains: runtime LLM provider versus OpenRouter/OD-03. This task
  observes existing routes and does not resolve that architecture decision.
- Price values can age; unknown models fail explicitly through pricing metric.
- Rollback before commit: discard this task's listed diff. After integration,
  downgrade migration one revision and revert the single integration commit.

## Merge/deploy/follow-up

- Not committed, merged, pushed or deployed, per explicit instruction.
- Grafana dashboard and LangSmith production configuration remain out of scope.
