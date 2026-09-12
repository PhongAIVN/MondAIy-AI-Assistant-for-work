import React from 'react';
import { ArrowUpRight, CheckCircle2, Clock3, Quote, Send } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { useRevealGroup } from '../../lib/scrollReveal';
import {
  IconAsk,
  IconChange,
  IconConfirm,
  IconConflict,
  IconEvidence,
  IconSynthesize,
} from '../ui/ProductIcons';
import { MondaiyMark } from '../ui/MondaiyMark';
import photoAn from '../../assets/anhoaithai.jpg';
import photoPhong from '../../assets/nguyenvanphong.jpg';
import photoNhi from '../../assets/lethiyennhi.jpg';
import photoDung from '../../assets/nguyenducdung.jpg';
import icmCanopy from '../../assets/icm-canopy.webp';
import icmForestPath from '../../assets/icm-forest-path.webp';
import icmWaterGrass from '../../assets/icm-water-grass.webp';
import icmGreenForest from '../../assets/icm-green-forest.webp';
import icmLakeReflection from '../../assets/icm-lake-reflection.webp';

const sectionTitle =
  'text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-ink-900';

export const LandingUseCases: React.FC = () => {
  const { t } = useTranslation();
  // Khớp đúng motion với LandingTeamMeet ("Gặp đội ngũ vận hành"): chỉ
  // hoverLift (nhấc nhẹ + scale khi hover), bỏ tilt 3D — tilt là thứ khác biệt
  // duy nhất giữa 2 nhóm card trước đây.
  const gridRef = useRevealGroup<HTMLDivElement>({ hoverLift: true });

  const items = [
    { icon: IconSynthesize, title: t.marketing.uc1Title, desc: t.marketing.uc1Desc, image: icmLakeReflection, layout: 'md:col-span-7', overlay: 'from-action-tint via-action-tint/90 to-action-tint/25' },
    { icon: IconChange, title: t.marketing.uc2Title, desc: t.marketing.uc2Desc, image: icmForestPath, layout: 'md:col-span-5', overlay: 'from-wash-sage via-wash-sage/92 to-wash-sage/30' },
    { icon: IconConflict, title: t.marketing.uc3Title, desc: t.marketing.uc3Desc, image: icmCanopy, layout: 'md:col-span-5', overlay: 'from-wash-apricot via-wash-apricot/92 to-wash-apricot/30' },
    { icon: IconAsk, title: t.marketing.uc4Title, desc: t.marketing.uc4Desc, image: icmGreenForest, layout: 'md:col-span-7', overlay: 'from-wash-porcelain via-wash-porcelain/90 to-wash-porcelain/25' },
    { icon: IconConfirm, title: t.marketing.uc5Title, desc: t.marketing.uc5Desc, image: icmWaterGrass, layout: 'md:col-span-12', overlay: 'from-paper-sunken via-paper-sunken/88 to-paper-sunken/18' },
  ];

  return (
    <section id="use-cases" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
      <div className="max-w-2xl space-y-4">
        <h2 className={sectionTitle}>{t.marketing.useCasesTitle}</h2>
        <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
          {t.marketing.useCasesSubtitle}
        </p>
      </div>

      <div ref={gridRef} className="mt-12 grid gap-4 [perspective:1000px] md:grid-cols-12">
        {items.map((item) => (
          <div
            key={item.title}
            className={`group relative isolate min-h-[220px] overflow-hidden rounded-[24px] ring-1 ring-hairline ${item.layout}`}
          >
            <img
              src={item.image}
              alt=""
              aria-hidden
              loading="lazy"
              decoding="async"
              className="absolute inset-0 h-full w-full object-cover opacity-72 saturate-[0.82]"
            />
            <div className={`absolute inset-0 bg-gradient-to-r ${item.overlay}`} />
            <div className="relative z-10 flex min-h-[220px] max-w-[34rem] flex-col justify-between p-6 sm:p-7">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-paper-raised/75 text-action-solid shadow-e1 backdrop-blur-sm">
                <item.icon size={23} />
              </span>
              <div className="mt-12 space-y-2.5">
                <h3 className="text-xl font-semibold text-ink-900">{item.title}</h3>
                <p className="max-w-[42ch] text-sm leading-relaxed text-ink-700">{item.desc}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

const TELEGRAM_BOT_URL = 'https://t.me/mondaiy_bot';

export const LandingTelegram: React.FC = () => {
  const { t } = useTranslation();

  return (
    <section id="telegram" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
      {/* bg-[#23404D] cố định (không phải token bg-ink-900) — ink-900 là thang
          màu CHỮ, đảo ngược theo theme (đậm ở sáng, nhạt ở tối); dùng làm nền
          card khiến nền lật màu ở dark mode trong khi chữ trắng cố định bên
          trong thì không, làm mất hẳn tương phản. */}
      <div className="relative isolate overflow-hidden rounded-[28px] bg-[#23404D] px-6 py-8 shadow-e3 sm:rounded-[36px] sm:px-10 sm:py-12 lg:px-14">
        <div
          className="pointer-events-none absolute -right-24 -top-32 h-80 w-80 rounded-full bg-action-solid/25 blur-3xl"
          aria-hidden
        />
        <div className="relative grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.7fr)] lg:gap-16">
          <div className="max-w-2xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-sm font-medium text-white/80">
              <Send className="h-4 w-4" strokeWidth={1.7} aria-hidden />
              {t.marketing.telegramLabel}
            </div>
            <h2 className="max-w-[18ch] text-balance text-[clamp(2.15rem,4vw,3.15rem)] font-semibold leading-[1.12] tracking-[-0.025em] text-white">
              {t.marketing.telegramTitle}
            </h2>
            <p className="mt-5 max-w-[52ch] text-base leading-relaxed text-white/65">
              {t.marketing.telegramSubtitle}
            </p>
            <a
              href={TELEGRAM_BOT_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t.marketing.telegramCtaAria}
              className="group mt-8 inline-flex items-center gap-2 rounded-full bg-white px-6 py-3.5 text-sm font-semibold text-ink-900 shadow-e2 transition-[transform,box-shadow] duration-[var(--d-fast)] ease-[var(--ease-out-quint)] hover:-translate-y-0.5 hover:shadow-e4 active:translate-y-0"
            >
              {t.marketing.telegramCta}
              <ArrowUpRight
                className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                strokeWidth={1.7}
                aria-hidden
              />
            </a>
          </div>

          <div className="rounded-[24px] bg-paper-raised p-5 shadow-e4 ring-1 ring-white/10 sm:p-6">
            <div className="flex items-center gap-3 border-b border-hairline pb-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#229ED9] text-white">
                <Send className="h-5 w-5" strokeWidth={1.7} aria-hidden />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink-900">mondaiy bot</p>
                <p className="text-xs text-success-solid">{t.marketing.telegramStatus}</p>
              </div>
            </div>
            <div className="mt-5 rounded-[18px] bg-action-tint p-4">
              <p className="text-sm font-semibold text-ink-900">{t.marketing.telegramPreviewTitle}</p>
              <div className="mt-3 space-y-2.5 text-sm text-ink-700">
                <p className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 shrink-0 text-action-solid" aria-hidden />
                  {t.marketing.telegramPreviewDue}
                </p>
                <p className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-action-solid" aria-hidden />
                  {t.marketing.telegramPreviewWaiting}
                </p>
              </div>
            </div>
            <p className="mt-4 text-xs leading-relaxed text-ink-400">
              {t.marketing.telegramPreviewNote}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export const LandingTeamMeet: React.FC<{ className?: string; showHeading?: boolean }> = ({
  className = '',
  showHeading = true,
}) => {
  const { t } = useTranslation();
  const gridRef = useRevealGroup<HTMLDivElement>({ hoverLift: true });

  const members = [
    {
      name: 'Thái Hoài An',
      handle: '@thaihoaian',
      role: t.marketing.teamRolePm,
      blurb: t.marketing.teamBlurbAn,
      photo: photoAn,
      portfolio: 'https://ahtportfolio.vercel.app/',
    },
    {
      name: 'Nguyễn Văn Phong',
      handle: '@nvphong',
      role: t.marketing.teamRoleTech,
      blurb: t.marketing.teamBlurbPhong,
      photo: photoPhong,
      portfolio: 'https://nguyenvanphong.net/',
    },
    {
      name: 'Lê Thị Yến Nhi',
      handle: '@yennih',
      role: t.marketing.teamRoleDesign,
      blurb: t.marketing.teamBlurbNhi,
      photo: photoNhi,
      portfolio: 'https://portfoliolynn.vercel.app/',
    },
    {
      name: 'Nguyễn Đức Dũng',
      handle: '@ducdung',
      role: t.marketing.teamRoleQc,
      blurb: t.marketing.teamBlurbDung,
      photo: photoDung,
      portfolio: 'https://www.nddung.io.vn/',
    },
  ];

  return (
    <section id="team" className={className}>
      {showHeading ? (
        <h2 className={`mb-8 ${sectionTitle}`}>{t.marketing.blogMeetTeam}</h2>
      ) : null}
      <div ref={gridRef} className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {members.map((member) => (
          <article
            key={member.name}
            className="flex h-full min-h-[240px] flex-col rounded-[28px] bg-paper-raised p-7 shadow-e2 ring-1 ring-hairline"
          >
            <Quote
              className="mb-5 h-7 w-7 shrink-0 text-ink-400/55"
              strokeWidth={1.4}
              aria-hidden
            />
            <div className="flex min-h-0 flex-1 flex-col">
              <p className="line-clamp-4 text-[15px] leading-relaxed text-ink-700">{member.blurb}</p>
              <p className="mt-3 text-sm text-ink-400">{member.role}</p>
            </div>
            <div className="mt-8 flex items-center gap-3">
              <a
                href={member.portfolio}
                target="_blank"
                rel="noreferrer"
                aria-label={`${member.name} portfolio`}
                className="group/member flex min-w-0 flex-1 items-center gap-3 rounded-[16px] outline-none transition-transform duration-200 hover:-translate-y-px focus-visible:ring-2 focus-visible:ring-action-solid focus-visible:ring-offset-2 active:translate-y-0"
              >
                <img
                  src={member.photo}
                  alt={member.name}
                  className="h-11 w-11 shrink-0 rounded-[14px] object-cover ring-1 ring-hairline"
                  loading="lazy"
                  decoding="async"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink-900 underline-offset-4 group-hover/member:underline">
                    {member.name}
                  </p>
                  <p className="truncate text-sm text-ink-400">{member.handle}</p>
                </div>
                <ArrowUpRight
                  size={16}
                  className="shrink-0 text-ink-400 transition-colors group-hover/member:text-action-solid"
                  aria-hidden
                />
              </a>
              <MondaiyMark size={22} className="shrink-0 opacity-70" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};

export const LandingPolicy: React.FC = () => {
  const { t } = useTranslation();

  const policies = [
    { icon: IconEvidence, title: t.marketing.policy1Title, desc: t.marketing.policy1Desc },
    { icon: IconConfirm, title: t.marketing.policy2Title, desc: t.marketing.policy2Desc },
    { icon: IconAsk, title: t.marketing.policy3Title, desc: t.marketing.policy3Desc },
    { icon: IconChange, title: t.marketing.policy4Title, desc: t.marketing.policy4Desc },
  ];

  return (
    <section id="policy" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
      <div className="rounded-[28px] bg-wash-sage/80 p-8 sm:rounded-[36px] sm:p-12">
        <div className="max-w-2xl space-y-4">
          <h2 className={sectionTitle}>{t.marketing.policyTitle}</h2>
          <p className="max-w-[48ch] text-base leading-relaxed text-ink-500">
            {t.marketing.policySubtitle}
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {policies.map((item) => (
            <div key={item.title} className="space-y-3 rounded-[20px] bg-paper-raised/75 p-5">
              <item.icon size={24} />
              <h3 className="text-xl font-semibold text-ink-900">{item.title}</h3>
              <p className="text-sm leading-relaxed text-ink-500">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

