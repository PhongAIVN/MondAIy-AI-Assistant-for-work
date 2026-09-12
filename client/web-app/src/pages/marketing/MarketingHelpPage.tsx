import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  Calendar,
  Compass,
  HelpCircle,
  MessageSquare,
  NotebookPen,
  Repeat,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { ConfidenceBadge } from '../../components/ui/Badge';

export const MarketingHelpPage: React.FC = () => {
  const { t } = useTranslation();

  const faqs = [
    { icon: Compass, q: t.helpPage.q1, a: t.helpPage.a1 },
    { icon: ShieldCheck, q: t.helpPage.q2, a: t.helpPage.a2, showBadges: true },
    { icon: Calendar, q: t.helpPage.q3, a: t.helpPage.a3 },
    { icon: Sparkles, q: t.helpPage.q4, a: t.helpPage.a4 },
    { icon: MessageSquare, q: t.helpPage.q5, a: t.helpPage.a5 },
    { icon: NotebookPen, q: t.helpPage.q6, a: t.helpPage.a6 },
    { icon: Repeat, q: t.helpPage.q7, a: t.helpPage.a7 },
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blogBackHome}
      </Link>

      <header className="mt-8 space-y-4">
        <div className="inline-flex items-center gap-2 text-sm font-medium text-action-solid">
          <HelpCircle className="h-4 w-4" strokeWidth={1.5} />
          {t.marketing.help}
        </div>
        <h1 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
          {t.marketing.helpPageTitle}
        </h1>
        <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
          {t.marketing.helpPageSubtitle}
        </p>
      </header>

      <div className="mt-14 space-y-10">
        {faqs.map((item) => (
          <section key={item.q} className="space-y-3 border-t border-hairline pt-8">
            <div className="flex items-center gap-2">
              <item.icon className="h-5 w-5 text-action-solid" strokeWidth={1.5} />
              <h2 className="text-xl font-semibold tracking-[-0.015em] text-ink-900">{item.q}</h2>
            </div>
            <p className="max-w-[52ch] whitespace-pre-line text-base leading-relaxed text-ink-500">
              {item.a}
            </p>
            {item.showBadges && (
              <div className="flex flex-wrap items-center gap-3 pt-1">
                <ConfidenceBadge level="certain" />
                <ConfidenceBadge level="possible" />
                <ConfidenceBadge level="ask_mentor" />
              </div>
            )}
          </section>
        ))}
      </div>

      <p className="mt-14 border-t border-hairline pt-8 text-sm text-ink-500">
        <Link to="/policy" className="font-semibold text-action-solid hover:text-ink-900">
          {t.marketing.policy}
        </Link>
        {' · '}
        <Link to="/sign-up" className="font-semibold text-action-solid hover:text-ink-900">
          {t.marketing.createAccount}
        </Link>
      </p>
    </div>
  );
};
