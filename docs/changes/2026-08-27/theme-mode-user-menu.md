# WHAT_CHANGED — Dời chế độ giao diện vào menu người dùng

| Field | Value |
| --- | --- |
| Task ID | `theme-mode-user-menu` |
| Status | Validated, awaiting user review |
| Date | `2026-08-27` |
| Lead | `Codex` |
| Agents / lanes | `Codex: production code + test; Antigravity: test matrix + independent review/validation` |
| Base SHA | `8496affdd794a0c5d05a3ac1947b4b82bc14b137` |
| Head / merge SHA | `Working tree, chưa commit theo yêu cầu của Thái` |
| PR / issue / ADR | `Không có` |

## Intent and acceptance criteria

- Dời năm lựa chọn `light/dark/white/black/system` từ tab Appearance sang user dropdown của Sidebar, ngay cạnh khối BỘ NỀN MÀU.
- Tái dùng `usePreferencesStore.theme/setTheme`; active state có `aria-pressed`; click cập nhật đúng shared state.
- SettingsPage không còn theme selector; palette selector giữ nguyên hành vi.
- Non-goals: theme engine, `PALETTES`, mobile app và các trang khác.

## Research and scope

- Sources: `AGENTS.md`, `docs/projects/README.md`, `docs/WORKFLOW.md`, `SettingsPage.tsx`, `Sidebar.tsx`, `usePreferencesStore.ts`, test Sidebar hiện có.
- Owned paths: `client/web-app/src/pages/SettingsPage.tsx`, `client/web-app/src/components/layout/Sidebar.tsx`, test liên quan, file evidence này.
- Risk: user dropdown hẹp; test cần phân biệt theme control với palette control và xác nhận không nhân đôi source of truth.

## Validation evidence

| Command | Result | Runner |
| --- | --- | --- |
| `npx vitest run` (baseline) | Pass, 366/366; 89 files; tập fail rỗng | Codex |
| `npx vitest run tests/SidebarThemeMode.test.tsx tests/SettingsPageAppearance.test.tsx` | Pass, 5/5; 2 files | Codex + Antigravity độc lập |
| `npx vitest run` (candidate) | Pass, 371/371; 91 files; đúng +5; tập fail rỗng | Codex + Antigravity độc lập |
| `npx tsc --noEmit` | Pass, exit 0 | Codex + Antigravity độc lập |
| `npx oxlint` | Pass, exit 0; 9 warning ngoài diff/có sẵn | Codex + Antigravity độc lập |
| `npm run build` | Pass; 2.442 modules transformed, PWA service worker generated | Codex + Antigravity độc lập |
| `git diff --check` | Pass | Codex + Antigravity độc lập |

- Observable behavior: user menu hiện đủ 5 mode bằng nhãn vi/en, click cập nhật Zustand state + `nav_theme`, active state đổi đúng; palette state/persistence độc lập; Settings không còn selector.
- Tests not completed: chưa có visual/layout test cho viewport rất thấp; behavioral matrix bắt buộc đã chạy đủ.
- Independent review: PASS; không có correctness/a11y finding blocking.

## Risk, rollback and follow-up

- Rollback: revert các hunk trong Sidebar, SettingsPage, test và evidence record.
- Follow-up: Tab Appearance sẽ chỉ còn tiêu đề sau khi dời; giữ nguyên theo brief, không tự ý xoá tab.
- Residual risk: Popover ở viewport rất thấp có thể cắt phần action do header + cụm giao diện nằm ngoài vùng scroll; chưa thay đổi layout ngoài brief.

## Merge and deployment

| Item | Value |
| --- | --- |
| Batch / date | `theme-mode-user-menu` / `2026-08-27` |
| User-visible update | Chọn chế độ giao diện trong menu người dùng cạnh BỘ NỀN MÀU |
| Scope | Frontend web |
| Source | Working tree trên base `8496aff` |
| Validation | 371/371 Vitest; targeted 5/5; tsc/oxlint/build pass; independent review pass |
| Status | Planned — validated, awaiting user review |
| Rollback | Revert working-tree diff |

- Merge status: Chưa commit/merge theo yêu cầu.
- Deploy status: Không deploy.
