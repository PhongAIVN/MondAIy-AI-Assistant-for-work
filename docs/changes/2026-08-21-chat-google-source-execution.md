# WHAT_CHANGED — Conversational source routing

| Field | Value |
|---|---|
| Objective | Router hiểu action và source xuyên suốt hội thoại, đọc được Google Sheets/Docs và không tự rơi sang Discord |
| Base SHA | `fcdc501` |
| Scope | Turn resolver, persisted routing state, source adapters, agent tool registry, authenticated scope, regression matrix |
| Ownership | Lead Codex/Tatejo; một writer |
| Status | Deployed to production VM; post-deploy health verified |

## Acceptance criteria

- Router resolve `action` độc lập với `source`: `READ`, `EXPLAIN`, `RETRY`, `SWITCH_SOURCE`, `ANSWER_FROM_CONTEXT`, `CLARIFY`.
- `EXPLAIN` giải thích kết quả/lỗi trước mà không gọi tool mới; `RETRY` chỉ gọi lại đúng source/resource trước.
- Cùng một contract áp cho Gmail, Google Sheets, Google Docs, Jira, Calendar và Discord.
- URL Google Sheets/Docs được route tới connector thật trong chat, kể cả khi model đoán Discord.
- Discord chỉ được auto-route khi người dùng nêu Discord/tin nhắn/kênh hoặc intent chương trình phù hợp; câu mới không kế thừa Discord cũ.
- Cụm định vị phân biệt source với topic, ví dụ “Jira trên Discord” và “task trong Google Sheets”.
- Google tools dùng user scope xác thực, connection/scopes/quota/cache/cap hiện có.

## Design

- Mỗi assistant turn lưu `extras.routing` gồm action, source, resource, status và lỗi an toàn cho người dùng.
- Turn mới ưu tiên source explicit hiện tại; follow-up mới dùng persisted result, chỉ fallback về lượt tương thích gần nhất cho hội thoại cũ.
- Nhiều source không xác định được referent thì hỏi lại, không chọn source mặc định.
- Intent ghi như tạo task/event giữ nguyên approval flow; source resolver không được biến nó thành read.

## Integration inventory

- Implementation commit: `60480c4241926e70768dd5b18b8f0859d9357680`; integrated as `d80862e`.
- `fix/tasks-calendar-test-clock-20260821`: its two commits are patch-equivalent to `origin/main`; no unique commit to harvest.
- `agent/cohort-refresh-20260820`: clean but contains a unique commit explicitly marked `wip(cohort)` on a stale foundation with broad divergence; deferred as not merge-ready, not silently integrated.
- Primary `p004-test-quality-hardening-20260821` lane was explicitly assigned by Thái, reviewed, validated and committed as `9acd3ac`; integrated as `67a05a9`.
- Clean-checkout gate exposed a missing test-only encryption key; fixed in `4eef2a8`. Full integration suite then passed.
- Generalization dossier: local-only `changes/2026-08-21/chat-google-routing-generalization.bugfix.json`, validator passed 4 cases across 2 dimensions.

## Deployment notification

| Item | Value |
|---|---|
| Batch / date | `chat-google-source-execution` / 2026-08-21 |
| User-visible update | Chat đọc đúng Google Sheet/Doc và không lạc sang Discord |
| Scope | backend; frontend chỉ deploy nếu diff yêu cầu |
| Source | `main` at deployed SHA `e233bbc7f49898b9d27ab220e335a9f66dc85d3c` |
| Validation | Full backend `1958 passed, 7 skipped`; Ruff passed; targeted integration `912 passed, 1 skipped` plus account deletion rerun `5 passed`; harness `12 cases / 6 sources / 6 actions`; bug-fix dossier passed; GitHub frontend build and secret scan passed |
| CI run | `32464983074`; backend full pytest was still running when post-deploy evidence was captured; equivalent clean-checkout full suite passed locally |
| Status | Deployed via `scripts/deploy_vm_local.sh`; backend/worker recreated successfully; backend container healthy; public `https://p004-api.duckdns.org/health` returned `{"status":"ok","env":"production"}`; startup logs clean |
| Rollback | `fcdc501` |
