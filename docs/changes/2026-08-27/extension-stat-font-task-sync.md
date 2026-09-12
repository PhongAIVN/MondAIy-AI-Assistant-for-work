# Extension: số stat bar hết giống chữ La Mã + tự sync danh sách task

## Objective

QA phản hồi 2 việc ở side panel extension (`client/extension`):

1. Số ở dải thống kê ("QUÁ HẠN / TUẦN NÀY / TỔNG") render bằng
   Cormorant Garamond (old-style figures) nên "1" đọc thành "I", "11" thành
   "II".
2. Confirm/done/dismiss một task bên web app thì panel không cập nhật — chỉ
   fetch lúc mount / "Thử lại" / sau QuickAdd.

Đã chọn **cách A** cho việc 2: panel tự fetch lại khi hiện + poll nhẹ. (Cách B
— cầu localStorage rev cho sync tức thì — để sau.)

## Scope

- `client/extension/entrypoints/sidepanel/App.tsx`
  - `TaskStatsBar`: 3 số bỏ `font-heading`, thêm `tabular-nums` (dùng
    `--font-sans` = Geist, có lining figures; `tabular-nums` là utility lõi
    Tailwind v4, không cần khai thêm CSS).
  - `TasksView.load()`: thêm tham số `quiet` — làm mới ngầm không set
    `state="loading"`, lỗi mạng thoáng qua thì `return` sớm giữ nguyên danh
    sách đang hiện thay vì nhảy màn lỗi.
  - `TasksView`: `useEffect` mới — `visibilitychange` + `setInterval(45s)` gọi
    `load(true)` khi `document.visibilityState === "visible"`, cleanup gỡ
    listener + clear interval.
- `client/extension/entrypoints/sidepanel/App.test.tsx`: +2 test.

KHÔNG đụng: web app, background, content script, backend, schema.

## Base / head

- Base: `4623f30` (main, sau khi FF-pull 16 commit ngày 2026-08-27 —
  gồm #99 taskCheckIn thêm `startedAt` vào `makeTask()` test helper; `git
  stash pop` auto-merge `App.test.tsx` sạch, không conflict)
- Head: chưa commit (working tree)

## Observable behavior

- Dải thống kê: số hiển thị bằng font sans, "1"/"11" không còn lẫn chữ La Mã;
  chữ số cùng bề rộng (tabular) nên căn cột thẳng.
- Duyệt/hoàn thành/bỏ một việc bên web app → chuyển focus về side panel →
  danh sách + banner "N việc đang chờ duyệt" khớp trong vòng một nhịp
  `visibilitychange`; nếu panel mở liên tục thì tối đa 45s.
- Làm mới ngầm không chớp spinner; nếu lần fetch ngầm lỗi mạng, danh sách cũ
  giữ nguyên, không hiện nút "Thử lại".

## Files

- `client/extension/entrypoints/sidepanel/App.tsx` (+25 / -5)
- `client/extension/entrypoints/sidepanel/App.test.tsx` (+34)

## Commands / results

- `pnpm compile` (tsc --noEmit): sạch (trước và sau FF-pull).
- `pnpm test` (vitest): sau FF-pull **138 pass** / 11 file (baseline 136 từ
  #99 + 2 test mới). Trước pull: 111 / 9 file.
- `pnpm build` (`wxt build --mode production`): ✔ 1.2s.
- `npx wxt build --mode development`: ✔ 0.84s.
- Lint: package không có eslint/biome riêng — cổng lint ở đây là `tsc`.

## Skipped checks

- Browser-preview verify: side panel MV3 không render được trong Browser pane
  (runtime khác). Đã phủ bằng RTL + jsdom trong App.test.tsx.

## Risk

Thấp. Font: đổi 3 class, thuần hiển thị. Sync: `load(quiet)` nhánh cũ
(`load()` không tham số) không đổi hành vi — "Thử lại" / QuickAdd vẫn full
load kèm spinner. Poll 45s + `visibilitychange` cùng gọi `reconcileWebSession()`
(nằm trong `load`) nên có `executeScript` đọc localStorage tab web mỗi 45s khi
panel mở — chi phí không đáng kể, và tiện giữ session tươi.

## Migration / config impact

Không.

## Merge / deploy status

Chưa commit, chưa merge. Frontend Vercel-managed; extension build thủ công /
`wxt` dev. Cần build lại (`pnpm dev` HMR hoặc reload unpacked) để thấy đổi.

## Rollback

`git checkout -- client/extension/entrypoints/sidepanel/App.tsx client/extension/entrypoints/sidepanel/App.test.tsx`

## Follow-up

- Cách B (sync tức thì khi panel mở cạnh tab web): web app ghi
  `localStorage["mondaiy_sync_rev"]` sau mutation task → `web-session.content.ts`
  nghe key đó → background bump `chrome.storage.local` → `TasksView` watch.
- Auth handoff "quằn" (đăng nhập web xong panel không nhận): thêm cùng
  `visibilitychange` → `reconcileWebSession()` vào `useAuthGate`. Chưa làm —
  ngoài phạm vi lần này.
