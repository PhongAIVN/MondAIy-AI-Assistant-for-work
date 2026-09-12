# WHAT_CHANGED — Port image paste/drop vision OCR pipeline

| Field | Value |
| --- | --- |
| Task ID | `agent/vision-image-port` |
| Status | Integrated (in agent branch, not merged) |
| Date | 2026-08-18 |
| Lead | Lane A agent (this task) |
| Agents / lanes | Lane A: nguyên trạng port, worktree `.claude/worktrees/agent-a2e21d29f525195a1` |
| Base SHA | `cec16e4b730fbfe7581456cfbf98ef5c676d553a` (HEAD of `feat/ui-revamp-va-agent-openrouter` at task start) |
| Head / merge SHA | branch `agent/vision-image-port`, commit `e04fae0` (chạy `git log -1` trong worktree để lấy full SHA) |
| PR / issue / ADR | Không có PR/issue được giao; lệch runtime provider OpenAI (ngoài OpenRouter/OD-03) đã nêu ở "Risks" |

Ghi chú: `docs/changes/` là fallback theo AGENTS.md vì tool sandbox của agent
không cho phép ghi trực tiếp vào `../Guidebook-Agent-Deploy/changes/` (path đó
nằm ngoài worktree cô lập được cấp cho agent này, dù thư mục AI workspace có
tồn tại). Lead nên copy nội dung này sang
`../Guidebook-Agent-Deploy/changes/2026-08-18/agent-vision-image-port.md` khi
tích hợp.

## Intent and acceptance criteria

- Intent: port nguyên trạng (không sửa logic) feature "paste/drop ảnh vào ô
  chat → OCR (OpenAI vision) → trả lời text" đang có trên
  `sync/main-8403c7a` nhưng KHÔNG có trên base/main hiện tại, sang branch mới
  dựa trên `cec16e4b730fbfe7581456cfbf98ef5c676d553a`.
- Observable acceptance criteria:
  - `POST /api/v1/vision/actions` tồn tại, yêu cầu auth, trả 422 khi ảnh quá
    lớn hoặc mime không hỗ trợ, trả 503 khi chưa cấu hình `OPENAI_API_KEY`,
    trả `VisionActionResponse` (response/actionType/warnings/...) khi hợp lệ.
  - Paste/drop ảnh vào ô chat DailyBriefingPage set `pastedImage`, hiện
    preview, và khi gửi (Start Briefing hoặc Follow-up) gọi
    `runVisionAction` rồi hiện text trả về trong tin nhắn AI.
- Non-goals: không cải tiến logic vision (rate limit, prompt, phân loại
  action, giới hạn kích thước...) — giữ nguyên hành vi gốc trên
  `sync/main-8403c7a`, kể cả các phần chưa tối ưu.

## Changes

- Observable behavior: thêm endpoint vision mới và luồng UI paste/drop ảnh
  trong DailyBriefingPage; không đổi hành vi endpoint/UI cũ nào khác.
- Components/files:
  - `src/api/vision.py` (mới) — route `/vision/actions`, rate limit
    10/minute, phân loại action_type (task/calendar_event/mixed/unclear).
  - `src/services/vision.py` (mới) — decode data URL, validate mime/size,
    gọi `ChatOpenAI` (langchain-openai) với `openai_vision_model`.
  - `src/models/schemas.py` — thêm `VisionActionRequest`,
    `VisionActionResponse` (chỉ thêm, không xoá class khác).
  - `src/main.py` — thêm import + `app.include_router(vision_router, ...)`.
  - `src/config.py` — thêm `openai_vision_model`,
    `openai_vision_timeout_seconds`, `vision_max_image_bytes`.
    `openai_api_key` đã tồn tại sẵn trên base, không cần thêm.
  - `client/web-app/src/lib/imageClipboard.ts` (mới) — helper đọc file ảnh
    từ clipboard, ưu tiên `items` (macOS screenshot) rồi mới `files`.
  - `client/web-app/src/lib/visionApi.ts` (mới) — `runVisionAction` gọi
    `POST /api/v1/vision/actions`.
  - `client/web-app/src/pages/DailyBriefingPage.tsx` — merge thủ công: thêm
    state `pastedImage`/`visionBusy`, hàm `acceptImageFile`/
    `handleImagePaste`/`handleImageDrop`, nhánh xử lý ảnh trong
    `handleStartBriefing`/`handleSendFollowUp` (dùng `createConversation`,
    `addMessage`, `replaceLatestAiMessage` — API store khớp với sync branch
    nên port gần như nguyên trạng), preview thumbnail + nút xoá ảnh, và
    `onPaste`/`onDrop`/`onDragOver` + cập nhật điều kiện `disabled` của 2 nút
    Send (state A và follow-up) để bấm gửi được khi chỉ có ảnh, không có
    text. Không đụng bất kỳ phần UI/streaming/voice khác của file (file này
    trên base khác nhiều so với sync/main-8403c7a: dùng streaming
    `streamConversationMessage` thay vì non-streaming — nhánh ảnh KHÔNG
    stream, giữ đúng như bản gốc trên sync/main).
- Config/migration/API compatibility: 3 setting mới trong `Settings` đều có
  default (`gpt-5.6-luna`, 60s, 8MB) nên không cần thay đổi `.env` hiện có để
  app khởi động; muốn dùng thật phải set `OPENAI_API_KEY`.

## Agent handoffs and integration

- Ownership boundaries: chỉ agent này ghi vào các file liệt kê ở trên, trong
  worktree riêng `.claude/worktrees/agent-a2e21d29f525195a1`, branch
  `agent/vision-image-port`.
- Integration order/conflicts: chưa merge vào branch nào. Lead cần review diff
  của `DailyBriefingPage.tsx` kỹ vì đây là merge thủ công (xem "Risks" bên
  dưới về các quyết định tự đưa ra).
- Independent review: chưa có review độc lập.

## Validation evidence

Môi trường không có sẵn `.venv`/`node_modules` — phải cài đặt runtime trước
khi test được (network chậm, ~10-15 phút cho backend, ~1 phút cho frontend).

| Command | Result | Timestamp |
| --- | --- | --- |
| `python -m venv .venv_test && .venv_test/bin/pip install -r requirements.txt` | Cài đặt thành công (dùng làm venv tạm để test, đã xoá sau khi xong) | 2026-08-18 |
| `APP_ENV=test OPENAI_API_KEY=test-key LLM_PROVIDER=openai APP_SECRET_KEY=ci-test-secret-key-not-for-production pytest tests/test_services/test_vision.py tests/test_api/test_vision.py -v` | 8 passed | 2026-08-18 |
| `APP_ENV=test OPENAI_API_KEY=test-key LLM_PROVIDER=openai APP_SECRET_KEY=ci-test-secret-key-not-for-production pytest tests/ -q --tb=short` | 1036 passed, 2 skipped, 1 failed (`tests/test_services/test_reminders.py::TestSnoozeAndDismiss::test_snooze_moves_scheduled_at_forward_and_clears_delivery` — xác nhận PRE-EXISTING bằng `git stash`/chạy lại trên code chưa port: cùng lỗi timezone-naive vs aware, không liên quan tới thay đổi của task này) | 2026-08-18 |
| `ruff check src/api/vision.py src/services/vision.py src/config.py src/main.py src/models/schemas.py tests/test_services/test_vision.py tests/test_api/test_vision.py` | All checks passed | 2026-08-18 |
| `npm install` (client/web-app, node_modules chưa có sẵn) | 467 packages installed; `package-lock.json` bị npm tự sửa 3 dòng không liên quan (thêm `workbox-precaching`/`workbox-routing` vào lockfile) — đã `git checkout` để revert, không giữ thay đổi ngoài phạm vi | 2026-08-18 |
| `npx vitest run tests/VisionApi.test.tsx tests/ImageClipboard.test.tsx` | 2 files, 5 tests passed | 2026-08-18 |
| `npx vitest run tests/DailyBriefingApproval.test.tsx tests/DailyBriefingStreaming.test.tsx tests/VisionApi.test.tsx tests/ImageClipboard.test.tsx` | 4 files, 12 tests passed (xác nhận không phá test DailyBriefingPage cũ) | 2026-08-18 |
| `npx vitest run` (toàn bộ client/web-app) | 46/47 file passed, 1 file (`tests/TasksCalendarPage.test.tsx`, 10 test) FAIL — xác nhận PRE-EXISTING bằng `git stash` rồi chạy lại đúng file đó trên code base chưa port: fail giống hệt, không liên quan Vision/DailyBriefingPage | 2026-08-18 |
| `npx tsc -b` (client/web-app) | 3 lỗi TS2835 trong `src/lib/meetingDisplay.ts` và `src/lib/meetingNotesApi.ts` (thiếu extension `.js` trong import) — file này agent KHÔNG đụng tới, xác nhận PRE-EXISTING; không có lỗi nào trong `DailyBriefingPage.tsx`/`visionApi.ts`/`imageClipboard.ts` | 2026-08-18 |
| `npx oxlint src/pages/DailyBriefingPage.tsx src/lib/visionApi.ts src/lib/imageClipboard.ts tests/VisionApi.test.tsx tests/ImageClipboard.test.tsx` | 0 lỗi | 2026-08-18 |

Tests not run and reason:

- Không chạy `make test-agent-coverage` (coverage riêng cho
  `src.agents.pipeline`) vì task không đụng tới pipeline đó.
- Không test thủ công gọi OpenAI vision thật (không có key thật trong môi
  trường agent) — test dùng mock/monkeypatch cho `extract_visual_context` và
  `agent.ainvoke`.
- Không chạy `npm run test` gộp (bao gồm cả `node --test`) vì phần
  `node --test` không liên quan tới file đã đổi; đã chạy `vitest` trực tiếp
  cho các file liên quan và toàn bộ suite vitest để bắt regression.

## Risk, rollback and follow-up

- Risks:
  - Lệch runtime provider: `src/services/vision.py` gọi thẳng
    `ChatOpenAI`/`openai_api_key` thay vì qua OpenRouter — đúng như bản gốc
    trên `sync/main-8403c7a`, nhưng đây là lệch đã biết so với quyết định
    OpenRouter/OD-03 (xem AGENTS.md mục "An toàn và các lệch đã biết"). Task
    này CHỈ port nguyên trạng, không tự chốt lại quyết định provider.
  - `DailyBriefingPage.tsx` trên base khác cấu trúc so với
    `sync/main-8403c7a` (dùng streaming, không có `pastedImage` state cũ).
    Agent đã tự quyết định: giữ nhánh ảnh KHÔNG streaming (đúng bản gốc, vì
    `/vision/actions` không phải SSE endpoint), đặt nhánh pastedImage TRƯỚC
    Gmail-intent gate trong `handleSendFollowUp` để tránh việc có ảnh nhưng
    text trùng từ khoá Gmail bị định tuyến sai. Cần lead review lại đoạn
    logic này trong diff.
  - Task yêu cầu ít nhất test backend cho input hợp lệ/ảnh quá lớn/mime
    không hỗ trợ/chưa cấu hình key — source branch (`sync/main-8403c7a`)
    KHÔNG có test API-level (`tests/test_api/test_vision.py`) sẵn, agent đã
    tự viết mới theo đúng yêu cầu; đây là phần code KHÔNG có sẵn ở nguồn nên
    không phải "port nguyên trạng" thuần tuý — cần lead review test này.
  - `python-3.13` local không có `.venv` sẵn trong repo; agent tạo
    `.venv_test` tạm thời để test rồi xoá sau khi xong (không commit).
- Rollback: `git branch -D agent/vision-image-port` và xoá worktree bằng
  `git worktree remove`; chưa merge vào branch nào nên không cần revert gì
  khác.
- Follow-up: lead review diff `DailyBriefingPage.tsx`, xác nhận quyết định
  đặt nhánh ảnh trước Gmail-intent gate, và quyết định có giữ nguyên
  provider OpenAI thẳng (lệch OD-03) hay điều chỉnh ở lane cải tiến sau
  (lane B/C theo mô tả task). Copy hồ sơ này sang
  `../Guidebook-Agent-Deploy/changes/2026-08-18/` khi có quyền ghi.

## Merge and deployment

- Chưa merge, chưa deploy. Agent không được phép merge/push theo AGENTS.md;
  chờ lead review và quyết định tích hợp.
