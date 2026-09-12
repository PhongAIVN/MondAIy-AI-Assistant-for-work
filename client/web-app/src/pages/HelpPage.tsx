import React from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { Card } from '../components/ui/Card';
import { ConfidenceBadge } from '../components/ui/Badge';
import {
  HelpCircle,
  Compass,
  ShieldCheck,
  Calendar,
  Sparkles,
  MessageSquare
  } from 'lucide-react';

export const HelpPage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="space-y-6 animate-in fade-in duration-200 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <HelpCircle className="w-4 h-4" /> Product Guidance
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            {t.helpPage.title}
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">{t.helpPage.subtitle}</p>
        </div>

        <div className="flex items-center gap-2 text-xs bg-[#E1EBFA] border border-[#E1EBFA] p-2.5 rounded-xl text-[var(--color-primary)] font-bold">
          <ShieldCheck className="w-4 h-4 text-[#2A6B4F]" /> Traceable & Grounded
        </div>
      </div>

      {/* Guidance Cards */}
      <div className="space-y-4">
        {/* Q1: Daily Briefing */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-[var(--color-text-primary)] font-bold text-base font-heading">
            <Compass className="w-5 h-5 text-[var(--color-primary)]" />
            <h3>{t.helpPage.q1}</h3>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{t.helpPage.a1}</p>
        </Card>

        {/* Q2: Confidence System */}
        <Card className="space-y-3">
          <div className="flex items-center gap-2 text-[var(--color-text-primary)] font-bold text-base font-heading">
            <ShieldCheck className="w-5 h-5 text-[#2A6B4F]" />
            <h3>{t.helpPage.q2}</h3>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] whitespace-pre-line leading-relaxed">
            {t.helpPage.a2}
          </p>

          <div className="flex items-center gap-3 pt-2 flex-wrap">
            <ConfidenceBadge level="certain" />
            <ConfidenceBadge level="possible" />
            <ConfidenceBadge level="ask_mentor" />
          </div>
        </Card>

        {/* Q3: Why No Auto Calendar */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-[var(--color-text-primary)] font-bold text-base font-heading">
            <Calendar className="w-5 h-5 text-[var(--color-primary)]" />
            <h3>{t.helpPage.q3}</h3>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{t.helpPage.a3}</p>
        </Card>

        {/* Q4: Source Coverage */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-[var(--color-text-primary)] font-bold text-base font-heading">
            <Sparkles className="w-5 h-5 text-[var(--color-primary)]" />
            <h3>{t.helpPage.q4}</h3>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{t.helpPage.a4}</p>
        </Card>

        {/* Q5: Feedback */}
        <Card className="space-y-2">
          <div className="flex items-center gap-2 text-[var(--color-text-primary)] font-bold text-base font-heading">
            <MessageSquare className="w-5 h-5 text-[var(--color-primary)]" />
            <h3>{t.helpPage.q5}</h3>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">{t.helpPage.a5}</p>
        </Card>
      </div>
    </div>
  );
};
