# WHAT_CHANGED — Lane kế hoạch ưu tiên + diagram kiến trúc agent

| Field | Value |
| --- | --- |
| Task ID | `p004-task-planning-diagrams-20260901` |
| Record schema | `v2` |
| Status | Merged to `main`, **not deployed** |
| Date | `2026-09-01` |
| Lead | `Tatejo (Claude Opus 5)` |
| Agents / lanes | `Tatejo: review, merge, conflict resolution, gate; lane phụ: dọn rác filesystem ngoài git` |
| Base SHA | `28306408413cf61fc154a71bc25464e20d12129f` |
| Head / merge SHA | `d8ed068bcd373f94ecf879770bbd41a45783347c` (`main`) |
| PR / issue / ADR | none — merge trực tiếp từ nhánh local sau review |

## Intent and acceptance criteria

- Intent: đóng đợt release cuối của repo — đưa nốt phần thật sự còn nợ lên `main`, loại phần đã trùng, và trả CI về xanh.
- Observable acceptance criteria: `ruff check src/ tests/` pass; `pytest tests/` không có fail mới so với baseline; net effect mỗi merge đúng bằng phần tính năng, không xoá nhầm file.
- Non-goals: deploy, migration, đụng production, gỡ 10 nhánh cũ còn conflict.

## Changes

- Observable behavior:
  - Câu hỏi dạng "hôm nay/tuần này + làm gì/ưu tiên/kế hoạch" đi vào **lane kế hoạch ưu tiên** (`task_planning`), trả lời terminal, **không còn đi qua agent tool-loop**. Áp cho cả `/api/v1/chat/stream` và `/api/v1/conversations/{id}/messages/stream`.
  - Hệ quả có chủ ý: câu `"Hôm nay tôi cần làm gì?"` không còn sinh `taskSuggestions` từ nguồn nữa. Thái chốt hướng này ngày 2026-09-01.
  - Thêm diagram `agent-loop-architecture` và `agent-guardrails-security-architecture` (drawio/png/svg).
- Components/files: `src/services/task_planning.py` (mới), `src/api/routes.py`, `src/api/conversations.py`, `docs/projects/engineering/agent-*`, test tương ứng.
- Config/migration/API compatibility: không migration, không đổi config, không đổi shape response.

## Nhánh đã xét và loại

Đo bằng merge thật vào `origin/main` rồi so net effect, **không dùng `git cherry`** — `git cherry` đếm commit khác SHA nên báo nhầm 47 nhánh là "còn nợ".

| Nhánh | Kết luận |
| --- | --- |
| `docs/agent-security-diagrams-20260901` | merge sạch, net effect 8 file → **đã vào** |
| `feat/task-planning-v0` | conflict 1 hunk `App.tsx` (nhánh xoá route `PlannerPage` mà `main` đã thêm) → giữ bản `main`, **đã vào** |
| `fix/calendar-readonly-403`, `fix/productivity-natural-language-prefill` | merge sạch nhưng **net effect = 0 file** → nội dung đã có trong `main` |
| `work/fpt-embedding` | migration `a1c4f7e29b30` + `fpt_embedding_model` đã có trong `main` |
| `work/qa-task`, `fix/task-inbox-priority-refresh`, `fix/announcement-natural-language-edit` | `main` đã có bản **mới hơn**; merge vào là regression |
| `agent/cohort-refresh-20260820` | conflict 8 file, commit tự khai `wip` → hoãn |
| 9 nhánh `origin/sync/*`, `origin/integrate/*`, `origin/fix/integration-*` | conflict 15–27 file, cũ từ 13–18/08 → hoãn, chờ quyết |

## Sửa CI kèm theo

- `ruff I001` ở `tests/test_alembic/test_migrations.py`: sắp lại import.
- `test_google_sheet_uncertain_proposal_stays_proposed_for_review` đỏ từ **2026-08-31**: helper `_sheet_proposal` hardcode `due_at = 2026-08-24`. `_task_drafts_from_agent_result` loại task cũ hơn `_TASK_STALE_AFTER` (7 ngày) khỏi card và dồn vào `taskBacklogCount`, nên test tự hỏng đúng 7 ngày sau ngày cứng đó. Triệu chứng: `taskDrafts: []`, `taskBacklogCount: 1`. Sửa bằng cách tính hạn theo lúc chạy.
- Bẫy đo lường: `ValueError: Chưa cấu hình OPENROUTER_API_KEY` xuất hiện trong log của test này là **warning đã được bắt** (`conftest.py:51` cố ý set rỗng để chặn network), không phải nguyên nhân. Chẩn đoán ban đầu quy sai cho nó.

## Validation evidence

| Command | Result | Timestamp |
| --- | --- | --- |
| `pytest tests/ -q -p no:randomly` (sau toàn bộ thay đổi) | `3052 passed, 6 skipped` | 2026-09-02 |
| `ruff check src/ tests/` | `All checks passed` | 2026-09-02 |
| `pytest tests/ -q` trên worktree `origin/main` sạch (baseline) | `3047 passed, 1 failed` — fail có sẵn, không do đợt này | 2026-09-01 |
| `pytest tests/test_api/test_conversations.py` | `40 passed` | 2026-09-01 |
| `npx tsc -b --force` (client/web-app) | rc=0 | 2026-09-01 |
| `npm run lint` (client/web-app) | rc=0, chỉ warning `react(purity)` / `set-state-in-effect` | 2026-09-01 |
| `git diff --stat origin/main..main` mỗi lần merge | net effect khớp phạm vi; `--diff-filter=D` trống | 2026-09-01 |

Proof level / claim ceiling: **gate offline pass**. Không có bằng chứng production — đợt này không deploy, không lấy log/metric từ instance thật.

Tests not run and reason: `npm run build` và test frontend không chạy vì net effect của cả hai merge không chạm file frontend nào (`App.tsx` giữ nguyên bản `main`).

## Risk, rollback and follow-up

- Risk: lane `task_planning` chặn **trước** agent bằng regex. Cửa sổ `.{0,180}` khá rộng, nên câu vừa có mốc thời gian vừa có từ "làm gì/ưu tiên/kế hoạch" sẽ không bao giờ tới được tool-loop. Đã có test khoá contract, nhưng phạm vi regex nên được soát lại nếu người dùng báo mất tính năng gợi ý.
- Đã ghi nhận, chưa sửa: `conversations.py` gán cứng `groundingStatus: "grounded"` cả ở nhánh fallback `task_planning_unavailable`.
- Rollback: revert `7d539f9b` (lane) và/hoặc `1726da22` (diagram); không có mutation dữ liệu/config/migration.
- Follow-up: 10 nhánh cũ còn conflict và ~8.5 GB worktree rác chưa dọn; `agent/cohort-refresh-20260820` còn `program_schedule_templates.py`/`program_cohorts.py` chưa có trong `main`.

| Item | Value |
| --- | --- |
| Batch / date | `task-planning-diagrams` / `2026-09-01` |
| User-visible update | Câu hỏi kế hoạch trong ngày/tuần trả lời trực tiếp thay vì chạy tool-loop |
| Scope | Backend chat/conversation lane + docs diagram |
| Source | `d8ed068bcd373f94ecf879770bbd41a45783347c` |
| Validation | 3052 passed, 6 skipped; ruff pass; tsc/lint rc=0 |
| Status | Merged, not deployed |
| Rollback | revert `7d539f9b` / `1726da22` |
