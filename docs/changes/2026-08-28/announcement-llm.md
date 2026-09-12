# Announcement candidate LLM extraction

## Objective

Biến text thông báo do admin dán thành đề xuất `title`, `body`, `category` và
`aliases` có cấu trúc; admin vẫn phải xem, sửa và bấm publish trước khi nội dung
đi vào kho thông tin chương trình.

## Authority and research

- `BRIEF.md`: nghiệm thu, ranh giới file và yêu cầu fallback/sanitize.
- `AGENTS.md`, `docs/WORKFLOW.md`: quyền, evidence và completion gate.
- `docs/projects/product/prd.md`: nguyên tắc đề xuất cần xác nhận, BR-01/03/05.
- `docs/projects/engineering/adr/adr-015-human-maintained-program-information.md`:
  kho nội dung do đội ngũ duyệt, source scope do server cấp.
- Executable truth: `src/services/announcement_candidates.py`, API admin,
  `AdminDiscordAnnouncementPage.tsx`, `Sidebar.tsx` và test hiện hữu.

## Acceptance criteria

- LLM được lấy duy nhất qua `get_llm(lane="work_response")`; test mock tại biên này.
- Text không tin cậy được sanitize trước prompt; output chỉ nhận sáu category hợp lệ.
- Lỗi provider/schema/grounding rơi về regex, có dấu vết trong preview và log.
- Candidate chỉ là draft; admin sửa category/aliases trước publish; không auto-publish.
- Mỗi nhánh mới có test và mutation proof; full `pytest tests -q` và frontend build pass.

## Scope and ownership

- Lead Codex: toàn bộ production code, test integration, conflict resolution và báo cáo.
- Antigravity: test matrix và final review/validation độc lập; không sửa production code.
- Allowed production paths theo `BRIEF.md`; thêm test, record này và `BAOCAO.md`.

## Source state

- Base/head trước sửa: `b83bb8af0b511d22dd6fa947324cb5c16e27abba` (`origin/main`).
- Branch: `work/announcement-llm`; worktree sạch khi bắt đầu.
- Baseline cùng environment: `44 passed, 2945 deselected` cho
  `pytest tests -k "announcement or program_information" -q`.

## Observable behavior and validation

- Admin paste tạo candidate `draft`; `get_llm(lane="work_response")` chỉ đề
  xuất title extractive, category và aliases. Body luôn là evidence do server
  sanitize/canonicalize, model không có quyền ghi.
- Title không phải canonical contiguous span của evidence, output sai schema,
  provider lỗi hoặc model cố trả body đều rơi về regex với
  `extractionMethod=regex_fallback`, `fallbackReason` và warning log.
- UI hiện raw evidence, exact title/body sẽ publish, category/aliases có thể sửa;
  publish request lưu đúng phần admin đã duyệt. Candidate không auto-publish.
- Sidebar chỉ thêm direct link `/admin/discord-announcements` trong nhánh role admin.

### Commands and real results

- Baseline: selector `44 passed, 2945 deselected`.
- Final selector: `66 passed, 2945 deselected`.
- Final backend targeted: `28 passed`; Antigravity chạy độc lập cũng `28 passed`.
- Final full backend, với explicit dummy test OAuth config vì `.env` để rỗng hai
  key này: `3004 passed, 7 skipped`.
- Frontend: Node tests `120 passed`; Vitest `422 passed`; page targeted `3 passed`;
  `pnpm lint` exit 0 với warning có sẵn; `pnpm build` passed.
- Ruff cho bốn Python file thay đổi: passed. `git diff --check`: passed.
- Candidate tracked-diff SHA-256:
  `5ca064df785c1fe3a2b0da3de13d3f1ec72edfeb9cbdf652bb8043e540246565`.
- Antigravity final review: PASS, không còn finding blocking.

### Mutation proof

- Vô hiệu LLM call → happy extraction test đỏ.
- Đưa raw thay sanitized vào prompt → sanitize-boundary test đỏ.
- Cho LLM điều khiển body → negation/body-ownership test đỏ.
- Bỏ extractive-title guard → 4 counterexample (`ngày mốt`, `next week`,
  room `9`→`ngày 9`, `bắt buộc`) cùng đỏ.
- Bỏ category/aliases đã duyệt khi publish → API persistence/alias test đỏ.
- Bỏ fallback reason → fallback-observability test đỏ.
- Bỏ aliases người dùng sửa khỏi publish payload → frontend test đỏ.
- Ẩn exact title/body sắp publish → frontend review test đỏ.

## Risk / config / migration

- Rủi ro: prompt injection, LLM bịa dữ kiện, output không đúng schema, admin edit
  bị bỏ qua khi publish; các rủi ro acceptance đã có positive/negative proof.
- Residual: concurrent request cùng content hash có cửa sổ SELECT→await→INSERT;
  chưa reproduce trong task này, nên ghi follow-up reliability thay vì khẳng định.
- Không gọi provider LLM thật theo nghiệm thu; toàn bộ test mock đúng biên `get_llm`.
- Không thêm config, secret, migration hay production action.
- Rollback: bỏ diff local trên branch này; chưa commit/push/deploy.

| Item | Value |
| --- | --- |
| Batch / date | `announcement-llm` / 2026-08-28 |
| User-visible update | Admin nhận đề xuất có cấu trúc và sửa trước publish |
| Scope | Backend API/service + admin frontend |
| Source | `b83bb8a` + local diff hash `5ca064df…6565` |
| Validation | 3004 pytest; 120+422 frontend; build/lint/Ruff; mutation; Antigravity PASS |
| Status | Validated locally; not integrated/deployed |
| Rollback | Revert local diff; không có production artifact |
