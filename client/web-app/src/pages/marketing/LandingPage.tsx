import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Sparkles,
} from 'lucide-react';
import { IconEvidence } from '../../components/ui/ProductIcons';
import { useTranslation } from '../../i18n/useTranslation';
import { useRevealOnScroll, useRevealGroup } from '../../lib/scrollReveal';
import { useMagnetic } from '../../hooks/useMagnetic';
import { useWordReveal } from '../../hooks/useWordReveal';
import { HeroVisualField } from '../../components/marketing/HeroVisualField';
import { HeroOrbs } from '../../components/marketing/HeroOrbs';
import {
  FeatheredBleed,
  NatureStage,
} from '../../components/marketing/NatureStages';
import {
  LandingTeamMeet,
  LandingTelegram,
  LandingUseCases,
} from '../../components/marketing/LandingSections';
import { TryChatPage } from './TryChatPage';

export const LandingPage: React.FC = () => {
  const { t } = useTranslation();

  const { containerRef: heroTitleRef, words: heroTitleWords } = useWordReveal<HTMLHeadingElement>(
    t.marketing.heroTitle,
  );
  const getStartedRef = useMagnetic<HTMLAnchorElement>();
  const productRef = useRevealOnScroll<HTMLDivElement>();
  const howItWorksHeadingRef = useRevealOnScroll<HTMLDivElement>();
  const howItWorksGridRef = useRevealGroup<HTMLDivElement>();
  const trustHeadingRef = useRevealOnScroll<HTMLDivElement>();
  const trustGridRef = useRevealGroup<HTMLDivElement>();
  const ctaRef = useRevealOnScroll<HTMLDivElement>();

  return (
    <div>
      {/* Hero: media soft-bleed vào paper, không khung card cứng */}
      <section className="relative isolate min-h-[100dvh] overflow-hidden px-4 sm:px-6 lg:px-8">
        <HeroVisualField />
        <HeroOrbs />

        <div className="relative z-10 mx-auto flex min-h-[100dvh] max-w-7xl flex-col justify-center py-20 lg:py-24">
          <div className="max-w-xl">
            <h1
              ref={heroTitleRef}
              className="max-w-[14ch] text-balance text-[clamp(2.85rem,6vw,4.75rem)] font-semibold leading-[1.08] tracking-[-0.03em] text-ink-900"
            >
              {heroTitleWords.map((word, i) => (
                <span key={i} data-word className="inline-block will-change-[filter,transform,opacity]">
                  {word}
                  {i < heroTitleWords.length - 1 ? ' ' : ''}
                </span>
              ))}
            </h1>

            <div className="hero-content-in hero-content-in-delay-3 mt-8 flex flex-col items-stretch gap-3 sm:mt-10 sm:flex-row sm:items-center">
              <Link
                ref={getStartedRef}
                to="/sign-up"
                className="group inline-flex w-full items-center justify-center gap-2 rounded-full bg-action-solid px-7 py-3.5 text-sm font-semibold text-[var(--color-on-primary)] shadow-e3 transition-[transform,background-color,box-shadow] duration-[var(--d-fast)] ease-[var(--ease-out-quint)] hover:bg-action-hover hover:shadow-e4 active:scale-[0.98] sm:w-auto"
              >
                {t.actions.getStarted}
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white/15 transition-transform duration-[var(--d-base)] ease-[var(--ease-out-quint)] group-hover:translate-x-0.5">
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} />
                </span>
              </Link>

              <a
                href="#product"
                className="inline-flex items-center justify-center rounded-full border border-hairline bg-paper-raised/80 px-6 py-3.5 text-sm font-semibold text-ink-700 backdrop-blur-sm transition-[transform,background-color] duration-[var(--d-fast)] ease-[var(--ease-out-quint)] hover:bg-paper-raised active:scale-[0.98]"
              >
                {t.marketing.exploreProduct}
              </a>
            </div>

            <a
              href="#try"
              className="hero-content-in hero-content-in-delay-3 mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-action-solid transition-colors hover:text-ink-900"
            >
              <Sparkles className="h-4 w-4" strokeWidth={1.5} />
              {t.marketing.tryChatCta}
            </a>
          </div>
        </div>

        <svg
          className="pointer-events-none absolute inset-x-0 bottom-0 z-[5] h-16 w-full sm:h-24"
          viewBox="0 0 1440 100"
          preserveAspectRatio="none"
          aria-hidden
        >
          <path d="M0,50 C360,100 1080,0 1440,50 L1440,100 L0,100 Z" className="fill-paper" />
        </svg>
      </section>

      {/* TryChatPage tự lo mx-auto/max-w/px riêng (dùng chung cho cả route
          /try độc lập) — section ngoài để trơn, không thêm màu/viền/khung
          full-bleed nữa vì mọi section khác trên trang đều trơn như vậy. */}
      <section id="try">
        <TryChatPage embedded />
      </section>

      {/* Split: chữ + đúng 1 ảnh feathered */}
      <section
        id="product"
        className="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8"
      >
        <div
          ref={productRef}
          className="grid items-center gap-10 md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:gap-14"
        >
          <div className="relative z-10 max-w-xl space-y-5 md:py-8">
            <h2 className="max-w-[15ch] text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
              {t.marketing.problemTitle}
            </h2>
            <p className="max-w-[42ch] text-pretty text-base leading-relaxed text-ink-500">
              {t.marketing.problemDesc}
            </p>

            {/* Grid THẬT với hàng chung (label / nội dung), không phải 2 cột flex
                độc lập — trước đây 2 bên "trôi" tự do nên nội dung dài/ngắn khác
                nhau làm 2 cột lệch hàng nhau. Mỗi hàng đặt CẢ HAI bên vào CÙNG
                một grid-row nên chiều cao hàng tự khớp theo bên cao hơn. */}
            <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-4 border-y border-hairline py-8 md:grid-cols-[1fr_auto_1fr] md:grid-rows-[auto_auto] md:items-start md:gap-y-5 md:gap-x-10">
              {/* Thứ tự DOM khớp cặp header+mô tả cho mobile (grid-cols-1 rơi
                  về stack theo đúng thứ tự này) — từ md: trở lên, col-start/
                  row-start ghi đè vị trí thật vào lưới 2 cột, không phụ thuộc
                  thứ tự DOM nữa nên không cần đổi gì thêm ở đó. */}
              <p className="font-heading text-xs font-semibold uppercase tracking-[0.16em] text-danger-solid md:col-start-1 md:row-start-1">Trước khi sử dụng mondaiy</p>
              <p className="text-sm leading-relaxed text-ink-500 md:col-start-1 md:row-start-2">{t.marketing.beforeDesc}</p>

              <div className="hidden w-px bg-hairline md:col-start-2 md:row-span-2 md:row-start-1 md:block" aria-hidden />

              <p className="font-heading text-xs font-semibold uppercase tracking-[0.16em] text-success-solid md:col-start-3 md:row-start-1">Sau khi sử dụng mondaiy</p>
              <p className="text-sm leading-relaxed text-ink-500 md:col-start-3 md:row-start-2">{t.marketing.afterDesc}</p>
            </div>
          </div>

          <FeatheredBleed className="hidden md:block" />
        </div>
      </section>

      <section id="how-it-works" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div ref={howItWorksHeadingRef} className="max-w-2xl space-y-4">
          <h2 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
            {t.marketing.howItWorks}
          </h2>
          <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
            {t.marketing.howItWorksSubtitle}
          </p>
        </div>

        <div ref={howItWorksGridRef} className="mt-12 grid gap-8 md:grid-cols-3">
          {[
            { title: t.marketing.step1Title, desc: t.marketing.step1Desc },
            { title: t.marketing.step2Title, desc: t.marketing.step2Desc },
            { title: t.marketing.step3Title, desc: t.marketing.step3Desc },
          ].map((step) => (
            <div key={step.title} className="space-y-3 border-t border-hairline pt-6">
              <h3 className="text-xl font-semibold tracking-[-0.015em] text-ink-900">{step.title}</h3>
              <p className="text-sm leading-relaxed text-ink-500">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <LandingUseCases />

      <LandingTelegram />

      <section id="trust" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div className="rounded-[28px] bg-wash-porcelain p-8 sm:rounded-[36px] sm:p-12">
          <div ref={trustHeadingRef} className="max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-2 text-sm font-medium text-action-solid">
              <IconEvidence size={16} className="text-action-solid" />
              {t.marketing.trustEyebrow}
            </div>
            <h2 className="text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900">
              {t.marketing.trustTitle}
            </h2>
            <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
              {t.marketing.trustSubtitle}
            </p>
          </div>

          <div ref={trustGridRef} className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { title: t.marketing.trustCard1Title, desc: t.marketing.trustCard1Desc },
              { title: t.marketing.trustCard2Title, desc: t.marketing.trustCard2Desc },
              { title: t.marketing.trustCard3Title, desc: t.marketing.trustCard3Desc },
              { title: t.marketing.trustCard4Title, desc: t.marketing.trustCard4Desc },
            ].map((item) => (
              <div key={item.title} className="space-y-2 rounded-[18px] bg-paper-raised/80 p-4">
                <h3 className="text-base font-semibold text-ink-900">{item.title}</h3>
                <p className="text-sm leading-relaxed text-ink-500">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="pt-8">
            <Link
              to="/policy"
              className="inline-flex items-center gap-2 text-sm font-semibold text-action-solid transition-colors hover:text-ink-900"
            >
              {t.marketing.trustLearnMore}
              <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
            </Link>
          </div>
        </div>
      </section>

      <LandingTeamMeet
        className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8"
        showHeading
      />

      {/* CTA stage: 1 nền */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        <div ref={ctaRef}>
          <NatureStage className="min-h-[400px] sm:min-h-[460px]">
            <div className="flex min-h-[400px] max-w-xl flex-col justify-center px-6 py-14 sm:min-h-[460px] sm:px-12 lg:px-14">
              {/* drop-shadow giữ chữ đọc được trên vùng đá/rêu sáng của ảnh nền
                  (cùng kỹ thuật đã dùng cho wordmark ở BrandLandscapeFooter) —
                  riêng gradient che không đủ ở những điểm ảnh sáng cục bộ. */}
              <h2 className="max-w-[14ch] text-balance text-[clamp(2.4rem,5vw,3.85rem)] font-semibold leading-[1.08] tracking-[-0.025em] text-white drop-shadow-[0_2px_14px_rgba(10,39,68,0.55)]">
                {t.marketing.finalCtaTitle}
              </h2>
              <p className="mt-5 max-w-[36ch] text-base leading-relaxed text-white/85 drop-shadow-[0_1px_8px_rgba(10,39,68,0.5)]">
                {t.marketing.finalCtaSubtitle}
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
                <Link
                  to="/sign-up"
                  className="inline-flex w-full items-center justify-center rounded-full bg-action-solid px-7 py-3.5 text-sm font-semibold text-[var(--color-on-primary)] shadow-e3 transition-[transform,background-color,box-shadow] duration-[var(--d-fast)] ease-[var(--ease-out-quint)] hover:bg-action-hover hover:shadow-e4 active:scale-[0.98] sm:w-auto"
                >
                  {t.marketing.createAccount}
                </Link>
                <Link
                  to="/sign-in"
                  className="inline-flex items-center justify-center rounded-full border border-white/40 bg-white/12 px-6 py-3.5 text-sm font-semibold text-white backdrop-blur-sm transition-[transform,background-color] duration-[var(--d-fast)] ease-[var(--ease-out-quint)] hover:bg-white/20 active:scale-[0.98]"
                >
                  {t.actions.signIn}
                </Link>
              </div>
            </div>
          </NatureStage>
        </div>
      </section>
    </div>
  );
};
