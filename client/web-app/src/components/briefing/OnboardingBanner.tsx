import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../i18n/useTranslation';
import { usePreferencesStore } from '../../stores/usePreferencesStore';
import { CheckCircle2, Circle, ArrowRight, Sparkles } from 'lucide-react';

export const OnboardingBanner: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const onboardingDismissed = usePreferencesStore((s) => s.onboardingDismissed);

  if (onboardingDismissed) return null;

  const steps = [
    { label: t.onboarding.stepWelcome, done: true },
    { label: t.onboarding.stepAbout, done: true },
    { label: t.onboarding.stepConnect, done: false },
  ];

  return (
    <div className="relative bg-[var(--color-accent-soft)] dark:bg-gradient-to-r dark:from-[#0F1F38] dark:to-[#1E4E85] text-[var(--color-text-primary)] dark:text-white p-5 rounded-2xl shadow-xs border border-[var(--color-primary)]/30 dark:border-[var(--color-primary)] space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] dark:text-[#E1EBFA]">
            <Sparkles className="w-4 h-4 text-[var(--color-primary)] dark:text-[#E1EBFA]" /> Setup Progress
          </div>
          <h3 className="text-base font-extrabold font-heading text-[var(--color-text-primary)] dark:text-white">{t.onboarding.title}</h3>
          <p className="text-xs text-[var(--color-text-secondary)] dark:text-white/80">{t.onboarding.subtitle}</p>
        </div>

        <button
          type="button"
          onClick={() => navigate('/onboarding')}
          className="self-start sm:self-center px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] dark:bg-[var(--color-surface-muted)] dark:text-[var(--color-text-primary)] font-bold text-xs rounded-xl hover:bg-[var(--color-primary-hover)] dark:hover:bg-[var(--color-accent-soft)] transition-all flex items-center gap-2 shadow-2xs shrink-0"
        >
          <span>{t.onboarding.continueSetup}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="pt-2 border-t border-[#B8C4D8] dark:border-white/15 flex items-center gap-3 sm:gap-6 flex-wrap text-xs">
        {steps.map((st, idx) => (
          <div key={idx} className="flex items-center gap-1.5 font-medium">
            {st.done ? (
              <CheckCircle2 className="w-4 h-4 text-[var(--color-success)] dark:text-[#8CC3A2]" />
            ) : (
              <Circle className="w-4 h-4 text-[var(--color-text-muted)] dark:text-white/50" />
            )}
            <span className={st.done ? 'text-[var(--color-text-primary)] dark:text-white' : 'text-[var(--color-text-secondary)] dark:text-white/70'}>{st.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
