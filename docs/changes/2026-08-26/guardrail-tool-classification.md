# Guardrail tool classification

- Objective: gỡ false block cho 6/26 registry tool và thêm guard test để mọi tool mới phải được phân loại tường minh trước khi qua `action_node`.
- Authority: brief của An Hoài Thái ngày 2026-08-26; fail-closed của unknown tool trong `src/guardrail/policy.py` phải được giữ nguyên.
- Research sources: `src/agents/nodes/core_nodes.py`; implementation/docstring của `plan_tool.py`, `program_information_tool.py`, `drive_search_tool.py`, `web_search.py`, `task_tool.py`; read paths trong `src/services/program_information.py`, `src/services/task_ownership.py`, `src/connectors/google_drive.py`.
- Scope: chỉ thêm tên thật vào policy và regression tests; không đổi tool behavior, registry, planner, runtime gate hay `src/services/intent_router/tool_planning.py`.
- Agents/ownership: lead agent là writer duy nhất cho `src/guardrail/policy.py`, tests và evidence; hai lane read-only review độc lập classification và test shape, không sửa file/commit.
- Base/head: `7cd011a79459aa1bb695b86acc3f0bf35d01b214` / worktree chưa commit theo yêu cầu.
- Observable behavior: `plan_my_day`, `program_information_search`, `drive_search_files`, `web_search` là `SAFE_READ`; `suggest_tasks`, `suggest_calendar_events` là `INTERNAL_COMPUTATION`; cả 26 tool đi qua cùng biểu thức gate của `action_node`.
- Files: `src/guardrail/policy.py`; `tests/test_agents/v1/test_agent_loop_hardening.py`; record này.
- Positive proof: focused guard + real `action_node(plan_my_day)` → `2 passed`; runtime measurement với web search bật → `registry=26 blocked=0 names=[]`; focused file → `36 passed`; Ruff và `git diff --check` passed.
- Negative proof: tạm bỏ classification `plan_my_day`, guard test fail với diagnostic `Registry tool chưa qua action_node guardrail: plan_my_day`; classification được khôi phục ngay và positive proof chạy lại xanh.
- Full check: `APP_SECRET_KEY=<64-char test value> <project-venv-python> -m pytest tests/ -q` ngoài sandbox để truy cập PostgreSQL test DB → `2681 passed, 7 failed, 2 skipped`; baseline do user cung cấp `2679 passed, 7 failed, 2 skipped`; tăng đúng 2 pass. Tập 7 failure giữ nguyên nhóm baseline: 6 attachment-extract tests thiếu OpenAI credential và 1 deploy concurrency expectation.
- Enforcement: local pytest/ruff có và đã chạy; không cài hook; `.github/workflows/checks.yml` có gọi Ruff + pytest nhưng chưa xác minh run hiện tại; branch protection chưa xác minh.
- Risk: `drive_search_files` có thể refresh OAuth credential gián tiếp trong read connector và `web_search` dùng network quota, nhưng không tạo write nghiệp vụ; web search vẫn chịu feature flag hiện hữu. Không migration/config/deploy.
- Rollback: bỏ 6 tên khỏi hai frozenset và bỏ 2 regression tests; unknown-tool fail-closed không thay đổi.
- Merge/deploy/follow-up: chưa commit, push, merge hoặc deploy; chờ Thái review. Tool thứ 27 chưa classification sẽ làm guard test đỏ kèm đúng tên và hướng dẫn sửa policy.
