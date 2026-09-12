import React from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Bell, Home, Menu, Search, Sparkles } from 'lucide-react';
import { MondaiyMark } from '../ui/MondaiyMark';
import { useNotificationsStore } from '../../stores/useNotificationsStore';

interface MobileBottomNavProps {
  onOpenMenu: () => void;
  onOpenSearch: () => void;
}

/** Primary mobile navigation. Kept separate from Sidebar so mobile stays one-thumb friendly. */
export const MobileBottomNav: React.FC<MobileBottomNavProps> = ({ onOpenMenu, onOpenSearch }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const unreadCount = useNotificationsStore((state) => state.unreadCount());
  const isHome = location.pathname === '/briefing' || location.pathname.startsWith('/briefing/');

  return (
    <nav
      aria-label="Mobile navigation"
      className="mobile-bottom-nav fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-[max(10px,env(safe-area-inset-bottom))] pt-2 lg:hidden"
    >
      <div className="flex h-[60px] w-full max-w-[380px] items-center justify-between rounded-[32px] border border-white/70 bg-[color-mix(in_srgb,var(--color-surface)_92%,white)] px-2 shadow-[0_10px_35px_rgba(35,64,77,0.2)] backdrop-blur-xl dark:border-white/10">
        <NavLink
          to="/briefing"
          aria-label="Home"
          aria-current={isHome ? 'page' : undefined}
          className={`mobile-bottom-nav__item ${isHome ? 'is-active' : ''}`}
        >
          <Home size={18} strokeWidth={2.2} />
        </NavLink>
        <button type="button" aria-label="Open menu" className="mobile-bottom-nav__item" onClick={onOpenMenu}>
          <Menu size={19} strokeWidth={2} />
        </button>
        <button
          type="button"
          aria-label="Ask mondaiy"
          className="mobile-bottom-nav__assistant"
          onClick={() => navigate('/briefing')}
        >
          <span className="mobile-bottom-nav__assistant-glow" aria-hidden="true" />
          <MondaiyMark size={30} />
          <Sparkles className="absolute -right-0.5 -top-0.5 text-[var(--color-primary)]" size={11} />
        </button>
        <NavLink
          to="/notifications"
          aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
          className="mobile-bottom-nav__item relative"
        >
          <Bell size={18} strokeWidth={2} />
          {unreadCount > 0 && <span aria-hidden="true" className="mobile-bottom-nav__badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
        </NavLink>
        <button type="button" aria-label="Search" className="mobile-bottom-nav__item" onClick={onOpenSearch}>
          <Search size={18} strokeWidth={2} />
        </button>
      </div>
    </nav>
  );
};
