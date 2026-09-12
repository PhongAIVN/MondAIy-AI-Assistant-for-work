import React from 'react';

type UserAvatarProps = {
  name: string;
  avatarUrl?: string | null;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
};

const SIZE_CLASS: Record<NonNullable<UserAvatarProps['size']>, string> = {
  sm: 'w-7 h-7 text-xs',
  md: 'w-9 h-9 text-sm',
  lg: 'w-10 h-10 text-sm',
  xl: 'w-20 h-20 text-2xl border-4 border-[#E1EBFA] shadow-xs',
};

/** Avatar người dùng — ảnh nếu có, không thì chữ cái đầu. */
export const UserAvatar: React.FC<UserAvatarProps> = ({
  name,
  avatarUrl,
  size = 'md',
  className = '',
}) => {
  const initial = (name || '?').trim().charAt(0).toUpperCase() || '?';
  const sizeClass = SIZE_CLASS[size];

  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={name}
        className={`${sizeClass} rounded-full object-cover shrink-0 ${className}`}
      />
    );
  }

  return (
    <div
      className={`${sizeClass} rounded-full bg-[#0F1F38] dark:bg-[#2563A6] text-white flex items-center justify-center font-bold shrink-0 font-heading ${className}`}
      aria-hidden
    >
      {initial}
    </div>
  );
};
