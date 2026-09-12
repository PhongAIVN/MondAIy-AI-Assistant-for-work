import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { usePreferencesStore, type ReminderLeadTime } from '../stores/usePreferencesStore';
import { useAuthStore } from '../stores/useAuthStore';
import { useAppStore } from '../stores/useAppStore';
import { useTranslation } from '../i18n/useTranslation';
import { useMotionEnabled } from '../hooks/useMotionEnabled';
import { PAGE_MOTION } from '../lib/pageMotion';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Toggle } from '../components/ui/Toggle';
import {
  Compass,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  LogOut,
  Sparkles,
  Layers,
  Lock,
  ExternalLink,
} from 'lucide-react';
import { resolveBrandIcon } from '../components/ui/BrandIcons';
import {
  listConnections,
  createConnectIntent,
  type ConnectionProvider,
  type ConnectionStatus,
} from '../lib/connectionsApi';
import { PROVIDER_LABEL } from '../types/pipeline';
import { updateReminderPreferences } from '../lib/reminderApi';

type WizardSourceKey = 'discord' | 'jira' | 'email';

const REAL_PROVIDER: Record<WizardSourceKey, ConnectionProvider> = {
  discord: 'discord',
  jira: 'jira',
  email: 'google',
};

type StepId = 'welcome' | 'about' | 'connect' | 'done';
type CompletionMode = 'configured' | 'browse';

/** '07:00 AM' -> 7, '09:00 PM' -> 21 — khớp field giờ 0-23 backend (daily_brief_hour). */
function parseBriefingHour(value: string): number {
  const match = /^(\d{1,2}):(\d{2})\s*(AM|PM)$/i.exec(value.trim());
  if (!match) return 7;
  let hour = Number(match[1]) % 12;
  if (match[3].toUpperCase() === 'PM') hour += 12;
  return hour;
}

export const OnboardingPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const o = t.onboarding;
  const motionEnabled = useMotionEnabled();
  const { briefingPreferences, updateBriefingPreferences, updateNotificationPreferences, dismissOnboarding } =
    usePreferencesStore();
  const accessToken = useAuthStore((s) => s.accessToken);
  const signOut = useAuthStore((s) => s.signOut);
  const { addToast } = useAppStore();

  const handleLeaveSetup = () => {
    signOut();
    navigate('/sign-in', { replace: true });
  };

  const steps = useMemo(
    () =>
      [
        { id: 'welcome' as const, title: o.stepWelcome, icon: Compass },
        { id: 'about' as const, title: o.stepAbout, icon: Sparkles },
        { id: 'connect' as const, title: o.stepConnect, icon: Layers },
        { id: 'done' as const, title: o.stepDone, icon: CheckCircle2 },
      ] satisfies Array<{ id: StepId; title: string; icon: typeof Compass }>,
    [o],
  );

  const connectStepIndex = steps.findIndex((s) => s.id === 'connect');

  // Quay lại từ OAuth thật (?status=...&provider=...) — nhảy thẳng về step Connect
  // thay vì reset về step 1, cùng cơ chế query SourceLibraryPage.tsx đang dùng.
  const initialStepIndex = useMemo(() => {
    const params = new URLSearchParams(location.search);
    if (!params.get('status')) return 0;
    return connectStepIndex === -1 ? 0 : connectStepIndex;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [currentStepIndex, setCurrentStepIndex] = useState(initialStepIndex);
  const currentStepId: StepId = steps[currentStepIndex]?.id ?? 'welcome';

  const [consentGiven, setConsentGiven] = useState(true);
  const [connections, setConnections] = useState<ConnectionStatus[]>([]);
  const isProviderConnected = (provider: ConnectionProvider) =>
    connections.some((c) => c.provider === provider && c.connected);
  const googleConnected = isProviderConnected('google');

  // Không còn bước riêng để chỉnh — giữ nguyên giá trị mặc định đã seed sẵn,
  // vẫn đồng bộ lên server ở bước Hoàn tất như trước.
  const [reminderLeadTime] = useState<ReminderLeadTime>('24h');
  const [briefingTime] = useState(briefingPreferences.briefingTime || '07:00 AM');

  // Trạng thái connect thật — đọc lúc vào trang (và lại lúc quay về từ OAuth ở effect dưới).
  useEffect(() => {
    if (!accessToken) return;
    void listConnections(accessToken).then((res) => setConnections(res.connections));
  }, [accessToken]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const status = params.get('status');
    const provider = params.get('provider') as ConnectionProvider | null;
    if (!status || !provider) return;

    addToast({
      type: status === 'connected' ? 'success' : 'error',
      title: status === 'connected' ? t.sourcesPage.connectSuccessTitle : t.sourcesPage.connectFailTitle,
      message:
        status === 'connected'
          ? t.sourcesPage.connectSuccessMsg.replace('{provider}', PROVIDER_LABEL[provider] || provider)
          : t.sourcesPage.connectFailMsg.replace('{provider}', PROVIDER_LABEL[provider] || provider),
    });
    if (accessToken) void listConnections(accessToken).then((res) => setConnections(res.connections));
    navigate('/onboarding', { replace: true });
    // chỉ đọc query redirect đúng 1 lần lúc mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const otherSources = useMemo(
    () =>
      [
        { id: 'discord' as const, name: o.sourceDiscord, desc: o.sourceDiscordDesc },
        { id: 'jira' as const, name: o.sourceJira, desc: o.sourceJiraDesc },
      ] as const,
    [o],
  );

  const handleConnect = async (wizardSource: WizardSourceKey) => {
    const provider = REAL_PROVIDER[wizardSource];
    if (!provider || !accessToken) return;
    try {
      const returnUrl = `${window.location.origin}${window.location.pathname}`;
      const { authorizeUrl } = await createConnectIntent(provider, returnUrl, accessToken);
      window.location.href = authorizeUrl;
    } catch {
      addToast({
        type: 'error',
        title: t.sourcesPage.connectFailTitle,
        message: t.sourcesPage.connectFailMsg.replace('{provider}', PROVIDER_LABEL[provider] || provider),
      });
    }
  };

  const finishOnboarding = (mode: CompletionMode) => {
    dismissOnboarding();
    addToast({
      type: 'success',
      title: o.completeToastTitle,
      message: mode === 'browse' ? o.browseToastMsg : o.completeToastMsg,
    });

    const returnTo = (location.state as { returnTo?: string } | null)?.returnTo;
    navigate(mode === 'browse' || !returnTo || returnTo === '/onboarding' ? '/briefing' : returnTo);
  };

  const handleNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    } else {
      void handleComplete();
    }
  };

  const handleBack = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  };

  /** Ghi nhận các lựa chọn thật (hoặc default đã seed sẵn) khi user đi hết luồng cấu hình. */
  const handleComplete = async () => {
    updateBriefingPreferences({ briefingTime });
    updateNotificationPreferences({ reminderLeadTime });

    if (accessToken) {
      try {
        await updateReminderPreferences({ dailyBriefHour: parseBriefingHour(briefingTime) }, accessToken);
      } catch {
        addToast({
          type: 'error',
          title: o.completeToastTitle,
          message: o.remindersSyncFailMsg,
        });
      }
    }

    finishOnboarding('configured');
  };

  const goToStep = (index: number) => {
    setCurrentStepIndex(index);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-200">
      <div className="bg-[#0F1F38] text-white p-6 rounded-2xl border border-[#2563A6] shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[#E1EBFA] mb-1">
            <Sparkles className="w-4 h-4 text-[#E1EBFA]" /> {o.setupEyebrow}
          </div>
          <h1 className="text-3xl font-semibold text-white font-heading">{o.setupTitle}</h1>
          <p className="text-xs text-[#E1EBFA]/80 mt-1">
            {o.stepOf
              .replace('{current}', String(currentStepIndex + 1))
              .replace('{total}', String(steps.length))
              .replace('{title}', steps[currentStepIndex].title)}
          </p>
        </div>

        <button
          type="button"
          onClick={handleLeaveSetup}
          className="self-start sm:self-center px-3 py-1.5 bg-white/10 text-white hover:bg-white/20 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors"
        >
          <LogOut className="w-4 h-4" /> {t.nav.signOut}
        </button>
      </div>

      <div className="grid grid-cols-4 gap-1.5 bg-white p-2 rounded-2xl border border-[#D5DDEB]">
        {steps.map((st, index) => {
          const StepIcon = st.icon;
          const isActive = index === currentStepIndex;
          const isDone = index < currentStepIndex;

          return (
            <button
              key={st.id}
              type="button"
              onClick={() => goToStep(index)}
              className={`p-2 rounded-xl flex flex-col items-center gap-1 text-[10px] font-bold transition-all ${
                isActive
                  ? 'bg-[#0F1F38] text-white shadow-xs'
                  : isDone
                    ? 'bg-[#DFF0E6] text-[#2A6B4F] border border-[#C4DDCB]'
                    : 'bg-[#EDF2FB] text-[#5A6A85] hover:bg-[#EBEFF8]'
              }`}
            >
              <StepIcon className="w-3.5 h-3.5" />
              <span className="truncate max-w-full hidden sm:inline">{st.title}</span>
              <span className="sm:hidden">{index + 1}</span>
            </button>
          );
        })}
      </div>

      <Card className="p-6 sm:p-8 space-y-6 overflow-hidden">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.div
          key={currentStepId}
          initial={motionEnabled ? { opacity: 0, y: 12 } : false}
          animate={{ opacity: 1, y: 0, transition: { duration: PAGE_MOTION.enterMs / 1000, ease: PAGE_MOTION.ease } }}
          exit={motionEnabled ? { opacity: 0, y: -8, transition: { duration: PAGE_MOTION.exitMs / 1000, ease: PAGE_MOTION.ease } } : { opacity: 1 }}
        >
        {currentStepId === 'welcome' && (
          <div className="space-y-4">
            <div className="w-12 h-12 bg-[#E1EBFA] text-[#2563A6] rounded-2xl flex items-center justify-center font-bold">
              <Compass className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-semibold text-[#0F1F38] font-heading">{o.welcomeTitle}</h2>
            <p className="text-xs text-[#5A6A85] leading-relaxed">{o.welcomeBody}</p>
          </div>
        )}

        {currentStepId === 'about' && (
          <div className="space-y-4">
            <div className="w-12 h-12 bg-[#E1EBFA] text-[#2563A6] rounded-2xl flex items-center justify-center font-bold">
              <Sparkles className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-semibold text-[#0F1F38] font-heading">{o.aboutTitle}</h2>
            <p className="text-xs text-[#5A6A85] leading-relaxed">{o.aboutBody}</p>

            <div className="space-y-2 pt-2">
              {[
                [o.aboutPoint1Title, o.aboutPoint1Body],
                [o.aboutPoint2Title, o.aboutPoint2Body],
                [o.aboutPoint3Title, o.aboutPoint3Body],
              ].map(([pointTitle, pointBody]) => (
                <div
                  key={pointTitle}
                  className="p-3 bg-[#EDF2FB] border border-[#D5DDEB] rounded-xl text-xs"
                >
                  <strong className="text-[#0F1F38] block font-heading">{pointTitle}</strong>
                  <span className="text-[#5A6A85]">{pointBody}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {currentStepId === 'connect' && (
          <div className="space-y-4">
            <div className="w-12 h-12 bg-[#E1EBFA] text-[#2563A6] rounded-2xl flex items-center justify-center font-bold">
              <Layers className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-semibold text-[#0F1F38] font-heading">{o.connectTitle}</h2>
            <p className="text-xs text-[#5A6A85]">{o.connectBody}</p>

            <div
              data-testid="google-onboarding-choice"
              className="flex items-center justify-between gap-3 p-4 bg-[#E1EBFA]/60 border border-[#2563A6]/35 rounded-xl"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2.5 bg-white border border-[#D5DDEB] rounded-lg shrink-0">
                  {resolveBrandIcon('google', 'w-5 h-5 text-[#2563A6]')}
                </div>
                <div className="min-w-0 text-xs">
                  <span className="font-bold text-[#0F1F38] block">{o.connectGoogleTitle}</span>
                  <span className="text-[#5A6A85] block">{o.connectGoogleDesc}</span>
                </div>
              </div>
              <button
                type="button"
                disabled={googleConnected}
                onClick={() => void handleConnect('email')}
                className={`px-3.5 py-2 rounded-lg text-xs font-bold transition-all shrink-0 ${
                  googleConnected
                    ? 'bg-[#DFF0E6] text-[#2A6B4F] border border-[#C4DDCB]'
                    : 'bg-[#0F1F38] text-white hover:bg-[#1E4E85]'
                }`}
              >
                {googleConnected ? o.connected : o.connectGoogleCta}
              </button>
            </div>

            <div
              data-testid="browse-onboarding-choice"
              className="flex items-center justify-between gap-3 p-4 bg-[#E1EBFA]/60 border border-[#2563A6]/35 rounded-xl"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2.5 bg-white border border-[#D5DDEB] rounded-lg shrink-0">
                  <Compass className="w-5 h-5 text-[#2563A6]" />
                </div>
                <div className="min-w-0 text-xs">
                  <span className="font-bold text-[#0F1F38] block">{o.browseTitle}</span>
                  <span className="text-[#5A6A85] block">{o.browseDesc}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => finishOnboarding('browse')}
                className="px-3.5 py-2 rounded-lg text-xs font-bold transition-all shrink-0 bg-[#0F1F38] text-white hover:bg-[#1E4E85]"
              >
                {o.browseCta}
              </button>
            </div>

            <div className="space-y-2 pt-1">
              <span className="text-[11px] font-bold uppercase tracking-wide text-[#5A6A85]">
                {o.otherSourcesLabel}
              </span>
              <div className="space-y-2 text-xs">
                {otherSources.map((src) => {
                  const provider = REAL_PROVIDER[src.id];
                  const isConnected = isProviderConnected(provider);

                  return (
                    <div
                      key={src.id}
                      className="flex items-center justify-between gap-3 p-4 bg-[#EDF2FB] border border-[#D5DDEB] rounded-xl"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2.5 bg-white border border-[#D5DDEB] rounded-lg shrink-0">
                          {resolveBrandIcon(src.id, 'w-5 h-5 text-[#2563A6]')}
                        </div>
                        <div className="min-w-0 text-xs">
                          <span className="font-bold text-[#0F1F38] block">{src.name}</span>
                          <span className="text-[#5A6A85] block">{src.desc}</span>
                        </div>
                      </div>

                      <button
                        type="button"
                        disabled={isConnected}
                        onClick={() => void handleConnect(src.id)}
                        className={`px-3.5 py-2 rounded-lg text-xs font-bold transition-all shrink-0 ${
                          isConnected
                            ? 'bg-[#DFF0E6] text-[#2A6B4F] border border-[#C4DDCB]'
                            : 'bg-[#0F1F38] text-white hover:bg-[#1E4E85]'
                        }`}
                      >
                        {isConnected ? o.connected : o.connect}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="pt-2 border-t border-[#D5DDEB] space-y-3">
              <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-[#5A6A85]">
                <Lock className="w-3.5 h-3.5" /> {o.privacyTitle}
              </span>
              <p className="text-xs text-[#5A6A85] leading-relaxed">{o.privacyBody}</p>
              <div className="flex items-center gap-3 p-4 bg-[#EDF2FB] border border-[#D5DDEB] rounded-xl">
                <Toggle checked={consentGiven} onChange={setConsentGiven} aria-label={o.privacyConsentTitle} />
                <div className="text-xs space-y-0.5">
                  <span className="font-bold text-[#0F1F38] block">{o.privacyConsentTitle}</span>
                  <span className="text-[#5A6A85] block">{o.privacyConsentHint}</span>
                </div>
              </div>
              <a
                href="/policy"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#2563A6] hover:underline"
              >
                {o.policyLinkLabel} <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        )}

        {currentStepId === 'done' && (
          <div className="space-y-4 text-center py-4">
            <div className="w-16 h-16 bg-[#DFF0E6] text-[#2A6B4F] rounded-full flex items-center justify-center mx-auto border-2 border-[#C4DDCB]">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-3xl font-semibold text-[#0F1F38] font-heading">{o.doneTitle}</h2>
            <p className="text-xs text-[#5A6A85] max-w-md mx-auto">{o.doneBody}</p>

            <div className="pt-4">
              <Button
                variant="primary"
                size="lg"
                icon={<Sparkles className="w-4 h-4 text-[#E1EBFA]" />}
                onClick={() => void handleComplete()}
                className="mx-auto shadow-md"
              >
                {o.launchBriefing}
              </Button>
            </div>
          </div>
        )}
        </motion.div>
      </AnimatePresence>

        <div className="pt-6 border-t border-[#D5DDEB] flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            icon={<ArrowLeft className="w-4 h-4" />}
            onClick={handleBack}
            disabled={currentStepIndex === 0}
          >
            {o.back}
          </Button>

          <div className="flex items-center gap-2">
            {currentStepId !== 'done' && (
              <>
                <Button
                  variant="primary"
                  size="sm"
                  icon={<ArrowRight className="w-4 h-4" />}
                  onClick={handleNext}
                  disabled={currentStepId === 'connect' && !googleConnected}
                >
                  {o.continue}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};
