import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ChevronDown } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import {
  IconAsk,
  IconChange,
  IconClock,
  IconConfirm,
  IconEvidence,
  IconLock,
  IconMail,
  IconPipeline,
  IconPrivacy,
  IconSettings,
  IconSources,
  IconSynthesize,
  IconUsers,
} from '../../components/ui/ProductIcons';

// Thứ tự khớp đúng policySections trong translations.ts (Scope → Contact).
const SECTION_ICONS = [
  IconSources,
  IconEvidence,
  IconPrivacy,
  IconPipeline,
  IconSynthesize,
  IconLock,
  IconSettings,
  IconClock,
  IconUsers,
  IconChange,
  IconMail,
];

export const PolicyPage: React.FC = () => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleSection = (title: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
  };

  const policies = [
    { icon: IconEvidence, title: t.marketing.policy1Title, desc: t.marketing.policy1Desc },
    { icon: IconConfirm, title: t.marketing.policy2Title, desc: t.marketing.policy2Desc },
    { icon: IconAsk, title: t.marketing.policy3Title, desc: t.marketing.policy3Desc },
    { icon: IconChange, title: t.marketing.policy4Title, desc: t.marketing.policy4Desc },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blogBackHome}
      </Link>

      <header className="mt-8 max-w-2xl space-y-4">
        <h1 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
          {t.marketing.policyTitle}
        </h1>
        <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
          {t.marketing.policySubtitle}
        </p>
      </header>

      <p className="mt-4 text-sm text-ink-500">{t.marketing.policyUpdated}</p>

      <div className="mt-14 grid gap-x-12 gap-y-10 sm:grid-cols-2">
        {policies.map((item) => (
          <div key={item.title} className="space-y-3 border-t border-hairline pt-6">
            <item.icon size={24} />
            <h2 className="text-xl font-semibold tracking-[-0.015em] text-ink-900">{item.title}</h2>
            <p className="max-w-[42ch] text-base leading-relaxed text-ink-500">{item.desc}</p>
          </div>
        ))}
      </div>

      <div className="mt-16 grid gap-x-12 gap-y-10 sm:grid-cols-2">
        {t.marketing.policySections.map((section, sectionIndex) => {
          const Icon = SECTION_ICONS[sectionIndex] ?? IconSources;
          const [preview, ...rest] = section.paragraphs;
          const isExpanded = expanded.has(section.title);
          const hasMore = rest.length > 0;

          return (
            <div key={section.title} className="space-y-3 border-t border-hairline pt-6">
              <Icon size={24} />
              <h2 className="text-xl font-semibold tracking-[-0.015em] text-ink-900">{section.title}</h2>
              <p className="max-w-[42ch] text-base leading-relaxed text-ink-500 whitespace-pre-line">
                {preview}
              </p>

              {hasMore && isExpanded && (
                <div className="space-y-3">
                  {rest.map((paragraph, index) => (
                    <p
                      key={index}
                      className="max-w-[42ch] text-base leading-relaxed text-ink-500 whitespace-pre-line"
                    >
                      {paragraph}
                    </p>
                  ))}
                </div>
              )}

              {hasMore && (
                <button
                  type="button"
                  onClick={() => toggleSection(section.title)}
                  className="inline-flex items-center gap-1 text-sm font-semibold text-action-solid transition-colors hover:text-ink-900"
                  aria-expanded={isExpanded}
                >
                  {isExpanded ? t.marketing.policyCollapse : t.marketing.policyExpand}
                  <ChevronDown
                    className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    strokeWidth={2}
                  />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
