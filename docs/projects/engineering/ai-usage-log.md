# AI Log — Personal Contextual Assistant

| Thuộc tính | Giá trị |
| --- | --- |
| Status | Active |
| Owner | Nguyễn Văn Phong (Technical Lead; acting AI/Memory owner) |
| Reviewers | PM, Tech Lead, QA Lead |
| Last updated | 2026-08-10 |
| Related | [PRD](../product/prd.md) · [Memory lifecycle](memory-lifecycle.md) · [Evaluation](../qa/evaluation-plan.md) |

## Mục đích

Ghi lại AI đã được dùng ở đâu trong discovery, documentation, coding, extraction, memory, retrieval và evaluation. Log phải giúp tái lập quyết định/kết quả mà không lưu secret hoặc raw personal context.

## Product decisions đã chốt

| Ngày | Quyết định | Rationale | Evidence |
| --- | --- | --- | --- |
| 2026-07-30 | Personal Contextual Assistant là product; Program Navigator là first vertical | Giữ reusable context/memory core nhưng dùng cohort làm bounded validation | [ADR-001](adr/adr-001-platform-core-program-navigator-vertical.md) |
| 2026-07-30 | Postgres là canonical memory/evidence | Cần provenance, temporal version, authority, audit và RLS | [Memory lifecycle](memory-lifecycle.md) |
| 2026-07-30 | Một tool-calling orchestrator cho P0 | Runtime agent swarm tăng latency/nondeterminism mà chưa tạo thêm user value | [Architecture](architecture.md) |
| 2026-07-30 | Hindsight/Vexa/Calendar OAuth sau adapter/feature flag | Tránh provider trở thành dependency chặn pilot | [PRD](../product/prd.md) |

## OSS/reference decisions

| Repository | Vai trò | Quyết định |
| --- | --- | --- |
| Pydantic AI | Python agent/tool calling | Direct dependency |
| Hindsight | Retain/recall/reflect benchmark | Optional `MemoryProvider`, không source of truth |
| Vexa | Meeting bot/transcription | Optional adapter; transcript import fallback |
| anarlog | Local transcript/import patterns | Reference/fallback |
| Supermemory | Browser content extraction/auth patterns | Selective reference theo MIT |
| NativeMind | Extension/local AI patterns | Reference only; AGPL review trước reuse |
| Google Calendar MCP | Calendar tool semantics | Reference; P0 dùng template/ICS |
| LongMemEval | Evaluation categories | Reuse concepts/scripts; golden set riêng |

## AI runtime guardrails

- Model chỉ nhận evidence pack đã permission-filter.
- Structured extraction/output dùng versioned schema.
- Factual block phải có citation IDs hoặc abstain.
- Citation validator chạy sau generation.
- Explicit profile thắng inferred memory.
- Model không tự promotion preference/identity.
- Không expose direct external-write tool ở P0.
- Prompt/model/embedder/retrieval/extractor versions lưu cùng result.
- Raw page/transcript/question không vào product analytics.

## Prompt/change record schema

Mỗi thay đổi prompt/model cần ghi:

```text
change_id
date
owner
component: extraction | memory | ask | brief | action
old_version
new_version
reason
golden_set_before
golden_set_after
cost_latency_delta
known_failures
rollback
```

## Coding-agent policy

- Coding agent làm task bounded với file ownership và verify command.
- Agent không tự thay product scope, schema hoặc retention.
- Agent không tạo cả fixture và ground truth mà không human review.
- Mọi generated code được review như code con người.
- Independent reviewer kiểm tra permission, provenance, idempotency và failure states.
- Không đưa transcript/browsing data thật vào prompt của coding agent.

## Log entry template

```md
### YYYY-MM-DD — Change title

- Owner:
- Component:
- Model/provider/version:
- Prompt/retrieval/extractor version:
- Input fixture:
- Output/decision:
- Evaluation:
- Cost/latency:
- Failure observed:
- Follow-up/rollback:
```

## Log entries

Mới nhất lên đầu.

### 2026-08-12 — Luồng task/sự kiện trùng nhau và chọn ưu tiên

- Owner: Thái Hoài An (PM) — dùng Claude Code (Opus 5) làm coding agent, review trực tiếp
- Component: `src/models/schedule_conflict.py` (mới),
  `src/services/schedule_conflicts.py` (mới), `src/api/schedule_conflicts.py`
  (mới), `src/models/schemas.py`, `src/api/tasks.py`, `src/main.py`;
  `client/web-app/src/components/calendar/ScheduleConflictPanel.tsx` (mới),
  `client/web-app/src/lib/scheduleConflictsApi.ts` (mới),
  `client/web-app/src/pages/TasksPage.tsx`, `i18n/translations.ts`
- Model/provider/version: Claude Opus 5 qua Claude Code CLI. Runtime KHÔNG
  thêm lời gọi LLM nào — phát hiện và gợi ý đều rule-based
- Prompt/retrieval/extractor version: không áp dụng. So tiêu đề dùng
  `difflib.SequenceMatcher` với đúng ngưỡng 0.72 của
  `src/agents/pipeline/nodes/cluster.py` để "trùng" nghĩa như nhau ở hai chỗ
- Input fixture: task và `calendar_events` synthetic dựng trong test; không có
  lịch hay email thật nào được commit
- Output/decision: hai kiểu trùng chung một bảng `schedule_conflicts` —
  `same_item` (cùng một việc, tinh thần FR-032) và `time_overlap` (hai việc
  khác nhau chiếm cùng khoảng giờ). Detect chỉ đọc bộ nhớ đệm
  `calendar_events`, không gọi Google, nên chạy được ngay trong
  `confirm_task`. `conflict_key` băm cả giờ hai bên: chạy lại không sinh bản
  trùng (FR-012), đổi giờ thì sinh phiên bản mới và dòng cũ chuyển
  `superseded` chứ không bị ghi đè (FR-032/FR-041). Gợi ý bằng chuỗi luật dựa
  trên thuộc tính task đã có (mức mơ hồ, trạng thái, số nguồn, số lần bỏ qua
  nhắc) và trả `undecided` khi không đủ căn cứ, không đoán bên nào hơn.
  Resolve không ghi gì lên Google và không tự dời hạn chót; riêng `same_item`
  mới đụng task (chọn sự kiện thì task trùng chuyển `dismissed` kèm
  `calendar_event_id`)
- Evaluation: 38 test mới — service 25, API 13, frontend 8. Backend suite
  793 passed / 1 skipped; frontend 63 passed; `ruff` sạch trên `src/` và
  `tests/`; `tsc --noEmit` sạch
- Cost/latency: không có chi phí LLM. Mỗi lần detect là hai truy vấn có index
  theo cửa sổ thời gian rồi ghép cặp trong bộ nhớ; cửa sổ bị chặn ở 42 ngày
  như hai endpoint lịch còn lại, `detect_for_task` chỉ quét ±1 ngày
- Failure observed: không có lỗi ngầm nào phát hiện thêm trong lần này
- Follow-up/rollback: rollback = gỡ router `schedule_conflicts` khỏi
  `src/main.py`, bỏ lời gọi `detect_for_task` trong `confirm_task` và bỏ panel
  khỏi `TasksPage`; bảng mới không có ai tham chiếu tới. Còn treo: (1) kiểu
  `time_overlap` và thao tác chọn ưu tiên CHƯA có FR trong PRD — đã ghi
  `TODO(PRD)` trong docstring service, cần PM chốt trước khi coi là phạm vi đã
  duyệt; (2) chưa đối chiếu sự kiện với sự kiện, chỉ task với sự kiện; (3) chưa
  có hạn lưu trữ cho dòng `resolved`

### 2026-08-12 — Luồng nhắc việc end-to-end (ADR-007 mục 4/5/8/9)

- Owner: Nguyễn Văn Phong (Technical Lead) — dùng Claude Code (Sonnet 5) làm coding agent, review trực tiếp
- Component: `src/models/reminder.py`, `src/models/notification_preference.py`
  (mới), `src/models/task.py`, `src/services/reminders.py` (mới),
  `src/api/reminders.py` (mới), `src/api/tasks.py`, `src/main.py`, `src/db.py`,
  `src/models/schemas.py`; phía extension: `entrypoints/background.ts`,
  `lib/api.ts`, `lib/storage.ts`, `types/index.ts`
- Model/provider/version: Claude Sonnet 5 qua Claude Code CLI. Không chạm
  LLM runtime nào — toàn bộ logic rule-based, không có prompt/extractor
- Prompt/retrieval/extractor version: không áp dụng
- Input fixture: task/reminder synthetic dựng trong test (due_at, evidence,
  preference giờ yên lặng); không dùng dữ liệu thật
- Output/decision: theo đúng ADR-007. Sinh mốc nhắc mặc định (-1 ngày, -30
  phút) lúc `confirm_task`; endpoint đọc nhẹ `GET /reminders/due` gộp lời nhắc
  cùng khung giờ, áp trần thông báo/giờ và giờ yên lặng trước khi trả về;
  `POST /reminders/deliveries` ghi nhận đã giao (idempotent theo
  `reminder_id`, unique constraint) để service worker MV3 khởi động lại không
  giao trùng; `snooze` xoá delivery cũ để giao lại được, `dismiss` chỉ đổi
  `reminder.status`, không đụng `task.status` (tách theo bảng mục 4 của ADR).
  Thêm `POST /tasks/{id}/complete` và `/cancel` vì trước đó chỉ có
  confirm/dismiss, không có đường nào tới "đã làm"/"hủy việc" mà ADR yêu cầu.
  Extension dùng `chrome.alarms` polling `/reminders/due` mỗi 5 phút, tự tạo
  OS notification kèm 2 nút (Nhắc lại/Bỏ qua), map notification id -> bundle
  qua `local storage` để bấm nút vẫn đúng dù service worker chết giữa chừng —
  đúng cơ chế ADR-007 mục 9 chọn, không dựng push server phía backend
- Evaluation: 24 test mới (14 trong `tests/test_services/test_reminders.py`
  cho logic thuần — sinh mốc, giờ yên lặng, ưu tiên theo luật, gộp/trần/snooze/
  dismiss; 10 trong `tests/test_api/test_reminders.py` cho endpoint + hook
  confirm/complete/cancel). Toàn bộ backend: 717 passed, 6 skipped. `ruff
  check` sạch trên mọi file đã sửa. Extension: `tsc --noEmit` sạch
- Cost/latency: không gọi LLM. `GET /reminders/due` mỗi lần gọi tối đa quét
  N reminder `scheduled` của 1 user (không có cap cứng số dòng — chấp nhận
  được ở quy mô pilot 5-10 người/~15 việc mỗi tuần nêu trong ADR, cần thêm
  LIMIT nếu dữ liệu lớn hơn)
- Failure observed: không phát hiện khi review — đây là lần triển khai đầu,
  chưa có dữ liệu production để đối chiếu
- Follow-up/rollback: rollback = không đăng ký `reminders_router` trong
  `src/main.py` (bảng mới không ảnh hưởng route cũ), extension revert
  `background.ts` về bản chỉ poll task count. Còn thiếu so với PRD §8.9: (1)
  UI web app cho "Đã làm"/"Hủy việc" và sửa/tắt từng mốc nhắc (FR-090 phần
  edit) chưa làm — mới có endpoint; (2) nút Bỏ qua nhanh trên OS notification
  mặc định lý do `khong_can_nua`, chưa cho chọn 1 trong 3 lý do FR-096 ngay
  tại chỗ, phải vào web app mới chọn đủ; (3) `ADR-007` đang `In review`, chưa
  `Accepted` — code này bám theo bản đang review, cần đối chiếu lại nếu ADR
  đổi khi duyệt chính thức

### 2026-08-12 — Auto-sync nền và nới trần nguồn mỗi lần Sync

- Owner: Thái Hoài An (PM) — dùng Claude Code làm coding agent, review và deploy
- Component: `src/services/auto_sync.py` (mới), `src/worker.py`, `src/api/runs.py`,
  `src/config.py`, `src/models/user.py`, `src/db.py`, SourcePicker và
  `usePipelineRunStore` phía FE
- Model/provider/version: Claude Code (Opus 5)
- Prompt/retrieval/extractor version: không đổi. Thay đổi nằm ở lớp lập lịch và
  hạn mức, không chạm prompt hay extractor nào
- Input fixture: user synthetic có run thành công/lỗi/đang chạy ở nhiều mốc thời
  gian; không dùng dữ liệu thật
- Output/decision: xem [ADR-011](adr/adr-011-tu-dong-dong-bo-nen-va-han-muc-nguon.md).
  Ba điểm chốt: (1) run tự động sao chép nguyên văn bộ nguồn của run **thành
  công** gần nhất, không bao giờ tự chọn nguồn mới — nhờ vậy vẫn nằm trong phạm
  vi ADR-002; (2) hai công tắc, công tắc tổng `AUTO_SYNC_ENABLED` mặc định
  `false`; (3) `max_sync_sources` 3 → 10 kèm điều kiện bắt buộc là FE đọc trần
  qua `GET /runs/limits` và khoá ô tick, vì nới trần mà không hiện ra thì chỉ
  dời chỗ người dùng ăn 422. `max_concurrent_runs` 3 → 10 vì nó đếm toàn hệ
  thống chứ không theo user
- Evaluation: 24 test mới (16 trong `tests/test_services/test_auto_sync.py`,
  4 trong `tests/test_api/test_runs.py`, 8 trong hai file FE
  `SourcePickerLimit.test.tsx` và `PipelineSourceLimit.test.tsx`). Backend:
  665 passed, 2 failed, 1 skipped — hai failure vẫn là lỗi `tasks.cluster_key`
  varchar(64) có sẵn từ trước, không liên quan. FE: 50 passed, `tsc -b` sạch,
  `oxlint` chỉ còn 4 warning có sẵn. `ruff check src/ tests/` sạch
- Cost/latency: bật auto-sync ở nhịp 180 phút là tối đa 8 run/user/ngày. Chi phí
  LLM mỗi run không đổi, vẫn bị `max_total_llm_batches_per_run` chặn
- Failure observed: (1) test auto-sync ban đầu để lại dòng `queued` trong DB dev
  dùng chung, cộng dồn vào trần `max_concurrent_runs` toàn cục và làm cả
  `test_runs.py` ăn 429 — đã thêm teardown xoá đúng phần mình sinh ra. (2) trần
  per-tick ban đầu nằm trong `find_due_users()` khiến "ai tới hạn" và "xử bao
  nhiêu người mỗi vòng" không kiểm chứng riêng được — đã tách sang
  `enqueue_due_auto_syncs()`
- Follow-up/rollback: rollback = `AUTO_SYNC_ENABLED=false`, vòng quét thoát ngay
  lúc khởi động, không schema nào phải hoàn tác. Còn treo: ADR-011 mới ở trạng
  thái `Proposed`, **chưa được bật ở production**; mặc định của công tắc cá nhân
  `users.auto_sync_enabled` là quyết định của PM, bản này tạm để `true`

### 2026-08-10 — Hoàn thiện Google Calendar read/agent/handoff end-to-end

- Owner: Thái Hoài An (PM) — dùng Codex làm coding agent, review và deploy
- Component: connector registry, pipeline fetch, agent tools/scope, Calendar
  handoff API client, source picker và tài liệu contract
- Model/provider/version: Codex (GPT-5 family)
- Prompt/retrieval/extractor version: prompt agent trong
  `src/agents/nodes/example_node.py`; không đổi extractor task
- Input fixture: Google connection dùng chung Gmail/Calendar; Calendar event có
  giờ, all-day event, token cũ thiếu `calendar.readonly`, task proposed/confirmed
  và tiêu đề `.ics` UTF-8 dài
- Output/decision: source Calendar có namespace `calendar:*`, Gmail giữ ID cũ
  để rollout tương thích; agent bind `calendar_search_events` theo user scope
  và cửa sổ hữu hạn; FE gọi ba endpoint task-scoped thật, tải `.ics` có Bearer
  token và ghi `opened`; không expose Calendar write tool
- Evaluation: targeted backend 51 passed, 1 skipped; full backend 327 passed,
  1 skipped; frontend 18 passed; TypeScript/Vite build pass; Ruff toàn
  `src/ tests/` pass. Production smoke test được ghi bổ sung sau deploy
- Cost/latency: mỗi source Calendar thêm một API list/fetch có phân trang; agent
  context bị chặn tối đa 30 event và query mặc định tối đa 30 ngày
- Failure observed: provider `google` trước đây map cứng sang Gmail; Calendar
  normalize trả chuỗi vào cột `DateTime`; FE gọi route không tồn tại rồi fallback
  local; `.ics` backend chưa fold dòng UTF-8; tool scope cũ chỉ reset search scope
- Follow-up/rollback: rollback commit Calendar nếu Google source listing gây
  regression; source Gmail không prefix vẫn hoạt động để hỗ trợ rollback mềm.
  P0 vẫn chưa tính schedule conflict và vẫn không ghi event trực tiếp

### 2026-08-10 — Chặn .env.local lọt vào bundle production

- Owner: Thái Hoài An (PM) — chạy Claude Code (Opus 5) làm coding agent
- Component: build/deploy config của `client/web-app` (không chạm prompt, model,
  memory hay retrieval)
- Model/provider/version: Claude Opus 5 qua Claude Code CLI
- Prompt/retrieval/extractor version: không áp dụng
- Input fixture: không dùng fixture. Bằng chứng lấy từ chính artifact build dưới
  máy — `dist/assets/index-ic76jJRx.js` và `.vercel/output/static/assets/` cùng
  hash, `.vercel/output/builds.json` ghi `argv: ["vc","build","--prod"]`
- Output/decision: thêm `client/web-app/.env.production` khai `VITE_API_URL=`
  rỗng, mở ngoại lệ `!.env.production` trong `client/web-app/.gitignore`, thêm
  `tests/test_frontend_env_production.py`
- Evaluation: build lại khi `.env.local` vẫn trỏ `127.0.0.1:8001` → bundle mới
  không còn chuỗi `127.0.0.1`, `API_BASE_URL` inline thành rỗng. Sau deploy,
  bundle live không có `127.0.0.1`, `/health` trả 200, `/api/v1/conversations`
  trả 401 đúng nghiệp vụ từ backend. pytest 3 passed, ruff sạch
- Cost/latency: không đổi runtime cost. Bundle không đổi kích thước đáng kể
- Failure observed: bản deploy 2026-08-09 gọi `http://127.0.0.1:8001` do Vite nạp
  `.env.local` ở mọi mode, kể cả `vc build --prod` chạy dưới máy. Vercel không
  cứu được vì project không khai `VITE_API_URL` (cố ý, để same-origin), nên
  không có biến `process.env` nào đè lên file
- Follow-up/rollback: rollback = xoá `.env.production` rồi build lại. Cách chặn
  triệt để hơn là chuyển deploy sang git integration của Vercel để không ai build
  dưới máy nữa — chưa quyết, thuộc Tech Lead

### 2026-08-11 — Dựng lớp long-term memory và short-term memory cho agent

- Owner: Thái Hoài An (PM) — chạy Claude Code (Opus 5) làm coding agent
- Component: `src/services/memory_store.py`, `memory_capture.py`,
  `working_memory.py`, `src/models/user_memory.py`, `src/api/memory.py`,
  `src/api/conversations.py`, `src/agents/state.py`,
  `src/agents/nodes/example_node.py` (có chạm prompt, memory và retrieval)
- Model/provider/version: Claude Opus 5 qua Claude Code CLI. Runtime dùng lane
  `small_talk` cho bước nén tóm tắt hội thoại
- Prompt/retrieval/extractor version: `EXTRACTOR_VERSION = "memory-store-1"`.
  Thêm hai khối prompt `<conversation_summary>` và `<long_term_memory>` vào cả
  `_ANALYZE_PROMPT` lẫn `_RESPOND_PROMPT`
- Input fixture: không dùng dữ liệu thật. Test dựng user và hội thoại synthetic
  trên sqlite in-memory
- Output/decision: bảng `user_memories` + `user_memory_evidence` theo
  memory-lifecycle §4; state machine §3; luật thăng cấp §5; versioning và
  disputed theo §6; công thức xếp hạng §7; decay và quyền xoá §9. Bộ nhớ ngắn
  hạn thành tóm tắt cuộn trên `conversations.summary` cộng cửa sổ nguyên văn cắt
  theo ngân sách ký tự, thay cho hằng số 8 lượt cũ
- Evaluation: 39 test mới (`test_memory_store.py` 21, `test_working_memory.py`
  10, `test_memory_capture.py` 8) cộng 9 test API trong
  `test_api/test_memory_long_term.py`. Toàn bộ suite 458 passed, 1 skipped, 1
  failed — lỗi còn lại là `test_llm_failover` có sẵn từ thay đổi dở dang trong
  `src/services/llm.py`, không liên quan tới memory. ruff sạch
- Cost/latency: thêm một lời gọi model mỗi ~4 lượt cho bước nén, chạy nền sau
  khi đã trả lời nên không cộng vào độ trễ câu trả lời. Truy hồi memory là truy
  vấn SQL cộng chấm điểm trong tiến trình, không gọi mạng
- Failure observed: bản đầu của `recall` loại trạng thái `superseded` khỏi truy
  vấn nên câu hỏi về quá khứ mất phiên bản đúng của quá khứ; và khớp từ khoá
  thuần khiến "dự án tới đâu rồi" không khớp `working_on`. Đã sửa bằng cách đưa
  `superseded` vào truy vấn rồi lọc theo khoảng hiệu lực, và thêm nhãn kind
  tiếng Việt cộng sàn `BASELINE_RELEVANCE`
- Follow-up/rollback: chưa cắm pgvector cho lớp memory vì kho vector còn là
  quyết định mở — độ liên quan hiện chỉ là khớp từ khoá có sàn. Ba thừa số
  `status`/`reinforcement`/`negative_feedback` trong `src/services/retrieval.py`
  vẫn hardcode 1.0 vì chúng chấm điểm chunk bằng chứng chứ không chấm memory.
  Rollback = gỡ hai bảng mới và trả `conversations.py` về đọc 8 lượt gần nhất

### 2026-08-11 — Truy hồi memory dài hạn bằng pgvector, hợp nhất RRF (ADR-006)

- Owner: Thái Hoài An (PM) — chạy Claude Code (Opus 5) làm coding agent
- Component: `src/services/memory_store.py`, `src/models/user_memory.py`,
  `src/api/conversations.py`, `src/config.py`, ADR-006 (có chạm retrieval và
  vòng đời memory, không chạm prompt)
- Model/provider/version: Claude Opus 5 qua Claude Code CLI. Runtime nhúng bằng
  `EMBEDDING_MODEL` hiện hành, dùng chung `embed_query` với truy hồi chunk
- Prompt/retrieval/extractor version: `EXTRACTOR_VERSION = "memory-store-1"`
  không đổi. Truy hồi đổi từ khớp từ khoá thuần sang lai: `RRF_K = 60`,
  `VECTOR_CANDIDATE_LIMIT = 50`, điểm RRF chuẩn hoá thay chỗ thừa số
  `relevance` của memory-lifecycle §7
- Input fixture: không dùng dữ liệu thật. Test nhánh vector dựng vector 2048
  chiều trực giao trong một database PostgreSQL tạm
- Output/decision: ADR-006 chốt pgvector thay vì Chroma, đặt vector trên chính
  `user_memories` để hợp đồng xoá không phát sinh bước thứ hai; nhánh từ khoá
  chấm điểm trong tiến trình, không dựng FTS cho memory; nhúng chạy nền sau khi
  trả lời, nhúng câu hỏi chạy ngoài event loop qua `arecall`; cờ
  `MEMORY_SEMANTIC_RECALL_ENABLED` là đường rollback
- Evaluation: 17 test mới trong `test_memory_semantic_recall.py`, gồm 5 test
  chạy thật trên PostgreSQL + pgvector (tự bỏ qua khi không có DB). Toàn bộ
  suite 489 passed, 1 skipped. ruff sạch trên `src/`
- Cost/latency: thêm một lời gọi nhúng cho mỗi lượt hỏi, trần theo
  `EMBEDDING_TIMEOUT_SECONDS`; nhúng ghi chạy nền tối đa
  `MEMORY_EMBEDDING_BATCH_LIMIT` dòng mỗi lượt
- Failure observed: bản đầu của test cách ly bằng schema PostgreSQL. `search_path`
  buộc phải thấy `public` để giải kiểu `vector`, nên `create_all` coi bảng đã tồn
  tại và test ghi thẳng vào DB dev `ai20k` — 22 dòng `user_memories` cùng một tài
  khoản `pg-owner@example.com`. Đã đổi sang tạo database riêng cho test và đã xoá
  sạch phần ghi nhầm; toàn bộ 22 dòng đều thuộc tài khoản `@example.com`, không
  có dữ liệu người dùng thật
- Follow-up/rollback: rollback = đặt `MEMORY_SEMANTIC_RECALL_ENABLED=false`, cột
  `embedding` giữ nguyên. Chưa đo p95 của bước nhúng trên staging và chưa có
  index ANN cho `user_memories.embedding` — với vài trăm dòng mỗi user thì quét
  tuần tự vẫn rẻ hơn, nhưng phải đo lại trước khi kho memory lớn lên

### 2026-08-12 — Cào tiếp Discord theo con trỏ và lọc thông báo cho học viên mức A

- Owner: Thái Hoài An (PM) — chạy Claude Code (Opus 5) làm coding agent
- Component: `scripts/discord/export_dce.py`, `scripts/discord/sync.py` (mới),
  `src/services/discord_announcements.py` (mới), `src/agents/tools/example_tool.py`,
  `src/agents/nodes/example_node.py`, `src/services/intent_router.py`,
  `src/services/program_access.py`, `scripts/discord/load_to_db.py`
- Model/provider/version: Claude Opus 5 qua Claude Code CLI. Không thêm lời gọi
  LLM nào vào runtime — bộ lọc thông báo chấm điểm bằng luật tường minh
- Prompt/retrieval/extractor version: prompt của `_ANALYZE_PROMPT` thêm một câu
  định tuyến sang `discord_list_announcements`. Ngưỡng lọc `MIN_SCORE = 5`,
  tín hiệu mạnh (kênh thông báo, `@everyone`) tự nó đủ vượt ngưỡng
- Input fixture: test dùng dữ liệu synthetic. Có chạy đối chiếu tay trên kho đã
  cào thật (615 scope, 20.925 item) để dò lỗi phân loại, không commit dữ liệu đó
- Output/decision: nguồn dữ liệu không đổi nên không cần ADR mới — Discord đã
  nằm trong ADR-002. Thông báo suy ra lúc truy vấn từ `source_items`, không dựng
  bảng mới và không đổi schema; đọc `source_items` thay vì `chunks` vì chunker
  cố ý bỏ tin bot và tin ngắn, mà thông báo hay là cả hai. Role người gửi chỉ là
  tín hiệu cộng điểm, không phải thẩm quyền (BR-04)
- Evaluation: 24 test mới (`test_discord_announcements.py`,
  `test_announcement_tool.py`, `test_discord_sync.py`, 2 test hồi quy trong
  `test_program_access.py`). Toàn bộ suite 607 passed, 2 failed, 1 skipped —
  hai failure có sẵn từ trước, do `tasks.cluster_key` ở DB dev là varchar(64).
  ruff sạch trên `src/` và `tests/`
- Cost/latency: không thêm chi phí LLM. Bộ lọc chạy một truy vấn SQL có trần
  `CANDIDATE_CAP = 400` rồi chấm điểm trong tiến trình
- Failure observed: (1) `--incremental` cũ chỉ đọc manifest run gần nhất nên kênh
  không có tin mới bị mất con trỏ và cào lại từ đầu — đã sửa thành gộp qua mọi
  run. (2) Bot đăng embed làm `content` rỗng, thông báo rỗng lọt vào danh sách —
  phát hiện khi đối chiếu dữ liệu thật, đã thêm ngưỡng `MIN_SUBSTANCE_CHARS`.
  (3) `reconcile_program_access` gọi `int(user_id)` nên một dòng connection rác
  làm chết cả bước cuối của nạp crawl và cả lúc khởi động backend — đã sửa để bỏ
  qua từng dòng. (4) Lần cào thật chỉ xong 1/19 kênh: token user hết hiệu lực
  giữa chừng, sau đó tài khoản bị Discord khóa. Chỉ nạp được 199 tin của run
  `20260812T021048Z`
- Follow-up/rollback: rollback = gỡ `discord_list_announcements` khỏi `_BASE_TOOLS`,
  không có schema nào phải hoàn tác. Còn treo: cào lại phần Discord còn thiếu khi
  có đường truy cập hợp lệ, và dọn dòng test trong DB dev (116 scope, 72 item,
  1216 grant) đang lấn át thông báo thật khi demo

### 2026-08-12 — Meeting note: người dùng tự ghi, AI trích việc cần làm

- Owner: Thái Hoài An (PM) — chạy Claude Code (Opus 5) làm coding agent
- Component: `src/models/meeting_note.py` (mới), `src/services/meeting_notes.py`
  (mới), `src/api/meeting_notes.py` (mới), `src/models/schemas.py`,
  `src/services/llm.py`, `src/main.py`,
  `client/web-app/src/pages/MeetingNotesPage.tsx` (mới),
  `client/web-app/src/pages/MeetingNoteDetailPage.tsx` (mới),
  `client/web-app/src/lib/meetingNotesApi.ts` (mới), `App.tsx`, `Sidebar.tsx`,
  `i18n/translations.ts`
- Model/provider/version: Claude Opus 5 qua Claude Code CLI. Runtime thêm đúng
  một lời gọi LLM cho mỗi lần bấm kết thúc cuộc họp, đi qua `get_llm(lane=
  "work_response")` — không thêm provider mới
- Prompt/retrieval/extractor version: `_SYSTEM_PROMPT` trong
  `src/services/meeting_notes.py`, schema `MeetingExtraction`. Nội dung cuộc họp
  vào prompt qua `sanitize_untrusted_text` + `evidence_block`, cùng đường mà
  `extract_batch` đang dùng cho email/tin nhắn
- Input fixture: toàn bộ test dùng câu synthetic viết tay, không có transcript
  thật nào được commit
- Output/decision: KHÔNG phải nguồn dữ liệu mới theo ADR-002 — nội dung do chính
  người dùng gõ hoặc dán vào, không có connector nào đi lấy về, nên không mở ADR
  mới. Hai bảng mới `meeting_notes` và `meeting_action_items`; action item là
  bản nháp riêng, chỉ sinh `Task` khi người dùng bấm chấp nhận, và Task sinh ra ở
  trạng thái `proposed` để vẫn đi qua đúng vòng xác nhận cũ (FR-062). Thời gian
  chỉ được chốt qua `resolve_due_at`, mơ hồ thì để trống chứ không đoán (BR-05)
- Evaluation: 26 test mới: API meeting notes 14, service meeting notes 7,
  structured failover 2 và frontend 3. Toàn bộ backend suite 745 passed,
  1 skipped; frontend 95 passed. `ruff` sạch trên `src/` và `tests/`; lint
  không có lỗi và `npm run build` xanh
- Cost/latency: một lời gọi LLM cho mỗi cuộc họp kết thúc. Đầu vào bị cắt ở
  `_MAX_PROMPT_CHARS = 24_000` cho mỗi phần ghi chú/transcript để một transcript
  dài bất thường không thổi bay cửa sổ ngữ cảnh
- Failure observed: `FailoverChatModel` và `RotatingChatModel` chưa có
  `with_structured_output`, nên `src/agents/pipeline/nodes/extract_batch.py:115`
  đang hỏng ngầm trong mọi cấu hình có `LLM_PROVIDERS=openrouter,groq` — lỗi bị
  nuốt vào danh sách `errors` của run nên không ai thấy. Đã bổ sung method này
  cho cả hai lớp kèm test, extract_batch được sửa gián tiếp
- Follow-up/rollback: rollback = gỡ router `meeting_notes` khỏi `src/main.py` và
  bỏ hai route frontend; hai bảng mới không có ai tham chiếu tới nên để lại cũng
  vô hại. Còn treo: (1) chạy lại tổng hợp cho một cuộc họp đã kết thúc hiện bị
  chặn bằng 409 vì chưa chốt số phận của action item người dùng đã xử lý;
  (2) chưa có hạn lưu trữ cho `meeting_notes` — cùng khoảng trống với OD-02 của
  lịch sử hội thoại

### 2026-08-12 — Thu audio cuộc họp qua extension và chuyển thành transcript có gán speaker

- Owner: Thái Hoài An (PM, quyết định phạm vi) · code do coding agent viết
- Component: `client/extension` (offscreen tabCapture + getUserMedia),
  `src/services/stt.py`, `POST /api/v1/meeting-notes/{id}/audio-chunk`,
  `src/services/meeting_notes.py` (glossary ASR), `MeetingNoteDetailPage`
- Model/provider/version: `whisper-large-v3-turbo` qua FPT marketplace
  (`https://mkp-api.fptcloud.com/v1/audio/transcriptions`), OpenAI-compatible
- Prompt/retrieval/extractor version: `_SYSTEM_PROMPT` của `summarize_meeting`
  thêm khối `_ASR_GLOSSARY`; các luật cũ giữ nguyên
- Input fixture: audio tổng hợp bằng `say -v Linh` (macOS TTS tiếng Việt), câu
  có code-switching Việt–Anh. Không dùng dữ liệu cuộc họp thật
- Output/decision: extension ghi hai kênh riêng (mic, tab audio), cắt chunk 20s
  bằng cách restart `MediaRecorder`, upload từng chunk ngay. Speaker suy ra từ
  kênh chứ không từ diarization; timestamp lấy từ đồng hồ client vì API không
  trả timestamp
- Evaluation: backend `816 passed, 1 skipped`; extension `11/11`; web-app
  `68/68`; ruff và tsc sạch. Đã gọi API thật để kiểm chuỗi
  `transcribe_chunk` → `build_turns` → `turns_to_transcript`
- Cost/latency: ~43x realtime (60s audio → 1.4s). Tính theo `input_duration`,
  ước tính ~$0.0008/giờ audio
- Failure observed: (1) API bỏ qua `response_format`, `timestamp_granularities`,
  `stream` và `prompt` — luôn trả `{text, usage}` phẳng, nên kế hoạch lấy
  timestamp từ API bị bỏ, chuyển sang cắt chunk phía client; (2) **không gửi
  `language` thì model tự dịch tiếng Việt sang tiếng Anh với đầu vào webm/opus**
  — đã ghim `STT_LANGUAGE=vi`; (3) WER thuật ngữ rất cao trên fixture tổng hợp:
  `deploy`→"ê tôi", `endpoint`→"nơ tuên", `schema`→"sơ hé má", tên `An`→"ăn".
  Xử lý bằng glossary trong prompt tóm tắt, KHÔNG sửa transcript gốc để
  `evidence_quote` còn đối chiếu được
- Follow-up/rollback: rollback = gỡ endpoint `audio-chunk`, bỏ `tabCapture`/
  `offscreen` khỏi `wxt.config.ts`, xoá `_ASR_GLOSSARY`. Còn treo: (1) tính năng
  này vượt ADR-002 §2 và §3 (không thu nội dung cuộc họp, extension không tự
  thu thập nội dung trang) — admin dự án quyết định bỏ qua để demo nội bộ, cần
  ADR mới trước khi đưa vào pilot; (2) chưa đo WER trên giọng người thật, con số
  hiện có đến từ TTS tổng hợp nên bi quan hơn thực tế; (3) chưa có hạn lưu trữ
  cho transcript, cùng khoảng trống với `meeting_notes`; (4) `STT_API_KEY` dùng
  cho demo đã bị lộ dạng plaintext, phải rotate sau demo

### 2026-08-13 — Hạn mức ghi âm 15 phút/ngày cho tài khoản thường

- Owner: Thái Hoài An (PM) · code do coding agent viết
- Component: `src/models/recording_quota.py`, `src/services/recording_quota.py`,
  `GET /api/v1/meeting-notes/recording-quota`, chặn 429 trong `audio-chunk`,
  popup extension đếm ngược và tự dừng khi hết
- Model/provider/version: không dùng LLM, thuần logic
- Prompt/retrieval/extractor version: không đổi
- Input fixture: test tổng hợp, không có dữ liệu thật
- Output/decision: hạn mức đo bằng **thời gian họp thật** chứ không phải tổng
  thời lượng audio — mic và tab gửi cùng `offset_ms` nên khoá duy nhất
  `(user_id, note_id, offset_ms)` chống tính đôi và chống cả chunk gửi lại sau
  lỗi mạng. Mốc ngày theo `Asia/Ho_Chi_Minh`, không phải UTC. Quản trị viên
  (`User.is_admin`) miễn trừ và không sinh dòng nào trong bảng
- Evaluation: backend `884 passed, 1 skipped`; extension `19/19`; ruff và tsc
  sạch; `pnpm build` thành công
- Cost/latency: giảm chi phí STT — hạn mức kiểm TRƯỚC khi gọi provider nên
  audio vượt hạn mức không tốn tiền
- Failure observed: (1) route `/recording-quota` phải khai báo trước
  `/{note_id}` nếu không FastAPI ép sang int rồi trả 422 — đã có test khoá lại;
  (2) chunk im lặng vẫn phải trừ hạn mức, nếu không nhánh `appended=False` thoát
  ra mà chưa commit sẽ cuốn ngược cả lát vừa ghi
- Follow-up/rollback: rollback = bỏ hai lệnh gọi `consume_slot`/`get_status`
  trong endpoint, bảng `recording_quota_slots` để lại vô hại. Còn treo: (1) chưa
  có màn admin để chỉnh hạn mức từng người, hiện chỉ có biến môi trường dùng
  chung; (2) chưa dọn dòng hạn mức cũ, cần chốt hạn lưu trữ cùng lúc với
  `meeting_notes`

### 2026-08-14 — Danh sách cuộc họp có ngày giờ và thời lượng, tên do LLM đặt, tự dừng khi phòng họp trống

- Owner: Thái Hoài An (PM) · code do coding agent viết
- Component: `POST /api/v1/meeting-notes/{id}/end` (đặt tên theo tóm tắt),
  `finalize-recording` (ghi `ended_at`), `src/services/meeting_notes.py`
  (`suggest_meeting_title(..., summary=)`), `client/web-app/src/lib/meetingDisplay.ts`,
  `MeetingNotesPage`/`MeetingNoteDetailPage`, `client/extension/lib/recording.ts`
  (`decideIdleAction`), alarm khoảng lặng trong `entrypoints/background.ts`
- Model/provider/version: lane `work_response` (như phần tóm tắt cuộc họp), không
  đổi provider
- Prompt/retrieval/extractor version: `_TITLE_SYSTEM_PROMPT` không đổi; chỉ đổi
  **nguồn evidence** đưa vào prompt đặt tên — có tóm tắt thì dùng tóm tắt thay
  cho transcript thô
- Input fixture: test tổng hợp, không có dữ liệu thật
- Output/decision: (1) tên cuộc họp đặt theo bản tóm tắt vì transcript thô đầy
  tiếng chào hỏi và lỗi phiên âm nên model hay bắt nhầm chủ đề mấy phút đầu;
  (2) `ended_at` ghi ngay lúc dừng ghi âm chứ không đợi bấm tổng hợp, nếu không
  thời lượng bị thổi phồng bằng khoảng cách tới lúc người dùng mở lại;
  (3) khoảng lặng đếm bằng cờ `appended` của endpoint audio-chunk — chunk chỉ có
  tiếng ồn KHÔNG được coi là tín hiệu, nếu không phòng họp trống có tiếng quạt
  vẫn giữ máy ghi chạy; (4) im lặng 10 phút thì hỏi, không trả lời sau 1 phút
  thì tự dừng qua đúng luồng dừng thủ công nên không mất phần đã ghi
- Evaluation: backend `pytest tests/test_api/test_meeting_notes*.py
  tests/test_services/test_meeting_notes.py` → 56 passed; extension `vitest` 41
  passed + `tsc` sạch; web app `tsc` sạch, `node --test tests/meetingDisplay.test.ts`
  11 passed, `vitest tests/MeetingNote*` 10 passed
- Cost/latency: thêm tối đa một lượt LLM ngắn cho mỗi cuộc họp được tổng hợp
  (chỉ khi người dùng chưa tự đặt tên); cơ chế tự dừng làm giảm chi phí STT của
  những phiên bị bỏ quên
- Failure observed: mock `uploadAudioChunk` trong test offscreen trả `undefined`
  nên destructuring ném TypeError sau khi API đổi kiểu trả về — đã sửa mock theo
  đúng hình dạng thật
- Follow-up/rollback: rollback = bỏ alarm `mondaiy-recording-idle` và lời gọi
  `suggest_meeting_title` trong `/end`, phần còn lại vô hại. Còn treo: (1) ngưỡng
  10 phút và 1 phút đang hardcode, chưa cho người dùng chỉnh; (2) cuộc họp
  "dừng giữa chừng" mới chỉ được suy đoán ở client theo `updated_at`, chưa có
  job phía server dọn các phiên treo

### 2026-08-14 — Hoàn thiện luồng nhắc việc trên ba kênh: extension, Telegram, PWA

- Owner: Thái Hoài An (PM) · code do coding agent viết
- Component: `src/models/schemas.py` (`ReminderKind`, preference request/response),
  `src/models/notification_preference.py` + `src/db.py` (cột kênh và `muted_kinds`),
  `src/services/reminders.py` (`is_channel_enabled`, lọc `muted_kinds`,
  `snooze_reminder` dọn receipt mọi kênh), `src/services/telegram_channel.py`
  (`reminder_keyboard`, `reminder_ids_for_message`, `apply_reminder_action`),
  `src/api/telegram_channel.py` (callback `rm:*`), `src/api/reminders.py`,
  `client/web-app/src/sw.ts` + `src/lib/pushNotification.ts` + `pwa.config.ts`,
  `client/web-app/src/components/settings/NotificationPreferencesPanel.tsx`
- Model/provider/version: không dùng LLM — toàn bộ là luật và hạ tầng giao tin
- Prompt/retrieval/extractor version: không đổi
- Input fixture: test tổng hợp, không có dữ liệu thật
- Output/decision: (1) `ReminderKind` thiếu `calendar_changed` khiến CẢ
  `/reminders` lẫn `/reminders/due` hỏng validate với user đang có thông báo lịch
  đổi — mất luôn mọi lời nhắc khác, không riêng dòng đó; (2) tuỳ chọn kênh và
  tắt theo loại đặt ở `get_due_notifications()` vì đó là cửa duy nhất cả ba kênh
  đi qua, tắt một chỗ là tắt thật; (3) `snooze_reminder` trước đây chỉ xoá
  receipt của extension nên nhắc lại từ Telegram/PWA dời lịch xong mà không kênh
  nào giao lại; (4) service worker do Workbox sinh không có handler `push`, nên
  toàn bộ kênh Web Push chỉ hiện được thông báo mặc định của trình duyệt — đổi
  sang `injectManifest` với service worker viết tay; (5) tab Thông báo trong
  Settings trước đây chỉ ghi localStorage, công tắc không ảnh hưởng gì tới việc
  giao tin
- Evaluation: `pytest tests/test_api/test_reminders.py` 21 passed,
  `tests/test_services/test_telegram_channel.py` 22 passed,
  `tests/test_api/test_telegram_channel.py` 8 passed, nhóm hồi quy
  reminders/web_push/worker/push/tasks/schedule_conflicts/calendar_auto_refresh
  119 passed; `ruff check` sạch; web app `tsc -p tsconfig.app.json` sạch,
  `vite build` sinh được `dist/sw.js` có cả `push` lẫn `notificationclick`,
  `node --test tests/PushNotification.test.ts` 15 passed, `vitest` các file
  Push*/Pwa*/NotificationPreferencesPanel 36 passed; extension `vitest` 41 passed
- Cost/latency: không thêm lời gọi LLM nào. Thêm một truy vấn nhỏ theo
  `provider_message_id` mỗi lần người dùng bấm nút trên Telegram
- Failure observed: `snooze` trong test Telegram dùng mốc giờ giả nên bundle
  không tới hạn lại — mốc mới tính từ thời điểm bấm nút thật, đã sửa test theo
  đúng ngữ nghĩa đó
- Follow-up/rollback: rollback từng phần được — bỏ `NotificationPreferencesPanel`
  khỏi Settings, hoặc trả `pwa.config.ts` về `generateSW`. Còn treo: (1) chưa có
  alembic nên các cột mới của `notification_preferences` do
  `ensure_runtime_schema()` thêm lúc khởi động; (2) nút nhắc lại/bỏ qua mới có ở
  extension và Telegram, thông báo của PWA còn phải mở app mới thao tác được vì
  service worker không cầm được access token
