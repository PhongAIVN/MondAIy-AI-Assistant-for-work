# Agenda bó Jira theo deadline window

## Objective

Luồng agenda dùng cùng `start/end` đã resolve cho Jira; issue không có deadline
không vào danh sách chính nhưng được báo số lượng và deep link thật để người dùng
tự quyết trên Jira. Lời gọi Jira trực tiếp không có window giữ nguyên hành vi.

## Research sources

- `AGENTS.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`
- `docs/projects/product/prd.md` FR-021
- `docs/projects/engineering/adr/adr-018-planner-xac-dinh-cho-phan-ra-va-uu-tien-viec.md`
- `src/services/intent_router/tool_planning.py`, `src/agents/tools/jira_tool.py`
- `tests/eval/routing_gold.py`, `tests/eval/test_routing_accuracy.py`

## Scope and ownership

- Lead Codex là writer duy nhất; Antigravity review độc lập, chỉ đọc diff và
  không sửa file.
- Sửa agenda tool args, Jira bounded output và tests tương ứng.
- Không sửa 23 routing regex, grounding, embedding hay `_budgeted_observations`.

## Base and head

- Branch: `fix/agenda-jira-deadline-window`
- Base/HEAD trước thay đổi: `b643f5be1df4067fb36cab9e8302fbafff0dcaee`
- Chưa commit theo yêu cầu; head Git vẫn là SHA trên, thay đổi nằm trong worktree.

## Observable behavior and files

- `src/services/intent_router/tool_planning.py`: mọi Jira call trong agenda nhận
  `due_after=start.isoformat()` và `due_before=end.isoformat()`.
- `src/agents/tools/jira_tool.py`: bounded call loại issue ngoài window và
  `due_at=NULL` khỏi danh sách chính, giữ biên trên exclusive; dùng aggregate
  đếm distinct task chưa hạn và lấy một `TaskEvidence.deep_link` có thật hoặc
  nói rõ dữ liệu không có link.
- `tests/v1/test_intent_router.py`: khóa auto call và model-proposed Jira call.
- `tests/test_agents/v1/test_jira_tool.py`: khóa lọc, summary/link, direct call
  không window và mức giảm output.

## Commands and real results

- Baseline full suite: `2743 passed, 7 skipped, 0 failed`.
- After full suite: `2746 passed, 7 skipped, 0 failed`; tăng đúng 3 test mới,
  tập test fail trước/sau đều rỗng.
- Focused: `24 passed`.
- Routing eval trước/sau: `14/21 (67%)`, `23 passed`; không gap nào chuyển đúng,
  nên không đổi status hoặc sàn.
- Ruff trên 4 Python file: `All checks passed!`.
- Jira agenda fixture cuối: output cũ `2464` ký tự, output mới `389` ký tự
  (giảm 84%).
- Antigravity nêu 2 finding (biên trên inclusive, materialize toàn bộ evidence);
  cả hai đã sửa, test biên đã pass và full suite đã chạy lại sau sửa.

## Skips, risk, config and rollout

- 1 live-LLM test cần `RUN_LLM_LIVE=1`; 5 vector tests không kết nối được Postgres
  localhost:5433 trong sandbox; 1 frontend env test skip vì worktree không phải
  git checkout. Không check nào thuộc phạm vi Jira bị bỏ qua.
- Rủi ro còn lại: bounded Jira call chạy thêm aggregate count và link lookup cho
  issue chưa hạn; không có schema, migration, config hay dữ liệu production đổi.
- Merge/deploy: chưa commit, chưa merge, chưa push, chưa deploy.
- Rollback: revert diff ở hai source file và hai test file; không có data rollback.
- Follow-up ngoài phạm vi: 23 regex routing, grounding, embedding,
  `_budgeted_observations` (PR #73).
