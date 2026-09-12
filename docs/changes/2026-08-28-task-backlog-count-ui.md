# Task backlog count UI

- Objective: hiển thị số task bị backend loại khỏi task cards và mở trang task đầy đủ.
- Research: `BRIEF.md`, `docs/projects/product/prd.md` (FR-060–069), `DailyBriefingPage.tsx`, `DailyBriefingStreaming.test.tsx`.
- Scope/owner: Codex; `client/web-app/src/pages/DailyBriefingPage.tsx` và `client/web-app/tests/DailyBriefingStreaming.test.tsx`; không đổi backend.
- Base/head: `6bcb41af5ab8b41ec0b7bdebcbd3c8be6addab4e` / uncommitted working tree.
- Behavior: `taskBacklogCount > 0` hiện một dòng “Còn N việc tồn đọng →”; bấm chuyển `/tasks`. Giá trị `0` hoặc thiếu không render.
- Tests: baseline `npx vitest run` 401 pass; sau đổi 404 pass. Focused test 18 pass. Cố ý đổi điều kiện `> 0` thành `> 4` khiến test count=4 đỏ, sau đó khôi phục.
- Gates: `npx tsc --noEmit`, `npx oxlint`, `npm run build` pass. Oxlint chỉ báo warning có sẵn; build cảnh báo chunk lớn có sẵn.
- Risk/impact: không migration, config, privacy hay deploy. Rollback: xóa block render và test mới.
- Status: chưa commit, push hay deploy theo brief.
