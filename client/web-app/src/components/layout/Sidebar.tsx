import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'motion/react';
import { useTranslation } from '../../i18n/useTranslation';
import {
  usePreferencesStore,
  PALETTES,
  type ThemeMode,
} from '../../stores/usePreferencesStore';
import {
  addConversationToProject,
  listProjects,
  removeConversationFromProject,
  type Project,
} from '../../lib/projectsApi';
import { useAuthStore } from '../../stores/useAuthStore';
import { useConversationStore } from '../../stores/useConversationStore';
import { useAppStore } from '../../stores/useAppStore';
import { usePipelineRunStore } from '../../stores/usePipelineRunStore';
import { useAppTourStore } from '../../stores/useAppTourStore';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';
import { requestProductRating } from '../../hooks/useProductRating';
import { shortcutLabel } from '../../lib/keyboardShortcuts';
import { isEnabledProvider } from '../../types/pipeline';
import type { Conversation } from '../../types/conversation';
import { MondaiyLogo } from '../ui/MondaiyLogo';
import { UserAvatar } from '../ui/UserAvatar';
import {
  IconPrivacy,
  IconSources,
} from '../ui/ProductIcons';
import {
  CalendarDays,
  Plus,
  ShieldAlert,
  ChevronUp,
  ChevronDown,
  HelpCircle,
  LogOut,
  MoreVertical,
  Edit2,
  Trash2,
  Search,
  Sparkles,
  MessageSquareText,
  PanelLeft,
  Download,
  Settings,
  User,
  Folder,
  FolderPlus,
  FolderMinus,
  Star,
  Sun,
  Moon,
  Monitor,
  Megaphone,
  Repeat2,
} from 'lucide-react';

interface SidebarProps {
  isOpenOnMobile?: boolean;
  onCloseMobile?: () => void;
  isCollapsed?: boolean;
  width?: number;
  onWidthChange?: (width: number) => void;
  onOpenCommandPalette?: () => void;
  /** Hover peek khi sidebar đang thu — chỉ desktop. */
  onMouseEnterDesktop?: () => void;
  onMouseLeaveDesktop?: () => void;
  isPeeking?: boolean;
  /** Thu/mở sidebar. Nút nằm ngay trong sidebar, không ở TopBar. */
  onToggleCollapse?: () => void;
}

/** Khoảng width cố định — kéo được nhưng không dãn quá mức. */
export const SIDEBAR_WIDTH = {
  collapsed: 64,
  min: 200,
  default: 224,
  max: 320,
} as const;

export const Sidebar: React.FC<SidebarProps> = ({
  isOpenOnMobile,
  onCloseMobile,
  isCollapsed = false,
  width = SIDEBAR_WIDTH.default,
  onWidthChange,
  onOpenCommandPalette,
  onMouseEnterDesktop,
  onMouseLeaveDesktop,
  isPeeking = false,
  onToggleCollapse,
}) => {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const motionEnabled = useMotionEnabled();
  const { profile } = usePreferencesStore();
  const theme = usePreferencesStore((s) => s.theme);
  const setTheme = usePreferencesStore((s) => s.setTheme);
  const palette = usePreferencesStore((s) => s.palette);
  // Cỡ chữ hệ thống lớn thì header hẹp lại tương đối so với chữ — thu nhỏ cỡ
  // logo (icon lẫn chữ "mondaiy" cùng nhỏ lại) thay vì ẩn chữ đi, để 2 nút
  // cạnh đó (thu gọn sidebar, tìm kiếm) luôn có chỗ mà logo vẫn đọc được.
  const compactHeaderLogo = usePreferencesStore((s) => s.accessibility.fontSize === 'large');
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsCollapsed, setProjectsCollapsed] = useState(false);
  // Menu con "đưa vào dự án" — mở theo từng hội thoại, đóng khi menu cha đóng.
  const [projectPickerOpen, setProjectPickerOpen] = useState(false);
  const setPalette = usePreferencesStore((s) => s.setPalette);
  const themeModeOptions: Array<{
    mode: ThemeMode;
    label: string;
    icon: React.ReactNode;
  }> = [
    { mode: 'light', label: t.topbar.light, icon: <Sun className="h-3.5 w-3.5" /> },
    { mode: 'dark', label: t.topbar.dark, icon: <Moon className="h-3.5 w-3.5" /> },
    { mode: 'white', label: t.topbar.white, icon: <Sun className="h-3.5 w-3.5 fill-current" /> },
    { mode: 'black', label: t.topbar.black, icon: <Moon className="h-3.5 w-3.5 fill-current" /> },
    { mode: 'system', label: t.topbar.system, icon: <Monitor className="h-3.5 w-3.5" /> },
  ];
  const { user, signOut, accessToken } = useAuthStore();
  const { conversations, fetchConversations, deleteConversation, renameConversation, setFavorite, generatingIds } = useConversationStore();

  useEffect(() => {
    if (accessToken) void fetchConversations(accessToken, language);
    if (accessToken) {
      void listProjects(accessToken)
        .then(setProjects)
        .catch(() => setProjects([]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const submitRename = async () => {
    if (!accessToken || !convToRename || !renameInputTitle.trim()) return;
    try {
      await renameConversation(accessToken, convToRename.id, renameInputTitle.trim());
      setConvToRename(null);
      addToast({
        type: 'info',
        title: language === 'vi' ? 'Đã đổi tên' : 'Briefing renamed',
        message: language === 'vi' ? 'Đã đổi tên briefing.' : 'Briefing renamed.',
      });
    } catch {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không đổi tên được' : 'Rename failed',
        message: language === 'vi' ? 'Vui lòng thử lại.' : 'Please try again.',
      });
    }
  };
  const { addToast } = useAppStore();
  const requestAppTour = useAppTourStore((s) => s.requestAppTour);
  const connections = usePipelineRunStore((state) => state.connections);
  const connectedCount = connections.filter(
    (connection) => connection.connected && isEnabledProvider(connection.provider),
  ).length;

  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [showSignOutConfirm, setShowSignOutConfirm] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);

  const [activeMenuConvId, setActiveMenuConvId] = useState<string | null>(null);
  const [historyMenuPos, setHistoryMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [convToDelete, setConvToDelete] = useState<any | null>(null);
  const [convToRename, setConvToRename] = useState<any | null>(null);
  const [renameInputTitle, setRenameInputTitle] = useState('');

  const profileMenuRef = useRef<HTMLDivElement>(null);
  const historyMenuRef = useRef<HTMLDivElement>(null);

  const toggleHistoryMenu = (convId: string, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    if (activeMenuConvId === convId) {
      setActiveMenuConvId(null);
      setHistoryMenuPos(null);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    const menuWidth = 176;
    setHistoryMenuPos({
      top: rect.bottom + 4,
      left: Math.min(window.innerWidth - menuWidth - 8, Math.max(8, rect.right - menuWidth)),
    });
    setActiveMenuConvId(convId);
  };

  const closeHistoryMenu = () => {
    setActiveMenuConvId(null);
    setHistoryMenuPos(null);
    // Menu con phải đóng theo menu cha, nếu không mở menu của hội thoại KHÁC
    // sẽ thấy danh sách dự án bung sẵn từ lần trước.
    setProjectPickerOpen(false);
  };

  const toggleFavorite = async (conversation: Conversation, event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!accessToken) return;
    try {
      await setFavorite(accessToken, conversation.id, !conversation.isFavorite);
      addToast({
        type: 'success',
        title: language === 'vi'
          ? (conversation.isFavorite ? 'Đã bỏ ghim' : 'Đã ghim vào Favorites')
          : (conversation.isFavorite ? 'Removed from Favorites' : 'Added to Favorites'),
        message: conversation.title,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không cập nhật được Favorites' : 'Could not update Favorites',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  useEffect(() => {
    if (!isResizing || isCollapsed || !onWidthChange) return;

    const onPointerMove = (e: PointerEvent) => {
      const next = Math.min(
        SIDEBAR_WIDTH.max,
        Math.max(SIDEBAR_WIDTH.min, Math.round(e.clientX)),
      );
      onWidthChange(next);
    };
    const onPointerUp = () => setIsResizing(false);

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    return () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  }, [isResizing, isCollapsed, onWidthChange]);

  const desktopWidth = isCollapsed ? SIDEBAR_WIDTH.collapsed : width;

  // Close history menu on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (historyMenuRef.current?.contains(target)) return;
      if (target.closest('[data-history-menu-trigger]')) return;
      closeHistoryMenu();
    };
    if (activeMenuConvId) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [activeMenuConvId]);

  // Close profile dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target as Node)) {
        setIsProfileMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close popovers and modals on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeMenuConvId) closeHistoryMenu();
        if (convToDelete) setConvToDelete(null);
        if (convToRename) setConvToRename(null);
        if (isProfileMenuOpen) {
          setIsProfileMenuOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isProfileMenuOpen, activeMenuConvId, convToDelete, convToRename]);

  const toggleSidebarLabel = language === 'vi' ? 'Thu/mở thanh bên' : 'Toggle sidebar';

  const handleNewBriefing = () => {
    navigate('/briefing', { state: { reset: true } });
    if (onCloseMobile) onCloseMobile();
  };

  // Các liên kết phụ nằm trong menu tài khoản để giữ sidebar chính gọn.
  type NavItem = {
    path: string;
    label: string;
    icon: React.ComponentType<{ className?: string; size?: number }>;
    badge?: string;
  };

  // Các công cụ admin nằm trong menu tài khoản, không mở cho participant.
  // Các workspace chính nằm ngang hàng để lối vào không phụ thuộc dữ liệu đã có.
  const navItems: NavItem[] = [
    {
      path: '/planner',
      label: language === 'vi' ? 'Kế hoạch' : 'Plans',
      icon: ({ className, size = 16 }: { className?: string; size?: number }) => (
        <CalendarDays className={className} width={size} height={size} />
      ),
    },
    {
      path: '/tasks',
      label: t.nav.myTasks,
      icon: ({ className, size = 16 }: { className?: string; size?: number }) => (
        <CalendarDays className={className} width={size} height={size} />
      ),
    },
    {
      path: '/routines',
      label: t.nav.routines,
      icon: Repeat2,
    },
    {
      path: '/projects',
      label: t.nav.projects,
      icon: ({ className, size = 16 }: { className?: string; size?: number }) => (
        <Folder className={className} width={size} height={size} />
      ),
    },
  ];
  // 2026-08-25: "/sources" rời sidebar, chỉ còn trong menu tài khoản (avatar)
  // theo yêu cầu của Thái — tránh hai chỗ cùng trỏ một trang.

  const accountExtraLinks: Array<{
    path: string;
    label: string;
    icon: React.ComponentType<{ className?: string; size?: number }>;
    badge?: string;
  }> = [
    { path: '/profile', label: t.nav.profile, icon: User },
    {
      path: '/sources',
      label: t.nav.sources,
      icon: IconSources,
      badge: connectedCount > 0 ? `${connectedCount}` : undefined,
    },
    { path: '/data-privacy', label: t.nav.dataPrivacy, icon: IconPrivacy },
  ];

  if (user?.role === 'admin') {
    accountExtraLinks.push({
      path: '/admin/discord-announcements',
      label: language === 'vi' ? 'Nạp thông báo' : 'Import announcements',
      icon: ({ className, size = 16 }: { className?: string; size?: number }) => (
        <Megaphone className={className} width={size} height={size} />
      ),
      badge: 'Admin',
    });
    accountExtraLinks.push({
      path: '/admin',
      label: t.nav.adminPortal,
      icon: ({ className, size = 16 }: { className?: string; size?: number }) => (
        <ShieldAlert className={className} width={size} height={size} />
      ),
      badge: 'Admin',
    });
  }

  const renderNavItem = (item: NavItem) => {
    const Icon = item.icon;

    return (
      <NavLink
        key={item.path}
        to={item.path}
        onClick={onCloseMobile}
        className={({ isActive }) =>
          `app-nav-item relative flex items-center gap-2.5 rounded-xl text-xs font-medium transition-[color,transform] duration-200 ease-[var(--ease-out-quint)] active:scale-[0.98] ${
            isActive ? 'app-nav-item-active font-semibold' : ''
          } ${isCollapsed ? 'h-10 justify-center px-0' : 'justify-between px-3 py-1.5'}`
        }
        title={isCollapsed ? item.label : undefined}
      >
        {({ isActive }) => (
          <>
            {isActive &&
              (motionEnabled ? (
                <motion.span
                  layoutId="app-nav-active"
                  className="app-nav-active-pill pointer-events-none absolute inset-0 rounded-xl"
                  transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.85 }}
                />
              ) : (
                <span className="app-nav-active-pill pointer-events-none absolute inset-0 rounded-xl" />
              ))}
            <div
              className={`relative z-10 flex items-center truncate ${isCollapsed ? 'justify-center' : 'gap-2.5'}`}
            >
              <Icon size={16} className="shrink-0 text-[var(--color-primary)]" />
              {!isCollapsed && <span className="truncate">{item.label}</span>}
            </div>
            {!isCollapsed && item.badge && (
              <span className="relative z-10 px-1.5 py-0.5 text-[10px] rounded bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] font-medium shrink-0">
                {item.badge}
              </span>
            )}
          </>
        )}
      </NavLink>
    );
  };

  // Nhóm theo lastUpdated thật mỗi lần render — conv.dateGroup ghi 1 lần lúc
  // tạo ('today') rồi đứng yên mãi, hôm sau vẫn nằm ở "Today" dù đã cũ.
  const classifyDateGroup = (iso: string): 'today' | 'yesterday' | 'earlier' => {
    const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const diffDays = Math.round((startOfDay(new Date()) - startOfDay(new Date(iso))) / 86_400_000);
    if (diffDays <= 0) return 'today';
    if (diffDays === 1) return 'yesterday';
    return 'earlier';
  };
  const todayConvs = conversations.filter((c) => classifyDateGroup(c.lastUpdated) === 'today');
  const yesterdayConvs = conversations.filter((c) => classifyDateGroup(c.lastUpdated) === 'yesterday');
  const earlierConvs = conversations.filter((c) => classifyDateGroup(c.lastUpdated) === 'earlier');
  const favoriteConvs = conversations.filter((c) => c.isFavorite);

  const historyGroups: { key: string; label: string; items: Conversation[] }[] = [
    { key: 'today', label: t.briefing.history.today, items: todayConvs.filter((c) => !c.isFavorite) },
    { key: 'yesterday', label: t.briefing.history.yesterday, items: yesterdayConvs.filter((c) => !c.isFavorite) },
    { key: 'earlier', label: t.briefing.history.earlier, items: earlierConvs.filter((c) => !c.isFavorite) },
  ];

  // Chỉ nhắc "chưa xếp dự án" khi người dùng ĐÃ tạo dự án — chưa có cái nào
  // thì chấm nhắc chỉ là nhiễu không hành động được.
  const hasProjects = projects.length > 0;

  const renderHistoryRow = (conv: Conversation) => {
    const isActive = location.pathname === `/briefing/conversation/${conv.id}`;
    const isGeneratingHere = generatingIds.has(conv.id);

    return (
      <div key={conv.id} className="relative group">
        <div
          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 ${
            isActive
              ? 'bg-[#E1EBFA] dark:bg-[#0F1F38] text-[#0F1F38] dark:text-[#E2E8F0] font-semibold border-l-2 border-[#2563A6]'
              : 'text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] hover:text-[#0F1F38] dark:hover:text-white'
          }`}
        >
          <button
            type="button"
            onClick={() => {
              navigate(`/briefing/conversation/${conv.id}`);
              if (onCloseMobile) onCloseMobile();
            }}
            className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer focus:outline-none"
            title={conv.title}
          >
            {/* Node trạng thái: rỗng = idle, đặc + nhấp nháy = agent vẫn đang
                trả lời ngầm cho hội thoại này (kể cả khi đang xem hội thoại
                khác) — cờ này sống ở store toàn cục nên rời trang không mất.
                Cũng là điểm neo thị giác phân tách tiêu đề khỏi phần chat bên
                trên nó, giúp phân cấp dễ nhìn hơn khi list dài. */}
            <span
              aria-hidden
              title={
                isGeneratingHere
                  ? (language === 'vi' ? 'mondaiy đang trả lời' : 'mondaiy is replying')
                  : undefined
              }
              className={`h-1.5 w-1.5 shrink-0 rounded-full border transition-colors ${
                isGeneratingHere
                  ? 'animate-pulse border-[var(--color-accent)] bg-[var(--color-accent)]'
                  : 'border-current opacity-30'
              }`}
            />
            <span className="min-w-0 flex-1 truncate">
              {conv.title}
              {/* Huy hiệu "chưa xếp dự án". Chỉ một chấm nhỏ — hàng hội thoại đã
                  chật, thêm chữ sẽ đẩy tiêu đề ra ngoài. Chỉ hiện khi người dùng
                  ĐÃ có dự án, chưa có thì nhắc là vô nghĩa. */}
              {hasProjects && !conv.projectId ? (
                <span
                  aria-hidden
                  title={language === 'vi' ? 'Chưa xếp vào dự án' : 'Not in a project yet'}
                  className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] align-middle opacity-70"
                />
              ) : null}
            </span>
          </button>

          <div className="relative flex h-5 w-8 shrink-0 items-center justify-end">
            <button
              type="button"
              onClick={(e) => void toggleFavorite(conv, e)}
              aria-label={language === 'vi'
                ? (conv.isFavorite ? `Bỏ ghim ${conv.title}` : `Ghim ${conv.title}`)
                : (conv.isFavorite ? `Remove ${conv.title} from Favorites` : `Add ${conv.title} to Favorites`)}
              title={conv.isFavorite ? 'Remove from Favorites' : 'Add to Favorites'}
              className={`rounded p-0.5 transition-opacity hover:bg-[#E1EBFA] dark:hover:bg-[#1E314C] ${
                conv.isFavorite
                  ? 'text-amber-500 opacity-100'
                  : 'text-[#8B98AB] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100'
              }`}
            >
              <Star className="h-3.5 w-3.5" fill={conv.isFavorite ? 'currentColor' : 'none'} />
            </button>
            <button
              type="button"
              data-history-menu-trigger
              onClick={(e) => toggleHistoryMenu(conv.id, e)}
              aria-label={
                language === 'vi'
                  ? `Tùy chọn cho ${conv.title}`
                  : `Actions for ${conv.title}`
              }
              className="p-0.5 rounded hover:bg-[#E1EBFA] dark:hover:bg-[#1E314C] text-[#5A6A85] dark:text-[#AEB9CC] opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity cursor-pointer"
            >
              <MoreVertical className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpenOnMobile && (
        <div
          className="app-overlay fixed inset-0 z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`app-sidebar fixed lg:sticky top-0 left-0 h-[100dvh] flex w-56 flex-col shrink-0 border-r lg:w-[var(--sidebar-desktop-w)] ${
          // Mở trên mobile là drawer kiểu modal, phải đè LÊN TRÊN thanh nav
          // dưới cùng (MobileBottomNav cũng z-40, render sau trong DOM nên
          // vốn đang thắng — nút profile ở đáy sidebar bị nó che mất).
          isPeeking || isOpenOnMobile ? 'z-50 shadow-[4px_0_24px_rgba(0,0,0,0.08)]' : 'z-40'
        } ${
          isResizing ? '' : 'transition-[width,transform] duration-200 ease-in-out'
        } ${isOpenOnMobile ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
        style={
          {
            ['--sidebar-desktop-w' as string]: `${desktopWidth}px`,
          } as React.CSSProperties
        }
        onMouseEnter={onMouseEnterDesktop}
        onMouseLeave={onMouseLeaveDesktop}
      >
        {/* Thanh kéo resize — chỉ desktop, khi chưa thu gọn; clamp 200–320px */}
        {!isCollapsed && onWidthChange && (
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize sidebar"
            aria-valuemin={SIDEBAR_WIDTH.min}
            aria-valuemax={SIDEBAR_WIDTH.max}
            aria-valuenow={width}
            tabIndex={0}
            onPointerDown={(e) => {
              e.preventDefault();
              setIsResizing(true);
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowLeft') {
                e.preventDefault();
                onWidthChange(width - 8);
              } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                onWidthChange(width + 8);
              }
            }}
            className="absolute top-0 right-0 z-[45] hidden h-full w-1.5 cursor-col-resize touch-none lg:block group"
          >
            <span
              className={`pointer-events-none absolute inset-y-0 right-0 w-px transition-colors ${
                isResizing
                  ? 'bg-[var(--color-primary)]'
                  : 'bg-transparent group-hover:bg-[var(--color-primary)]'
              }`}
            />
          </div>
        )}
          {/* Logo Header — thu gọn thì chỉ còn mascot icon; search nằm cạnh
              logo theo yêu cầu 2026-08-25, rời khỏi danh sách điều hướng. */}
          <div
            className={`flex h-[60px] shrink-0 items-center border-b border-[var(--color-border)] ${
              isCollapsed ? 'justify-center px-2' : 'justify-between px-4'
            }`}
          >
            {/* Thu gọn thì đổi logo thành nút mở lại: bề ngang 64px không đủ
                cho cả logo lẫn nút, mà khi đã thu thì việc duy nhất cần làm
                được là mở ra. Hover vào rìa vẫn peek ra header đầy đủ. */}
            {isCollapsed ? (
              <button
                type="button"
                onClick={onToggleCollapse}
                className="flex items-center justify-center overflow-hidden rounded-full focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                title={`${toggleSidebarLabel} (${shortcutLabel('B')})`}
                aria-label={toggleSidebarLabel}
                aria-expanded={false}
              >
                <img src="/loadinggif1.gif" alt="" className="h-9 w-9 rounded-full object-cover" />
              </button>
            ) : (
              <>
                <NavLink
                  to="/briefing"
                  onClick={onCloseMobile}
                  className="flex min-w-0 flex-1 items-center overflow-hidden focus:outline-none"
                  title="mondaiy"
                  aria-label="mondaiy"
                >
                  <MondaiyLogo
                    size={compactHeaderLogo ? 'xs' : 'md'}
                    variant="auto"
                    showIcon
                    className="min-w-0"
                  />
                </NavLink>
                <div className="flex shrink-0 items-center gap-0.5">
                  {onToggleCollapse && (
                    <button
                      type="button"
                      onClick={onToggleCollapse}
                      className="app-icon-button hidden rounded-lg p-2 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] lg:inline-flex"
                      title={`${toggleSidebarLabel} (${shortcutLabel('B')})`}
                      aria-label={toggleSidebarLabel}
                      aria-expanded
                    >
                      <PanelLeft className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      onOpenCommandPalette?.();
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className="app-icon-button rounded-lg p-2 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)]"
                    aria-label={t.actions.search}
                    data-tour-id="sidebar-search"
                  >
                    <Search className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Vùng giữa cuộn; card cohort neo dưới, sát profile */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overflow-x-hidden">
          {/* Primary action nằm cùng nhịp với navigation, không dựng thành card riêng. */}
          <div className={`${isCollapsed ? 'p-2' : 'px-3 py-1'}`}>
            <button
              onClick={handleNewBriefing}
              className={`app-nav-item group w-full flex items-center gap-2.5 rounded-xl text-xs font-semibold text-[var(--color-primary)] transition-[color,transform] duration-200 ease-[var(--ease-out-quint)] active:scale-[0.98] ${
                isCollapsed ? 'h-10 justify-center px-0' : 'justify-between px-3 py-1.5'
              }`}
              title={t.nav.newBriefing}
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <Plus className="w-4 h-4 shrink-0" />
                {!isCollapsed && <span className="truncate">{t.nav.newBriefing}</span>}
              </span>
              {!isCollapsed && <kbd className="text-[11px] font-medium text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">{shortcutLabel('⇧↵')}</kbd>}
            </button>
          </div>

          {/* Navigation Links — New briefing + các mục chính. Search đã dời
              lên header cạnh logo (2026-08-25). */}
          <nav className={`${isCollapsed ? 'px-2' : 'px-3'} py-0.5 space-y-0.5`}>
            {navItems.map((item) => renderNavItem(item))}

            {/* Chỉ danh sách project phụ thuộc inventory; link quản lý ở navItems luôn hiện. */}
            {!isCollapsed && hasProjects && (
              <div className="mt-4 pt-2">
                <div className="flex items-center rounded-xl px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text-secondary)]">
                  <button
                    type="button"
                    onClick={() => setProjectsCollapsed((collapsed) => !collapsed)}
                    className="flex min-w-0 flex-1 items-center gap-1.5 text-left uppercase tracking-wide"
                    aria-expanded={!projectsCollapsed}
                    aria-controls="sidebar-project-list"
                  >
                    <span className="truncate">{t.nav.projects}</span>
                    <ChevronDown className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${projectsCollapsed ? '-rotate-90' : ''}`} />
                  </button>
                </div>
                <motion.div
                  id="sidebar-project-list"
                  initial={false}
                  animate={{ height: projectsCollapsed ? 0 : 'auto', opacity: projectsCollapsed ? 0 : 1 }}
                  transition={{ duration: motionEnabled ? 0.2 : 0 }}
                  className="overflow-hidden"
                >
                  <div className="space-y-0.5 pt-0.5">
                    {projects.map((project) => {
                      const isActive = location.pathname === `/projects/${project.id}`;
                      return (
                        <NavLink
                          key={project.id}
                          to={`/projects/${project.id}`}
                          onClick={onCloseMobile}
                          className={isActive
                            ? 'flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-xs font-medium bg-[var(--color-surface-hover)] text-[var(--color-text-primary)]'
                            : 'flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]'}
                        >
                          <Folder className="h-4 w-4 shrink-0" style={{ color: project.color }} />
                          <span className="truncate">{project.name}</span>
                        </NavLink>
                      );
                    })}
                  </div>
                </motion.div>
              </div>
            )}

            {/* Favorites — section riêng, luôn nằm trên Gần đây. */}
            {!isCollapsed && favoriteConvs.length > 0 && (
              <div className="pt-3 mt-3 space-y-2">
                <div className="px-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-secondary)]">
                  <Star className="h-3.5 w-3.5 text-amber-500" fill="currentColor" />
                  {language === 'vi' ? 'Yêu thích' : 'Favorites'}
                </div>
                <div className="space-y-1 pr-1">
                  {favoriteConvs.map(renderHistoryRow)}
                </div>
              </div>
            )}

            {/* Briefing History Section */}
            {!isCollapsed && conversations.length > 0 && (
              <div className="pt-3 mt-3 space-y-2">
                <button
                  type="button"
                  onClick={() => setHistoryCollapsed((prev) => !prev)}
                  className="w-full px-3 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors"
                  aria-expanded={!historyCollapsed}
                >
                  <span className="truncate">{t.briefing.history.title}</span>
                  <ChevronDown
                    className={`w-3.5 h-3.5 shrink-0 transition-transform duration-200 ${historyCollapsed ? '-rotate-90' : ''}`}
                  />
                </button>

                <motion.div
                  id="sidebar-history-list"
                  initial={false}
                  animate={{ height: historyCollapsed ? 0 : 'auto', opacity: historyCollapsed ? 0 : 1 }}
                  transition={{ duration: motionEnabled ? 0.2 : 0 }}
                  className="overflow-hidden"
                >
                  <div className="space-y-2 pr-1">
                    {historyGroups.map(
                      (group) =>
                        group.items.length > 0 && (
                          <div key={group.key} className="space-y-1">
                            <span className="block px-3 text-[11px] font-medium text-[var(--color-text-muted)]">
                              {group.label}
                            </span>
                            {group.items.map(renderHistoryRow)}
                          </div>
                        ),
                    )}
                  </div>
                </motion.div>
              </div>
            )}

            {/* Empty Briefing History State */}
            {!isCollapsed && conversations.length === 0 && (
              <div className="pt-3 mt-3 space-y-2">
                <div className="px-3 flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                  <span className="truncate">{t.briefing.history.title}</span>
                </div>

                <div className="p-3 mx-1 bg-[#EDF2FB] dark:bg-[#0F1F38]/50 border border-[#E4EAF6] dark:border-[#1E2E4A] rounded-xl text-left space-y-1.5">
                  <p className="text-xs font-semibold text-[#0F1F38] dark:text-[#E2E8F0]">
                    {t.briefing.history.noBriefingsYet}
                  </p>
                  <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] leading-relaxed">
                    {t.briefing.history.noBriefingsDesc}
                  </p>
                  <button
                    type="button"
                    onClick={handleNewBriefing}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[#2563A6] hover:underline pt-0.5 cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>{t.nav.newBriefing}</span>
                  </button>
                </div>
              </div>
            )}
          </nav>
            </div>
          </div>

          {/* User Profile Control & Popover — ngoài vùng scroll để không bị che */}
          <div
            className={`relative z-50 shrink-0 border-t border-[var(--color-border)] ${
              isCollapsed ? 'p-1.5' : 'p-2'
            }`}
            ref={profileMenuRef}
          >
            {/* Popover Dropdown */}
            {isProfileMenuOpen && (
              <div
                className={`absolute z-[60] bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1E2E4A] rounded-[12px] shadow-xl shadow-slate-900/10 dark:shadow-black/40 py-2 text-xs transition-all animate-in fade-in zoom-in-95 duration-150 overflow-hidden ${
                  isCollapsed
                    ? 'bottom-0 left-full ml-2 w-72'
                    : 'bottom-full left-2 right-2 mb-2 w-[calc(100%-16px)] sm:w-[270px]'
                }`}
                style={{ maxHeight: 'calc(100dvh - 5rem)' }}
              >
                {/* Profile Header */}
                <div className="px-3.5 py-3 border-b border-[#D5DDEB] dark:border-[#1E2E4A] bg-[#EDF2FB]/80 dark:bg-[#0F1F38]/40 flex items-center gap-3">
                  <UserAvatar
                    name={profile.name}
                    avatarUrl={profile.avatarUrl || user?.avatarUrl}
                    size="md"
                  />
                  <div className="truncate">
                    <p className="font-extrabold text-xs text-[#0F1F38] dark:text-[#E2E8F0] truncate">
                      {profile.name}
                    </p>
                  </div>
                </div>

                {/* Bộ nền màu — đặt ngay dưới tên người dùng vì đây là thứ
                    đổi tức thì và hay được thử đi thử lại, không nên chôn dưới
                    danh sách điều hướng. Mỗi ô là một chấm màu: người dùng thấy
                    được tông TRƯỚC khi bấm, thay vì phải đọc tên rồi đoán. */}
                <div className="px-3.5 py-2.5 border-b border-[#D5DDEB] dark:border-[#1E2E4A]">
                  <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-[#5A6A85] dark:text-slate-400">
                    {t.auth.colorTheme}
                  </p>
                  <div className="flex items-center gap-1.5">
                    {PALETTES.map((item) => {
                      const active = palette === item.id;
                      const label = language === 'vi' ? item.labelVi : item.labelEn;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => setPalette(item.id)}
                          title={label}
                          aria-label={label}
                          aria-pressed={active}
                          className={`h-6 w-6 rounded-full border-2 transition-transform hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] ${
                            active
                              ? 'border-[#2563A6] dark:border-[#8AB4F8] scale-110'
                              : 'border-transparent'
                          }`}
                          style={{ backgroundColor: item.swatch }}
                        />
                      );
                    })}
                  </div>

                  <div className="mt-2.5 border-t border-[#D5DDEB] pt-2.5 dark:border-[#1E2E4A]">
                    <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-[#5A6A85] dark:text-slate-400">
                      {t.settingsPage.themeModeLabel}
                    </p>
                    <div className="grid grid-cols-5 gap-1">
                      {themeModeOptions.map((item) => {
                        const active = theme === item.mode;
                        return (
                          <button
                            key={item.mode}
                            type="button"
                            onClick={() => setTheme(item.mode)}
                            title={item.label}
                            aria-label={item.label}
                            aria-pressed={active}
                            className={`flex h-10 min-w-0 flex-col items-center justify-center gap-1 rounded-lg border text-[9px] font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] ${
                              active
                                ? 'border-[#2563A6] bg-[#E1EBFA] text-[#2563A6] shadow-sm dark:border-[#8AB4F8] dark:bg-[#1E314C] dark:text-[#8AB4F8]'
                                : 'border-transparent text-[#5A6A85] hover:bg-[#E2E8F0] dark:text-[#AEB9CC] dark:hover:bg-[#0F1F38]'
                            }`}
                          >
                            {item.icon}
                            <span className="w-full truncate px-0.5 leading-none">{item.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Menu Actions */}
                <div className="p-1.5 space-y-0.5 max-h-[60vh] overflow-y-auto">
                  {/* Liên kết từng nằm trên sidebar — chuyển vào account menu.
                      Vẫn cần active-state pill giống nav chính, không phải chỉ
                      là action list — trước đó thiếu hẳn, không có highlight nào. */}
                  {accountExtraLinks.map((item) => {
                    const Icon = item.icon;
                    const isActive =
                      location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
                    return (
                      <button
                        key={item.path}
                        type="button"
                        onClick={() => {
                          setIsProfileMenuOpen(false);
                          navigate(item.path);
                          if (onCloseMobile) onCloseMobile();
                        }}
                        className={`relative w-full text-left px-3 py-2 text-xs rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] ${
                          isActive
                            ? 'text-[#2563A6] font-semibold'
                            : 'text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C]'
                        }`}
                      >
                        {isActive &&
                          (motionEnabled ? (
                            <motion.span
                              layoutId="app-nav-active-account"
                              className="app-nav-active-pill pointer-events-none absolute inset-0 rounded-lg"
                              transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.85 }}
                            />
                          ) : (
                            <span className="app-nav-active-pill pointer-events-none absolute inset-0 rounded-lg" />
                          ))}
                        <Icon size={16} className="relative z-10 text-[#2563A6] shrink-0" />
                        <span className="relative z-10 truncate flex-1">{item.label}</span>
                        {item.badge ? (
                          <span className="relative z-10 px-1.5 py-0.5 text-[10px] rounded bg-[var(--color-surface-muted)] text-[var(--color-text-secondary)] font-medium shrink-0">
                            {item.badge}
                          </span>
                        ) : null}
                      </button>
                    );
                  })}

                  <div className="my-1 border-t border-[#D5DDEB] dark:border-[#1E2E4A]" />

                  {/* Cài đặt chung nằm trong Settings, menu tài khoản chỉ giữ lối tắt. */}
                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      navigate('/settings');
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6]"
                  >
                    <Settings size={16} className="text-[#2563A6] shrink-0" />
                    <span className="truncate">{t.nav.settings}</span>
                  </button>

                  {/* 5. Help & Support */}
                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      navigate('/extension');
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6]"
                  >
                    <Download className="w-4 h-4 text-[#2563A6] shrink-0" />
                    <span className="truncate">{t.nav.installExtension}</span>
                  </button>

                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      navigate('/help');
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6]"
                  >
                    <HelpCircle className="w-4 h-4 text-[#2563A6] shrink-0" />
                    <span className="truncate">{t.nav.help}</span>
                  </button>

                  {/* 5b. Chạy lại tour hướng dẫn toàn app — cố ý giấu trong đây thay vì
                      để lộ trên từng trang. */}
                  <button
                    type="button"
                    data-tour-menu-item
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      if (onCloseMobile) onCloseMobile();
                      requestAppTour();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6]"
                  >
                    <Sparkles className="w-4 h-4 text-[#2563A6] shrink-0" />
                    <span className="truncate">
                      {language === 'vi' ? 'Xem hướng dẫn sử dụng' : 'Take the guided tour'}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      if (onCloseMobile) onCloseMobile();
                      requestProductRating();
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#0F1F38] dark:text-[#E2E8F0] hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] rounded-lg transition-colors flex items-center gap-2.5 font-medium cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6]"
                  >
                    <MessageSquareText className="w-4 h-4 text-[#2563A6] shrink-0" />
                    <span className="truncate">{t.nav.giveFeedback}</span>
                  </button>

                  {/* 6. Divider */}
                  <div className="my-1 border-t border-[#D5DDEB] dark:border-[#1E2E4A]" />

                  {/* 7. Sign Out */}
                  <button
                    onClick={() => {
                      setIsProfileMenuOpen(false);
                      setShowSignOutConfirm(true);
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#A03D3D] hover:bg-[#F9DEDE] dark:hover:bg-[#A03D3D]/20 rounded-lg transition-colors flex items-center gap-2.5 font-semibold cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#A03D3D]"
                  >
                    <LogOut className="w-4 h-4 shrink-0" />
                    <span className="truncate">{t.nav.signOut}</span>
                  </button>
                </div>
              </div>
            )}

            {/* Interactive Profile Block Button */}
            <button
              type="button"
              onClick={() => setIsProfileMenuOpen((prev) => !prev)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setIsProfileMenuOpen((prev) => !prev);
                }
              }}
              aria-haspopup="true"
              aria-expanded={isProfileMenuOpen}
              aria-label="User account menu"
              className={`w-full p-2 rounded-xl flex items-center transition-all duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563A6] focus-visible:ring-offset-2 hover:bg-[#E2E8F0] dark:hover:bg-[#0F1F38] active:bg-[#E1EBFA] dark:active:bg-[#1E314C] ${
                isProfileMenuOpen
                  ? 'bg-[#E2E8F0] dark:bg-[#0F1F38] ring-1 ring-[#2563A6]/40'
                  : ''
              } ${isCollapsed ? 'justify-center' : 'justify-between'}`}
              title={profile.name}
              data-tour-id="sidebar-profile-button"
            >
              <div className="flex items-center gap-2.5 truncate text-left">
                <UserAvatar
                  name={profile.name}
                  avatarUrl={profile.avatarUrl || user?.avatarUrl}
                  size="sm"
                />
                {!isCollapsed && (
                  <div className="truncate">
                    <p className="text-xs font-semibold text-[#0F1F38] dark:text-[#E2E8F0] truncate leading-snug">
                      {profile.name}
                    </p>
                  </div>
                )}
              </div>
              {!isCollapsed && (
                <ChevronUp
                  className={`w-4 h-4 text-[#5A6A85] dark:text-[#AEB9CC] shrink-0 transition-transform duration-150 ${
                    isProfileMenuOpen ? 'rotate-180' : ''
                  }`}
                />
              )}
            </button>
          </div>
      </aside>

      {typeof document !== 'undefined' &&
        activeMenuConvId &&
        historyMenuPos &&
        createPortal(
          <div
            ref={historyMenuRef}
            style={{ top: historyMenuPos.top, left: historyMenuPos.left }}
            className="fixed z-[120] w-44 space-y-0.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-1 text-xs shadow-lg animate-in fade-in zoom-in-95 duration-100"
          >
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                const conv = conversations.find((item) => item.id === activeMenuConvId);
                closeHistoryMenu();
                if (!conv) return;
                setConvToRename(conv);
                setRenameInputTitle(conv.title);
              }}
              className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]"
            >
              <Edit2 className="h-3.5 w-3.5 text-[var(--color-primary)]" />
              <span>{language === 'vi' ? 'Đổi tên briefing' : 'Rename briefing'}</span>
            </button>

            {/* Đưa vào dự án — chỉ hiện khi ĐÃ có dự án. Không có dự án nào mà
                vẫn hiện thì bấm vào là ngõ cụt. Danh sách mở ngay tại chỗ thay
                vì đẩy sang màn hình khác: người dùng đang ở đúng hội thoại cần
                xếp, bắt họ rời đi rồi tìm lại là thừa. */}
            {hasProjects && (
              <>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setProjectPickerOpen((open) => !open);
                  }}
                  aria-expanded={projectPickerOpen}
                  className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]"
                >
                  <FolderPlus className="h-3.5 w-3.5 text-[var(--color-primary)]" />
                  <span>{language === 'vi' ? 'Đưa vào dự án' : 'Add to project'}</span>
                </button>

                {projectPickerOpen && (
                  <div className="max-h-44 overflow-y-auto rounded-lg bg-[var(--color-surface)] p-0.5">
                    {projects.map((project) => {
                      const conv = conversations.find((item) => item.id === activeMenuConvId);
                      const already = conv?.projectId === project.id;
                      return (
                        <button
                          key={project.id}
                          type="button"
                          disabled={already}
                          onClick={async (e) => {
                            e.stopPropagation();
                            const target = conversations.find((item) => item.id === activeMenuConvId);
                            closeHistoryMenu();
                            if (!target || !accessToken) return;
                            try {
                              await addConversationToProject(accessToken, project.id, Number(target.id));
                              await fetchConversations(accessToken, language);
                              addToast({
                                type: 'success',
                                title: language === 'vi' ? 'Đã thêm vào dự án' : 'Added to project',
                                message: project.name,
                              });
                            } catch (error) {
                              addToast({
                                type: 'error',
                                title: language === 'vi' ? 'Không thêm được' : 'Could not add',
                                message: error instanceof Error ? error.message : String(error),
                              });
                            }
                          }}
                          className="flex w-full cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] disabled:cursor-default disabled:opacity-50"
                        >
                          <span className="truncate">{project.name}</span>
                          {already && (
                            <span className="ml-auto shrink-0 text-[10px]">
                              {language === 'vi' ? 'đang ở đây' : 'current'}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Gỡ khỏi dự án — chỉ có nghĩa khi hội thoại đang thuộc một dự án. */}
                {conversations.find((item) => item.id === activeMenuConvId)?.projectId ? (
                  <button
                    type="button"
                    onClick={async (e) => {
                      e.stopPropagation();
                      const target = conversations.find((item) => item.id === activeMenuConvId);
                      closeHistoryMenu();
                      if (!target || !accessToken) return;
                      try {
                        await removeConversationFromProject(accessToken, Number(target.id));
                        await fetchConversations(accessToken, language);
                      } catch (error) {
                        addToast({
                          type: 'error',
                          title: language === 'vi' ? 'Không gỡ được' : 'Could not remove',
                          message: error instanceof Error ? error.message : String(error),
                        });
                      }
                    }}
                    className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left font-medium text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)]"
                  >
                    <FolderMinus className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
                    <span>{language === 'vi' ? 'Gỡ khỏi dự án' : 'Remove from project'}</span>
                  </button>
                ) : null}
              </>
            )}

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                const conv = conversations.find((item) => item.id === activeMenuConvId);
                closeHistoryMenu();
                if (!conv) return;
                setConvToDelete(conv);
              }}
              className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left font-semibold text-[var(--color-danger)] hover:bg-[var(--color-danger-soft)]"
            >
              <Trash2 className="h-3.5 w-3.5 text-[var(--color-danger)]" />
              <span>{language === 'vi' ? 'Xóa briefing' : 'Delete briefing'}</span>
            </button>
          </div>,
          document.body,
        )}

      {typeof document !== 'undefined' &&
        convToDelete &&
        createPortal(
          <div
            className="app-overlay fixed inset-0 z-[110] flex items-center justify-center p-4 animate-in fade-in duration-150"
            onClick={() => setConvToDelete(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-sm space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-6 text-left shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3 text-[var(--color-text-primary)]">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-danger-soft)]">
                  <Trash2 className="h-5 w-5 text-[var(--color-danger)]" />
                </div>
                <div>
                  <h3 className="font-heading text-base font-extrabold">
                    {language === 'vi' ? 'Xóa briefing này?' : 'Delete this briefing?'}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                    {language === 'vi'
                      ? 'Thao tác này sẽ xóa vĩnh viễn cuộc hội thoại và lịch sử tin nhắn đã lưu khỏi mondaiy. Hành động này không thể hoàn tác.'
                      : 'This will permanently remove this conversation and its saved message history from mondaiy. This action cannot be undone.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[var(--color-border)] pt-2">
                <button
                  type="button"
                  onClick={() => setConvToDelete(null)}
                  className="app-control cursor-pointer rounded-xl px-4 py-2 text-xs font-semibold"
                >
                  {language === 'vi' ? 'Hủy' : 'Cancel'}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (!accessToken) return;
                    const targetId = convToDelete.id;
                    const isActive = location.pathname === `/briefing/conversation/${targetId}`;
                    setConvToDelete(null);
                    try {
                      await deleteConversation(accessToken, targetId);
                    } catch {
                      addToast({
                        type: 'error',
                        title: language === 'vi' ? 'Không xóa được' : 'Delete failed',
                        message: language === 'vi' ? 'Vui lòng thử lại.' : 'Please try again.',
                      });
                      return;
                    }

                    if (isActive) {
                      addToast({
                        type: 'info',
                        title: language === 'vi' ? 'Đã xóa briefing' : 'Briefing deleted',
                        message:
                          language === 'vi'
                            ? 'Đã xóa briefing. Bạn có thể bắt đầu một briefing mới bất cứ lúc nào.'
                            : 'Briefing deleted. You can start a new briefing anytime.',
                      });
                      navigate('/briefing', { state: { reset: true } });
                    } else {
                      addToast({
                        type: 'info',
                        title: language === 'vi' ? 'Đã xóa briefing' : 'Briefing deleted',
                        message: language === 'vi' ? 'Đã xóa briefing.' : 'Briefing deleted.',
                      });
                    }
                  }}
                  className="cursor-pointer rounded-xl bg-[var(--color-danger)] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:opacity-90"
                >
                  {language === 'vi' ? 'Xóa briefing' : 'Delete briefing'}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {typeof document !== 'undefined' &&
        convToRename &&
        createPortal(
          <div
            className="app-overlay fixed inset-0 z-[110] flex items-center justify-center p-4 animate-in fade-in duration-150"
            onClick={() => setConvToRename(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-sm space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-6 text-left shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3 text-[var(--color-text-primary)]">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-soft)]">
                  <Edit2 className="h-5 w-5 text-[var(--color-primary)]" />
                </div>
                <div className="flex-1">
                  <h3 className="font-heading text-base font-extrabold">
                    {language === 'vi' ? 'Đổi tên briefing' : 'Rename briefing'}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                    {language === 'vi'
                      ? 'Nhập tiêu đề mới cho bản briefing này.'
                      : 'Enter a new title for this briefing conversation.'}
                  </p>
                </div>
              </div>

              <input
                type="text"
                value={renameInputTitle}
                onChange={(e) => setRenameInputTitle(e.target.value)}
                placeholder={language === 'vi' ? 'Nhập tiêu đề mới...' : 'Enter new title...'}
                className="app-field w-full rounded-xl px-3 py-2 text-xs focus:outline-none"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && renameInputTitle.trim()) {
                    void submitRename();
                  }
                }}
              />

              <div className="flex items-center justify-end gap-2 border-t border-[var(--color-border)] pt-2">
                <button
                  type="button"
                  onClick={() => setConvToRename(null)}
                  className="app-control cursor-pointer rounded-xl px-4 py-2 text-xs font-semibold"
                >
                  {language === 'vi' ? 'Hủy' : 'Cancel'}
                </button>
                <button
                  type="button"
                  disabled={!renameInputTitle.trim()}
                  onClick={() => {
                    if (renameInputTitle.trim()) {
                      void submitRename();
                    }
                  }}
                  className="cursor-pointer rounded-xl bg-[var(--color-primary)] px-4 py-2 text-xs font-semibold text-[var(--color-on-primary)] shadow-xs transition-colors hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
                >
                  {language === 'vi' ? 'Lưu' : 'Save'}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {typeof document !== 'undefined' &&
        showSignOutConfirm &&
        createPortal(
          <div
            className="app-overlay fixed inset-0 z-[110] flex items-center justify-center p-4 animate-in fade-in duration-150"
            onClick={() => setShowSignOutConfirm(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-sm space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-6 text-left shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3 text-[var(--color-text-primary)]">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-danger-soft)]">
                  <LogOut className="h-5 w-5 text-[var(--color-danger)]" />
                </div>
                <div>
                  <h3 className="font-heading text-base font-extrabold">
                    {language === 'vi' ? 'Đăng xuất khỏi mondaiy?' : 'Sign out of mondaiy?'}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                    {language === 'vi'
                      ? 'Bạn có thể đăng nhập lại để tiếp tục truy cập các bản tóm tắt và tùy chọn của mình.'
                      : 'You can sign in again to continue accessing your briefings and preferences.'}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-[var(--color-border)] pt-2">
                <button
                  type="button"
                  onClick={() => setShowSignOutConfirm(false)}
                  className="app-control cursor-pointer rounded-xl px-4 py-2 text-xs font-semibold"
                >
                  {language === 'vi' ? 'Hủy' : 'Cancel'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowSignOutConfirm(false);
                    signOut();
                    addToast({
                      type: 'info',
                      title: 'Signed Out',
                      message: 'Signed out of session.',
                    });
                    navigate('/');
                  }}
                  className="cursor-pointer rounded-xl bg-[var(--color-danger)] px-4 py-2 text-xs font-semibold text-white shadow-xs transition-colors hover:opacity-90"
                >
                  {language === 'vi' ? 'Đăng xuất' : 'Sign out'}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
};
