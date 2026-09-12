import React, { useLayoutEffect, useRef } from 'react';
import { gsap } from 'gsap';
import { useMotionEnabled } from '../../hooks/useMotionEnabled';

type OrbConfig = {
  className: string;
  style: React.CSSProperties;
  /** Biên độ tự trôi lên xuống (px) — thời lượng lấy cảm hứng từ hero-float-far/mid/near cũ. */
  floatAmplitude: number;
  floatDuration: number;
  /** Orb "gần" hơn di theo cursor nhiều hơn — tạo cảm giác chiều sâu. */
  parallaxDepth: number;
  /** Orb "gần" đuổi theo chậm hơn (trễ/inertia rõ hơn). */
  parallaxDuration: number;
};

const ORBS: OrbConfig[] = [
  {
    className: 'bg-action-tint',
    style: { top: '8%', left: '10%', width: 320, height: 320 },
    floatAmplitude: 14,
    floatDuration: 22,
    parallaxDepth: 0.012,
    parallaxDuration: 0.8,
  },
  {
    className: 'bg-wash-sage',
    style: { top: '4%', right: '8%', width: 380, height: 380 },
    floatAmplitude: 18,
    floatDuration: 16,
    parallaxDepth: 0.02,
    parallaxDuration: 1,
  },
  {
    className: 'bg-wash-apricot',
    style: { bottom: '6%', left: '32%', width: 260, height: 260 },
    floatAmplitude: 22,
    floatDuration: 11,
    parallaxDepth: 0.035,
    parallaxDuration: 1.2,
  },
];

/**
 * Orb gradient mờ trong hero: tự trôi lên xuống chậm (float) + trôi nhẹ
 * theo cursor có độ trễ rõ (parallax inertia). Float chạy trên wrapper
 * ngoài, parallax chạy trên orb bên trong — tách 2 element để 2 tween
 * không tranh cùng property transform trên 1 node.
 */
export const HeroOrbs: React.FC = () => {
  const motionEnabled = useMotionEnabled();
  const floatRefs = useRef<Array<HTMLDivElement | null>>([]);
  const orbRefs = useRef<Array<HTMLDivElement | null>>([]);

  useLayoutEffect(() => {
    if (!motionEnabled) return;

    const ctx = gsap.context(() => {
      ORBS.forEach((orb, i) => {
        const el = floatRefs.current[i];
        if (!el) return;
        gsap.to(el, {
          y: `+=${orb.floatAmplitude}`,
          duration: orb.floatDuration,
          yoyo: true,
          repeat: -1,
          ease: 'sine.inOut',
        });
      });
    });

    const parallaxSetters = ORBS.map((orb, i) => {
      const el = orbRefs.current[i];
      if (!el) return null;
      return {
        x: gsap.quickTo(el, 'x', { duration: orb.parallaxDuration, ease: 'power2.out' }),
        y: gsap.quickTo(el, 'y', { duration: orb.parallaxDuration, ease: 'power2.out' }),
        depth: orb.parallaxDepth,
      };
    });

    const onMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - window.innerWidth / 2;
      const dy = e.clientY - window.innerHeight / 2;
      parallaxSetters.forEach((setter) => {
        if (!setter) return;
        setter.x(dx * setter.depth);
        setter.y(dy * setter.depth);
      });
    };

    window.addEventListener('mousemove', onMouseMove);

    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      ctx.revert();
    };
  }, [motionEnabled]);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {ORBS.map((orb, i) => (
        <div
          key={i}
          ref={(el) => {
            floatRefs.current[i] = el;
          }}
          className="absolute"
          style={orb.style}
        >
          <div
            ref={(el) => {
              orbRefs.current[i] = el;
            }}
            className={`h-full w-full rounded-full opacity-40 blur-3xl ${orb.className}`}
          />
        </div>
      ))}
    </div>
  );
};
