import React, { useEffect, useState } from 'react';
import { ArrowUp } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';

const SHOW_AFTER_PX = 480;

/** Nút cuộn lên đầu trang, chỉ hiện sau khi người dùng đã cuộn xuống một đoạn. */
export const BackToTopButton: React.FC = () => {
  const { t } = useTranslation();
  const motionEnabled = useMotionEnabled();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => setVisible(window.scrollY > SHOW_AFTER_PX);
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: motionEnabled ? 'smooth' : 'auto' })}
      aria-label={t.marketing.backToTop}
      title={t.marketing.backToTop}
      className="fixed bottom-6 right-4 z-30 inline-flex h-11 w-11 items-center justify-center rounded-full bg-action-solid text-[var(--color-on-primary)] shadow-[var(--shadow-lg)] transition-transform hover:-translate-y-0.5 hover:bg-action-hover focus:outline-none focus:ring-2 focus:ring-[var(--color-focus-ring)] focus:ring-offset-2 sm:bottom-8 sm:right-6"
    >
      <ArrowUp className="h-5 w-5" strokeWidth={2} />
    </button>
  );
};
