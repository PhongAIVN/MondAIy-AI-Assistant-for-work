import React from 'react';

interface MondaiyMarkProps {
  className?: string;
  size?: number;
  title?: string;
  /** Gif thay thế lúc hover — chỉ set ở nơi cần hiệu ứng (landing header); mặc định undefined = ảnh tĩnh luôn, hành vi cũ giữ nguyên. */
  hoverSrc?: string;
  /** Trạng thái hover đọc từ ngoài (vd. hover cả logo lockup, không chỉ riêng icon) — mặc định false. */
  hovered?: boolean;
}

/** Mascot mark dùng chung cho wordmark, product UI và favicon. */
export const MondaiyMark: React.FC<MondaiyMarkProps> = ({
  className = '',
  size = 28,
  title = 'Mondaiy',
  hoverSrc,
  hovered = false,
}) => {
  const showingGif = Boolean(hoverSrc && hovered);

  return (
    <img
      src={showingGif ? hoverSrc : '/mondaiy-mascot.png'}
      width={size}
      height={size}
      // Ảnh tĩnh và gif được cắt cùng một bbox nên khớp khung sẵn — không cần scale bù.
      className={`shrink-0 object-contain ${className}`}
      alt={title}
      draggable={false}
    />
  );
};
