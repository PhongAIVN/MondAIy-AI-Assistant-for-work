import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  Copy,
  Download,
  FolderOpen,
  PackageOpen,
  PanelsTopLeft,
  Pin,
  Puzzle,
  ShieldCheck,
} from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

export const EXTENSION_DOWNLOAD_PATH = '/downloads/mondaiy-extension-chrome.zip';

export const ExtensionInstallPage: React.FC = () => {
  const { t } = useTranslation();
  const copy = t.extensionInstall;
  const [copied, setCopied] = useState(false);

  const copyExtensionsUrl = async () => {
    try {
      await navigator.clipboard.writeText('chrome://extensions');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const steps = [
    { icon: PackageOpen, title: copy.step1Title, description: copy.step1Desc },
    { icon: PanelsTopLeft, title: copy.step2Title, description: copy.step2Desc },
    { icon: Puzzle, title: copy.step3Title, description: copy.step3Desc },
    { icon: FolderOpen, title: copy.step4Title, description: copy.step4Desc },
    { icon: Pin, title: copy.step5Title, description: copy.step5Desc },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 sm:py-16 lg:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-500 transition-colors hover:text-action-solid"
      >
        <ArrowLeft className="h-4 w-4" strokeWidth={1.5} />
        {t.marketing.blogBackHome}
      </Link>

      <section className="mt-8 overflow-hidden rounded-[2rem] border border-hairline bg-[var(--color-surface)] shadow-[var(--shadow-lg)]">
        <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
          <div className="px-6 py-9 sm:px-10 sm:py-12 lg:px-14 lg:py-16">
            <div className="inline-flex items-center gap-2 rounded-full border border-hairline bg-paper-sunken px-3 py-1.5 text-xs font-semibold text-action-solid">
              <PanelsTopLeft className="h-4 w-4" strokeWidth={1.5} />
              {copy.eyebrow}
            </div>
            <h1 className="mt-6 max-w-[13ch] text-balance text-[clamp(2.5rem,5vw,4.5rem)] font-semibold leading-[0.98] tracking-[-0.045em] text-ink-900">
              {copy.title}
            </h1>
            <p className="mt-6 max-w-[52ch] text-base leading-relaxed text-ink-500 sm:text-lg">
              {copy.subtitle}
            </p>

            <div className="mt-8 flex flex-col items-start gap-3 sm:flex-row sm:items-center">
              <a
                href={EXTENSION_DOWNLOAD_PATH}
                download="mondaiy-extension-chrome.zip"
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-action-solid px-5 py-3 text-sm font-semibold text-white shadow-[var(--shadow-md)] transition-[transform,background-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:bg-action-hover hover:shadow-[var(--shadow-lg)] active:translate-y-0 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-action-solid"
              >
                <Download className="h-4 w-4" strokeWidth={1.7} />
                {copy.download}
              </a>
              <span className="text-xs leading-relaxed text-ink-500">{copy.downloadMeta}</span>
            </div>

            <div className="mt-8 flex flex-wrap gap-x-5 gap-y-2 border-t border-hairline pt-6">
              {[copy.benefit1, copy.benefit2, copy.benefit3].map((benefit) => (
                <span key={benefit} className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-700">
                  <Check className="h-3.5 w-3.5 text-action-solid" strokeWidth={2} />
                  {benefit}
                </span>
              ))}
            </div>
          </div>

          <aside className="relative flex min-h-[24rem] items-center justify-center overflow-hidden border-t border-hairline bg-[#17343F] p-7 text-[#FFFFDD] lg:border-l lg:border-t-0 sm:p-10">
            <div aria-hidden className="absolute inset-0 opacity-30 [background-image:radial-gradient(circle_at_25%_25%,#9BCBD2_0,transparent_38%),radial-gradient(circle_at_78%_75%,#356F83_0,transparent_42%)]" />
            <div className="relative w-full max-w-sm rounded-2xl border border-white/15 bg-white/8 p-5 shadow-2xl backdrop-blur-sm">
              <div className="flex items-center gap-3 border-b border-white/12 pb-4">
                <img src="/mondaiy-mascot.png" alt="" className="h-10 w-10 rounded-xl" />
                <div>
                  <p className="font-semibold text-[#FFFFDD]">mondaiy</p>
                  <p className="text-xs text-[#C8D9D6]">{copy.previewStatus}</p>
                </div>
                <span className="ml-auto rounded-md bg-[#9BCBD2]/15 px-2 py-1 text-[10px] font-semibold text-[#9BCBD2]">
                  MV3
                </span>
              </div>
              <div className="space-y-3 pt-4">
                <div className="rounded-xl bg-[#FFFEDD] p-3 text-[#17343F]">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#55727A]">{copy.previewReminder}</p>
                  <p className="mt-1 text-sm font-semibold">{copy.previewTask}</p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-white/12 p-3">
                    <p className="text-[10px] text-[#9BB3B5]">{copy.previewBadge}</p>
                    <p className="mt-1 text-sm font-semibold">3</p>
                  </div>
                  <div className="rounded-xl border border-white/12 p-3">
                    <p className="text-[10px] text-[#9BB3B5]">{copy.previewSync}</p>
                    <p className="mt-1 text-sm font-semibold text-[#9BCBD2]">{copy.previewReady}</p>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </section>

      <section className="py-14 sm:py-18" aria-labelledby="install-steps-title">
        <div className="grid gap-10 lg:grid-cols-[18rem_minmax(0,1fr)] lg:gap-16">
          <div>
            <p className="text-sm font-semibold text-action-solid">{copy.stepsEyebrow}</p>
            <h2 id="install-steps-title" className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-ink-900">
              {copy.stepsTitle}
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-ink-500">{copy.stepsSubtitle}</p>
            <button
              type="button"
              onClick={() => void copyExtensionsUrl()}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-paper-sunken px-3 py-2 font-mono text-xs font-semibold text-action-solid transition-colors hover:text-ink-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-action-solid"
            >
              chrome://extensions
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              <span className="font-sans">{copied ? copy.copiedUrl : copy.copyUrl}</span>
            </button>
            <p className="mt-1 text-xs text-ink-500">{copy.chromeUrlHint}</p>
          </div>

          <ol className="divide-y divide-hairline border-y border-hairline">
            {steps.map((step, index) => (
              <li key={step.title} className="grid grid-cols-[2.5rem_1fr] gap-4 py-6 sm:grid-cols-[3rem_1fr] sm:gap-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-paper-sunken text-action-solid sm:h-12 sm:w-12">
                  <step.icon className="h-5 w-5" strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-action-solid">{String(index + 1).padStart(2, '0')}</p>
                  <h3 className="mt-1 text-lg font-semibold tracking-[-0.015em] text-ink-900">{step.title}</h3>
                  <p className="mt-1.5 max-w-[58ch] text-sm leading-relaxed text-ink-500">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="grid gap-4 border-t border-hairline py-10 md:grid-cols-2">
        <div className="rounded-2xl bg-paper-sunken p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            <ShieldCheck className="h-5 w-5 text-action-solid" strokeWidth={1.5} />
            {copy.securityTitle}
          </div>
          <p className="mt-3 text-sm leading-relaxed text-ink-500">{copy.securityDesc}</p>
        </div>
        <div className="rounded-2xl border border-hairline p-6">
          <h2 className="text-sm font-semibold text-ink-900">{copy.updateTitle}</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-500">{copy.updateDesc}</p>
        </div>
      </section>
    </div>
  );
};
