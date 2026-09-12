/**
 * Sidebar chính có New Briefing + Search + Tasks + Routines + Projects.
 * Meeting Notes tạm ẩn (2026-08-25, chưa public).
 * Nút thu/mở sidebar nằm trong chính sidebar, không còn ở TopBar.
 * Các mục Run Briefing và Notifications không còn nằm trong menu tài khoản;
 * TopBar không còn search bar / avatar góc phải.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('shell navigation layout', () => {
  it('sidebar keeps Tasks, Projects and search, hides Meeting Notes, with a reduced account menu', () => {
    const sidebarSource = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    assert.match(sidebarSource, /path: '\/tasks'/);
    // Meeting tạm rút khỏi sidebar — route trong App.tsx giữ nguyên, chỉ gỡ
    // lối vào. Chốt lại ở đây để không ai vô tình thêm lại mà không bàn.
    assert.doesNotMatch(sidebarSource, /path: '\/meeting-notes'/);
    assert.match(sidebarSource, /onOpenCommandPalette/);
    assert.match(sidebarSource, /accountExtraLinks/);
    assert.match(sidebarSource, /path: '\/sources'/);
    assert.match(sidebarSource, /path: '\/data-privacy'/);
    assert.doesNotMatch(sidebarSource, /path: '\/run'/);
    assert.doesNotMatch(sidebarSource, /path: '\/notifications'/);
    assert.match(sidebarSource, /path: '\/routines'/);
    assert.match(sidebarSource, /path: '\/projects'/);
    assert.match(sidebarSource, /t\.nav\.giveFeedback/);
    assert.match(sidebarSource, /navigate\('\/extension'\)/);
    assert.match(sidebarSource, /t\.nav\.installExtension/);
    assert.match(sidebarSource, /requestProductRating\(\)/);
    assert.doesNotMatch(sidebarSource, /navItems\.push\(\{\s*path: '\/admin'/);
    assert.match(sidebarSource, /if \(user\?\.role === 'admin'\)[\s\S]*path: '\/admin\/discord-announcements'/);

    const paletteSource = readFileSync(join(root, 'src/components/ui/CommandPalette.tsx'), 'utf8');
    assert.doesNotMatch(paletteSource, /navigate\('\/run'\)/);
  });

  it('sidebar owns the collapse toggle and TopBar no longer duplicates it', () => {
    const sidebarSource = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    const topBarSource = readFileSync(join(root, 'src/components/layout/TopBar.tsx'), 'utf8');
    const shellSource = readFileSync(join(root, 'src/components/layout/AppShell.tsx'), 'utf8');

    assert.match(sidebarSource, /onToggleCollapse/);
    assert.match(sidebarSource, /PanelLeft/);
    // Hai lối vào cho cùng một việc thì người dùng phải đoán cái nào là cái
    // thật — TopBar không được giữ lại bản sao.
    assert.doesNotMatch(topBarSource, /PanelLeft/);
    assert.doesNotMatch(topBarSource, /onToggleSidebarCollapse/);
    assert.match(shellSource, /onToggleCollapse=\{toggleSidebarCollapse\}/);
  });

  it('topbar drops search trigger and corner avatar menu', () => {
    const source = readFileSync(join(root, 'src/components/layout/TopBar.tsx'), 'utf8');
    assert.doesNotMatch(source, /IconSearch/);
    assert.doesNotMatch(source, /UserAvatar/);
    assert.doesNotMatch(source, /showProfileMenu/);
    assert.doesNotMatch(source, /searchPlaceholder/);
  });

  it('topbar lets a long title shrink before actions leave a mobile viewport', () => {
    const source = readFileSync(join(root, 'src/components/layout/TopBar.tsx'), 'utf8');
    assert.match(source, /className="flex min-w-0 flex-1 items-center gap-2"/);
    assert.doesNotMatch(source, /className="flex min-w-0 shrink-0 items-center gap-2"/);
  });

  it('sidebar uses sliding active nav pill', () => {
    const source = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    assert.match(source, /layoutId="app-nav-active"/);
    assert.match(source, /useMotionEnabled/);
  });

  it('briefing history is collapsible and no longer divided from the tools above by a rule line', () => {
    const source = readFileSync(join(root, 'src/components/layout/Sidebar.tsx'), 'utf8');
    assert.match(source, /historyCollapsed/);
    assert.match(source, /setHistoryCollapsed/);
    // Cả 2 khối (có lịch sử / rỗng) trước đây đều mở đầu bằng "pt-3 mt-3
    // border-t" — cụm border-t đó là thanh ngang cần bỏ, không xoá nhầm
    // border-t ở chỗ khác (footer, popover...).
    assert.doesNotMatch(source, /pt-3 mt-3 border-t/);
  });
});
