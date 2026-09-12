# Capture actual minutes

- Objective: bắt đầu thu `actual_minutes` tự báo khi task hoàn tất, theo ADR-018 QĐ-5.
- Sources: `AGENTS.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`, ADR-018 QĐ-5.
- Scope: `POST /tasks/{id}/complete`, response/API web, dialog web và test; không sửa planner, migration/schema hay mobile.
- Ownership: Codex; base/head lúc bắt đầu `65aad1fd133e15941afb9f78aca7eaf07bc347ab`; chưa commit, merge, push hoặc deploy.
- Behaviour: body optional; `actualMinutes` 1–1440 được ghi cùng transition, bỏ qua gửi body rỗng để giữ `NULL`, invalid trả 422 trước khi đổi task.
- Files: `src/api/tasks.py`, `src/models/schemas.py`, `client/web-app/src/{lib/tasksApi.ts,pages/TasksPage.tsx,i18n/translations.ts}`, test API/web.
- Verification: `APP_SECRET_KEY=test-only-not-a-production-secret ... pytest tests/test_api/v1/test_tasks.py -q` → 32 passed; `npx tsc --noEmit` → pass; `npx vitest run tests/TasksApiLifecycle.test.tsx tests/TasksCalendarPage.test.tsx` → 16 passed; `npx oxlint` → exit 0 với 9 warning có sẵn; `npm run build` → pass.
- Full baseline: `pytest tests/ -q` không nạp `.env` → 2352 passed, 305 failed, 7 skipped; 4 fail tăng thêm là 4 case mới cần `APP_SECRET_KEY`, còn baseline do environment thiếu `.env`. Focused test dùng secret giả để thực thi path mới, không dùng production secret.
- Risk/config: schema có sẵn, không migration; mobile tiếp tục gọi không body nên tương thích, chưa cần sửa `apps/mobile`.
- Rollback: bỏ payload, dialog và test trong diff; không có data/config/deploy đã thay đổi.
