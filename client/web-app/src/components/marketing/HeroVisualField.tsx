import React, { useEffect, useRef, useState } from 'react';
import backgroundVideo from '../../assets/background.mp4';

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => {
      setReduced(
        media.matches || document.documentElement.classList.contains('reduce-motion'),
      );
    };
    sync();
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);

  return reduced;
}

/**
 * Hero media hòa vào nền paper bằng mask feathered
 * (cùng ngôn ngữ với FeatheredBleed ở section product).
 */
export const HeroVisualField: React.FC = () => {
  const bgRef = useRef<HTMLVideoElement>(null);
  const reduceMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (bgRef.current) bgRef.current.playbackRate = 0.55;
  }, []);

  const softMask =
    'radial-gradient(ellipse 78% 72% at 62% 42%, black 18%, rgba(0,0,0,0.72) 42%, transparent 74%)';

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div
        className="hero-soft-bleed absolute inset-0"
        style={{
          WebkitMaskImage: softMask,
          maskImage: softMask,
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
          WebkitMaskSize: '100% 100%',
          maskSize: '100% 100%',
        }}
      >
        <div className="hero-bg-drift absolute inset-[-6%] scale-[1.08]">
          {!reduceMotion ? (
            <video
              ref={bgRef}
              className="h-full w-full object-cover"
              src={backgroundVideo}
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
            />
          ) : (
            <div className="h-full w-full bg-wash-sage" />
          )}
        </div>

        {/* Tint rất nhẹ - chỉ hòa palette, không làm mất nét */}
        <div className="absolute inset-0 bg-gradient-to-br from-wash-porcelain/10 via-transparent to-wash-sage/15 mix-blend-soft-light" />
      </div>

      {/* Wash chỉ ở mép để soft-bleed, giữ vùng ảnh chính rõ nét */}
      <div className="absolute inset-y-0 left-0 w-[34%] bg-gradient-to-r from-paper via-paper/70 to-transparent" />
      <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-paper via-paper/55 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-paper via-paper/60 to-transparent" />
      <div className="absolute inset-y-0 right-0 w-[8%] bg-gradient-to-l from-paper/70 to-transparent" />
    </div>
  );
};
