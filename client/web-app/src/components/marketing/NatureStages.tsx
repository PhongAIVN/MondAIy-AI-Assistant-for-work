import React from 'react';
import { Link } from 'react-router-dom';
import { Mail, MapPin } from 'lucide-react';
import card1 from '../../assets/card1.gif';
import card2 from '../../assets/card2.gif';
import card3 from '../../assets/card3.gif';
import { MondaiyWordmark } from '../ui/MondaiyLogo';
import { useTranslation } from '../../i18n/useTranslation';

const FACEBOOK_URL = 'https://web.facebook.com/profile.php?id=61593367619616';
const CONTACT_EMAIL = 'lyn.nhi3010@gmail.com';
const CONTACT_ADDRESS = 'Vinhomes Ocean Park, Gia Lâm, Hà Nội';

// lucide-react bỏ hẳn icon thương hiệu (Facebook, Google...) vì lý do bản
// quyền — icon Facebook duy nhất vẽ tay ở đây, không kéo thêm thư viện chỉ
// cho 1 icon.
const FacebookIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
    <path d="M13.5 21v-7.6h2.55l.38-2.96h-2.93V8.55c0-.86.24-1.44 1.47-1.44h1.57V4.46A21 21 0 0 0 14.5 4.3c-2.15 0-3.62 1.31-3.62 3.72v2.42H8.32v2.96h2.56V21h2.62Z" />
  </svg>
);

interface FeatheredBleedProps {
  src?: string;
  className?: string;
}

/**
 * Landscape soft-bleed giống hero: mask mềm + wash mép,
 * không còn viền cắt cứng (kể cả cạnh phải).
 */
export const FeatheredBleed: React.FC<FeatheredBleedProps> = ({
  src = card2,
  className = '',
}) => {
  const softMask =
    'radial-gradient(ellipse 94% 96% at 48% 47%, black 10%, rgba(0,0,0,0.9) 42%, rgba(0,0,0,0.52) 64%, rgba(0,0,0,0.16) 80%, transparent 96%)';

  return (
    <div
      className={`pointer-events-none relative min-h-[430px] w-full overflow-hidden ${className}`}
      aria-hidden
    >
      <div
        className="absolute inset-[-5%]"
        style={{
          WebkitMaskImage: softMask,
          maskImage: softMask,
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
          WebkitMaskSize: '100% 100%',
          maskSize: '100% 100%',
        }}
      >
        <img
          className="h-full w-full scale-[1.04] object-cover object-[58%_center] saturate-[0.94]"
          src={src}
          alt=""
          decoding="async"
          draggable={false}
        />
      </div>

      <div className="absolute inset-y-0 left-0 w-[22%] bg-gradient-to-r from-paper via-paper/65 to-transparent" />
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-paper via-paper/55 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-paper via-paper/72 to-transparent" />
      <div className="absolute inset-y-0 right-0 w-[24%] bg-gradient-to-l from-paper via-paper/58 to-transparent" />
      <div className="absolute inset-0 bg-action-highlight/5 mix-blend-color" />
    </div>
  );
};

interface NatureStageProps {
  children: React.ReactNode;
  className?: string;
  mediaSrc?: string;
}

/**
 * Stage CTA: đúng 1 media nền, không card chồng.
 */
export const NatureStage: React.FC<NatureStageProps> = ({
  children,
  className = '',
  mediaSrc = card1,
}) => {
  return (
    <div
      className={`relative isolate overflow-hidden rounded-[28px] sm:rounded-[36px] ${className}`}
    >
      <div className="absolute inset-0" aria-hidden>
        <img
          className="h-full w-full scale-[1.02] object-cover"
          src={mediaSrc}
          alt=""
          decoding="async"
          draggable={false}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-[#17343F]/84 via-[#17343F]/50 to-[#17343F]/18" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#17343F]/40 via-transparent to-transparent" />
      </div>

      <div className="relative z-10">{children}</div>
    </div>
  );
};

interface EndingCardProps {
  rightsText: string;
}

/**
 * Ending card kiểu Littlebird: background mờ dần lên trên,
 * chữ brand nổi, copyright đè lên cùng card.
 */
export const BrandLandscapeFooter: React.FC<EndingCardProps> = ({ rightsText }) => {
  const { t } = useTranslation();

  return (
    <section className="relative mt-6 w-full overflow-hidden" aria-label="Mondaiy">
      {/* Mobile (<sm) xếp dọc Facebook/địa chỉ/email/bản quyền/nav thành 1 cột
          cao hơn hẳn bản 2 cột ngang từ sm: trở lên — chữ "mondaiy" khổng lồ
          canh giữa theo CHIỀU CAO section, container thấp thì nó đè thẳng lên
          khối info ghim đáy. Cao hơn ở mobile để hai khối không chồng nhau. */}
      <div className="relative min-h-[640px] w-full sm:min-h-[420px] lg:min-h-[520px]">
        <img
          className="absolute inset-0 h-full w-full object-cover"
          src={card3}
          alt=""
          aria-hidden
          decoding="async"
        />

        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-paper via-paper/75 to-transparent sm:h-52" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_55%,rgba(10,39,68,0.18)_0%,transparent_55%)]" />
        <div className="absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-[#17343F]/45 to-transparent" />

        <div className="absolute inset-0 flex flex-col items-center justify-center px-6 pt-10">
          <h2 className="select-none text-center text-[clamp(3.25rem,12vw,8.5rem)] font-bold leading-none tracking-[-0.045em] text-white drop-shadow-[0_8px_28px_rgba(10,39,68,0.35)]">
            <MondaiyWordmark
              className="font-bold"
              accentClassName="text-[#B4DDE0]"
            />
          </h2>
        </div>

        <div className="absolute inset-x-0 bottom-0 z-10 flex flex-col gap-4 px-5 pb-6 sm:flex-row sm:items-end sm:justify-between sm:px-8 sm:pb-8">
          {/* Facebook/địa chỉ/email xếp dọc, cùng 1 cột với dòng bản quyền —
              trước đây nằm ngang thành hàng riêng phía trên, tách khỏi "© 2026". */}
          <div className="flex flex-col gap-1.5 text-sm text-white/80">
            <a
              href={FACEBOOK_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Facebook"
              className="inline-flex items-center gap-1.5 hover:text-white"
            >
              <FacebookIcon className="h-4 w-4 shrink-0" />
              Facebook
            </a>
            <span className="inline-flex items-center gap-1.5">
              <MapPin className="h-4 w-4 shrink-0" aria-hidden />
              {CONTACT_ADDRESS}
            </span>
            <a href={`mailto:${CONTACT_EMAIL}`} className="inline-flex items-center gap-1.5 hover:text-white">
              <Mail className="h-4 w-4 shrink-0" aria-hidden />
              {CONTACT_EMAIL}
            </a>
            <p className="pt-1 text-sm text-white/85 drop-shadow-sm">{rightsText}</p>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-white/80">
              <Link to="/blog" className="hover:text-white">
                {t.marketing.blog}
              </Link>
              <Link to="/policy" className="hover:text-white">
                {t.marketing.policy}
              </Link>
              <Link to="/help" className="hover:text-white">
                {t.marketing.help}
              </Link>
              <Link to="/sign-in" className="hover:text-white">
                {t.actions.signIn}
              </Link>
          </div>
        </div>
      </div>
    </section>
  );
};
