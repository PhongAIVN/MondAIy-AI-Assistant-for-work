import React, { useEffect, useRef } from 'react';

/**
 * Nền tranh động cho hero, phủ toàn khối rồi bị màn nền ngà kéo mờ ở giữa để
 * chữ luôn nằm trên vùng gần như đặc màu.
 *
 * Thêm clip mới thì bỏ file vào public/media/ rồi truyền tên qua prop name.
 * Nhận gif thì phải chuyển sang video trước, gif nặng gấp mười lăm lần và
 * không dừng được khi người dùng bật giảm chuyển động:
 *
 *   ffmpeg -i nguon.gif -movflags +faststart -pix_fmt yuv420p \
 *     -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -crf 26 -an ten.mp4
 *   ffmpeg -i nguon.gif -c:v libvpx-vp9 -crf 36 -b:v 0 -an ten.webm
 *   ffmpeg -i nguon.gif -vframes 1 -q:v 4 ten-poster.jpg
 *
 * Tiêu chí chọn tranh: khổ ngang, nước, tông lạnh, chuyển động chậm và đều.
 * Chuyển động nhanh sẽ giành sự chú ý với tiêu đề.
 */

type WaterBackdropProps = {
  /** Tên file trong public/media, không kèm đuôi */
  name?: string;
  /** Kiểu màn che: toả từ giữa cho hero, hoặc đổ ngang cho thẻ và đầu trang con */
  scrim?: 'center' | 'side';
  className?: string;
};

export const WaterBackdrop: React.FC<WaterBackdropProps> = ({
  name = 'hero-rain',
  scrim = 'center',
  className = '',
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');

    const apply = (): void => {
      const video = videoRef.current;
      if (!video) return;
      if (media.matches) {
        video.pause();
      } else {
        void video.play().catch(() => undefined);
      }
    };

    // Gọi play ngay lúc mount thì video chưa có dữ liệu, promise bị reject và
    // clip đứng im ở khung poster. Chờ canplay rồi thử lại mới chắc chạy.
    const video = videoRef.current;
    apply();
    video?.addEventListener('canplay', apply);
    media.addEventListener('change', apply);
    return () => {
      video?.removeEventListener('canplay', apply);
      media.removeEventListener('change', apply);
    };
  }, []);

  const scrimStyle =
    scrim === 'center'
      ? {
          // Khối hero trong app cao hơn bản dựng thử vì có thêm ô xem trước bên
          // dưới, nên vùng đặc màu phải rộng ra thì chữ mới đủ tương phản.
          background: `
            radial-gradient(ellipse 58% 46% at 50% 30%, var(--color-app-bg) 0%, var(--color-app-bg) 62%, transparent 100%),
            linear-gradient(to bottom, var(--color-app-bg) 0%, transparent 12%, transparent 46%, var(--color-app-bg) 88%)
          `,
        }
      : {
          background: `
            linear-gradient(to right, var(--color-app-bg) 6%, color-mix(in srgb, var(--color-app-bg) 72%, transparent) 62%, transparent 100%),
            linear-gradient(to bottom, var(--color-app-bg) 0%, transparent 24%, transparent 52%, var(--color-app-bg) 98%)
          `,
        };

  return (
    <div className={`pointer-events-none absolute inset-0 -z-10 overflow-hidden ${className}`} aria-hidden="true">
      <video
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        poster={`/media/${name}-poster.jpg`}
        className="h-full w-full object-cover opacity-90 dark:opacity-30"
        style={{ objectPosition: 'center 46%' }}
      >
        <source src={`/media/${name}.webm`} type="video/webm" />
        <source src={`/media/${name}.mp4`} type="video/mp4" />
      </video>
      <div className="absolute inset-0" style={scrimStyle} />
    </div>
  );
};
