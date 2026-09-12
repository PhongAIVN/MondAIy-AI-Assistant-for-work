import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from '../../i18n/useTranslation';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { useAppStore } from '../../stores/useAppStore';
import {
  Menu,
  Sun,
  Moon,
  Globe,
  ChevronLeft,
  ChevronRight,
  Share2,
  Star,
  ExternalLink,
} from 'lucide-react';
import { NotificationPopover } from './NotificationPopover';
import { IconBell } from '../ui/ProductIcons';
import { useAuthStore } from '../../stores/useAuthStore';
import { useNotificationsStore } from '../../stores/useNotificationsStore';
import { useConversationStore } from '../../stores/useConversationStore';
import { shareServerConversation } from '../../lib/conversationApi';

const NOTIFICATIONS_POLL_MS = 60_000;
interface TopBarProps {
  onOpenMobileMenu: () => void;
  onOpenCommandPalette: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  onOpenMobileMenu,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { addToast } = useAppStore();
  const { theme, setTheme, language, setLanguage } = usePreferencesStore();
  const conversationId = location.pathname.startsWith('/briefing/conversation/')
    ? location.pathname.split('/')[3] || null
    : null;
  const conversation = useConversationStore((state) =>
    conversationId ? state.conversations.find((item) => item.id === conversationId) : undefined,
  );
  const [shareOpen, setShareOpen] = useState(false);
  const [shareVisibility, setShareVisibility] = useState<'private' | 'public'>('private');
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [shareBusy, setShareBusy] = useState(false);

  const { accessToken } = useAuthStore();
  const setFavorite = useConversationStore((state) => state.setFavorite);
  const isPinned = conversation?.isFavorite ?? false;
  const { fetchDue, unreadCount } = useNotificationsStore();
  const unreadNotifications = unreadCount();

  const togglePinnedConversation = async () => {
    if (!conversationId || !accessToken) return;
    try {
      await setFavorite(accessToken, conversationId, !isPinned);
      addToast({
        type: 'success',
        title: language === 'vi'
          ? (!isPinned ? 'Đã ghim vào Favorites' : 'Đã bỏ ghim')
          : (!isPinned ? 'Added to Favorites' : 'Removed from Favorites'),
        message: conversation?.title ?? '',
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không cập nhật được Favorites' : 'Could not update Favorites',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const shareConversation = () => {
    setShareVisibility('private');
    setShareLink(null);
    setShareOpen(true);
  };

  const confirmShare = async () => {
    if (!conversationId || !accessToken) return;
    setShareBusy(true);
    try {
      const result = await shareServerConversation(Number(conversationId), shareVisibility, accessToken);
      setShareLink(result.publicToken ? `${window.location.origin}/shared-chat/${result.publicToken}` : result.publicUrl);
      if (shareVisibility === 'private') setShareOpen(false);
    } catch {
      addToast({
        type: 'error',
        title: language === 'vi' ? 'Không thể cập nhật chia sẻ' : 'Could not update sharing',
        message: language === 'vi' ? 'Vui lòng thử lại.' : 'Please try again.',
      });
    } finally {
      setShareBusy(false);
    }
  };

  const [showNotifications, setShowNotifications] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accessToken) return;
    void fetchDue(accessToken);
    const id = window.setInterval(() => void fetchDue(accessToken), NOTIFICATIONS_POLL_MS);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (notificationsRef.current && !notificationsRef.current.contains(target)) {
        setShowNotifications(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowNotifications(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' || theme === 'black' ? 'light' : 'dark';
    setTheme(nextTheme);
    addToast({
      type: 'info',
      title: 'Theme Updated',
      message: `Switched to ${nextTheme} mode.`,
    });
  };

  const toggleLanguage = () => {
    const nextLang = language === 'en' ? 'vi' : 'en';
    setLanguage(nextLang);
    addToast({
      type: 'info',
      title: 'Language Updated',
      message: `Switched to ${nextLang === 'en' ? 'English' : 'Tiếng Việt'}.`,
    });
  };

  const getWorkspaceLabel = () => {
    if (conversationId) return conversation?.title || '';
    switch (location.pathname) {
      case '/briefing':
      case '/':
        return t.nav.newBriefing || 'New Briefing';
      case '/sources':
        return t.nav.sources;
      case '/notifications':
        return t.nav.notifications;
      case '/settings':
        return t.nav.settings;
      case '/profile':
        return t.nav.profile;
      case '/help':
        return t.nav.help;
      case '/tasks':
        return t.nav.myTasks;
      case '/admin':
        return t.nav.adminPortal;
      default:
        if (location.pathname.startsWith('/briefing/')) {
          return '';
        }
        return 'mondaiy Workspace';
    }
  };

  return (
    <>
    <header className="app-toolbar sticky top-0 z-30 flex h-[60px] items-center justify-between gap-3 border-b border-[var(--color-border)] px-3 text-xs sm:px-6">
      {/* flex-1 + min-w-0 thay cho shrink-0: cụm trái phải co lại được thì
          truncate của tiêu đề mới có tác dụng. Để shrink-0 thì nhan đề dài
          ("Cổng Quản trị Admin") đẩy cụm nút bên phải ra ngoài màn 390px. */}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <button
          onClick={onOpenMobileMenu}
          className="p-1.5 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] lg:hidden"
          aria-label="Open sidebar menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="hidden sm:flex items-center gap-0.5 border-r border-[var(--color-border)] pr-2">
          <button
            onClick={() => navigate(-1)}
            className="p-1 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
            title="Go back"
            aria-label="Navigate back"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => navigate(1)}
            className="p-1 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
            title="Go forward"
            aria-label="Navigate forward"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {getWorkspaceLabel() && (
          <div className="flex min-w-0 items-center gap-2 pl-1">
            <span className="truncate font-extrabold text-[var(--color-text-primary)] font-heading text-sm sm:text-base tracking-tight">
              {getWorkspaceLabel()}
            </span>
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        {conversationId && (
          <>
            <button
              type="button"
              onClick={shareConversation}
              className="p-1.5 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
              title={language === 'vi' ? 'Chia sẻ hội thoại' : 'Share conversation'}
              aria-label={language === 'vi' ? 'Chia sẻ hội thoại' : 'Share conversation'}
            >
              <Share2 className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={togglePinnedConversation}
              className="p-1.5 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
              title={isPinned
                ? language === 'vi' ? 'Bỏ ghim hội thoại' : 'Unpin conversation'
                : language === 'vi' ? 'Ghim hội thoại' : 'Pin conversation'}
              aria-label={isPinned
                ? language === 'vi' ? 'Bỏ ghim hội thoại' : 'Unpin conversation'
                : language === 'vi' ? 'Ghim hội thoại' : 'Pin conversation'}
              aria-pressed={isPinned}
            >
              <Star className="w-4 h-4" fill={isPinned ? 'currentColor' : 'none'} />
            </button>
          </>
        )}
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1 p-1.5 font-bold text-[11px] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
          title="Switch Language"
        >
          <Globe className="w-3.5 h-3.5 text-[var(--color-primary)]" />
          <span className="uppercase">{language}</span>
        </button>

        <button
          onClick={toggleTheme}
          className="p-1.5 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
          title={`Theme: ${theme}`}
        >
          {theme === 'dark' || theme === 'black' ? (
            <Moon className="w-3.5 h-3.5 text-[var(--color-primary)]" />
          ) : (
            <Sun className="w-3.5 h-3.5 text-[var(--color-warning)]" />
          )}
        </button>

        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            onClick={() => setShowNotifications((prev) => !prev)}
            className={`relative p-1.5 text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] ${
              showNotifications ? 'bg-[var(--color-surface-hover)] text-[var(--color-text-primary)]' : ''
            }`}
            title={t.nav.notifications}
            aria-label={t.nav.notifications}
            aria-haspopup="true"
            aria-expanded={showNotifications}
          >
            <IconBell size={14} className="text-current" />
            {unreadNotifications > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[var(--color-danger)] ring-2 ring-[var(--color-topbar-bg)]" />
            )}
          </button>
          {showNotifications && (
            <NotificationPopover
              onViewAll={() => {
                setShowNotifications(false);
                navigate('/notifications');
              }}
            />
          )}
        </div>
      </div>
    </header>
    {shareOpen && conversationId && (
      <div className="fixed inset-0 z-[80] flex items-start justify-end bg-black/20 p-4 pt-16 backdrop-blur-[2px] sm:p-6 sm:pt-20">
        <section className="w-full max-w-[30rem] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 text-[var(--color-text-primary)] shadow-[var(--shadow-e4)]" role="dialog" aria-modal="true" aria-labelledby="share-chat-title">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 id="share-chat-title" className="text-base font-semibold">{language === 'vi' ? 'Chia sẻ đoạn chat' : 'Share chat'}</h2>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{language === 'vi' ? 'Chỉ những tin nhắn hiện có mới được chia sẻ.' : 'Only messages up until now will be shared.'}</p>
            </div>
            <button type="button" onClick={() => setShareOpen(false)} className="text-xl leading-none text-[var(--color-text-muted)]" aria-label={language === 'vi' ? 'Đóng' : 'Close'}>×</button>
          </div>

          <div className="mt-5 overflow-hidden rounded-xl border border-[var(--color-border)]">
            {(['private', 'public'] as const).map((visibility) => {
              const selected = shareVisibility === visibility;
              return (
                <button
                  key={visibility}
                  type="button"
                  onClick={() => {
                    setShareVisibility(visibility);
                    if (visibility === 'private') setShareLink(null);
                  }}
                  className={`flex w-full items-center gap-3 border-b border-[var(--color-border)] p-4 text-left last:border-b-0 ${selected ? 'bg-[var(--color-surface-hover)]' : 'bg-transparent hover:bg-[var(--color-surface-hover)]'}`}
                  aria-pressed={selected}
                >
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full border ${selected ? 'border-[var(--color-primary)]' : 'border-[var(--color-text-muted)]'}`}>
                    {selected && <span className="h-2 w-2 rounded-full bg-[var(--color-primary)]" />}
                  </span>
                  <span>
                    <span className="block text-sm font-medium">{visibility === 'private' ? (language === 'vi' ? 'Riêng tư' : 'Private') : (language === 'vi' ? 'Công khai' : 'Public access')}</span>
                    <span className="mt-0.5 block text-xs text-[var(--color-text-secondary)]">{visibility === 'private' ? (language === 'vi' ? 'Chỉ bạn có quyền truy cập' : 'Only you have access') : (language === 'vi' ? 'Ai có link đều có thể xem' : 'Anyone with the link can view')}</span>
                  </span>
                </button>
              );
            })}
          </div>

          {shareLink && (
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-2">
              <input readOnly value={shareLink} className="min-w-0 flex-1 bg-transparent px-2 text-xs text-[var(--color-text-secondary)] outline-none" aria-label="Shared chat link" />
              <button type="button" onClick={() => void navigator.clipboard?.writeText(shareLink)} className="rounded-lg bg-[var(--color-primary)] px-3 py-2 text-xs font-semibold text-[var(--color-on-primary)]">{language === 'vi' ? 'Sao chép' : 'Copy'}</button>
              <a href={shareLink} target="_blank" rel="noreferrer" className="p-2 text-[var(--color-text-secondary)]" aria-label={language === 'vi' ? 'Mở link' : 'Open link'}><ExternalLink className="h-4 w-4" /></a>
            </div>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <button type="button" onClick={() => setShareOpen(false)} className="rounded-lg px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]">{language === 'vi' ? 'Hủy' : 'Cancel'}</button>
            {!shareLink && <button type="button" disabled={shareBusy} onClick={() => void confirmShare()} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] disabled:opacity-50">{shareBusy ? '…' : language === 'vi' ? 'Xác nhận' : 'Confirm'}</button>}
          </div>
        </section>
      </div>
    )}
    </>
  );
};
