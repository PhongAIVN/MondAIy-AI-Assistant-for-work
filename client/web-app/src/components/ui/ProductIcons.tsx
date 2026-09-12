import React from 'react';

interface IconProps {
  className?: string;
  size?: number;
}

const base = (size: number, className: string, children: React.ReactNode, label: string) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden={label ? undefined : true}
    role={label ? 'img' : undefined}
    aria-label={label || undefined}
  >
    {children}
  </svg>
);

/** Gộp nhiều nguồn thành một danh sách có dẫn nguồn */
export const IconSynthesize: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path d="M5 6h6M5 12h10M5 18h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M17 7l2.5 2.5L22 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Synthesize',
  );

/** Bằng chứng / nguồn gốc có thể lần ngược */
export const IconEvidence: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path
        d="M8 4h6l4 4v12a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M14 4v4h4M9.5 13h5M9.5 16.5h3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="10.2" cy="10" r="1" fill="currentColor" />
    </>,
    'Evidence',
  );

/** Hai nguồn mâu thuẫn đặt cạnh nhau */
export const IconConflict: React.FC<IconProps> = ({ className = 'text-warning-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path d="M7 5v14M17 5v14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M7 9h4M13 15h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M10.5 8.5L13.5 15.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Conflict',
  );

/** Người dùng xác nhận trước khi hành động */
export const IconConfirm: React.FC<IconProps> = ({ className = 'text-success-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <rect x="4" y="5" width="16" height="14" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 12.2l2.4 2.4L16.2 9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Confirm',
  );

/** Hỏi đáp kèm nguồn */
export const IconAsk: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path
        d="M5 17.5V8.2A2.2 2.2 0 0 1 7.2 6h9.6A2.2 2.2 0 0 1 19 8.2v5.6a2.2 2.2 0 0 1-2.2 2.2H9.2L5 19v-1.5z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M9.5 10.5h5M9.5 13.2h3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Ask',
  );

/** Thay đổi / phiên bản */
export const IconChange: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path
        d="M7 8h7.5a3.5 3.5 0 1 1 0 7H10"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path d="M9.5 5.5L7 8l2.5 2.5M14.5 18.5L17 16l-2.5-2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Change',
  );

/** Nguồn / thư viện kết nối */
export const IconSources: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <rect x="4" y="5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="5" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="4" y="14" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
      <rect x="13" y="14" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
    </>,
    'Sources',
  );

/** Công việc cần làm / checklist */
export const IconTasks: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <rect x="4.5" y="4.5" width="15" height="15" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 9.2h8M8 12.2h8M8 15.2h5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Tasks',
  );

/** Quyền riêng tư / khiên dữ liệu */
export const IconPrivacy: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path
        d="M12 3.5l6.5 2.5v5.2c0 4.1-2.7 7.2-6.5 8.8-3.8-1.6-6.5-4.7-6.5-8.8V6L12 3.5z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M9.8 12.1l1.6 1.6 3.2-3.4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Privacy',
  );

/** Hoạt động / nhật ký */
export const IconActivity: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path d="M4 12h3.2l2-5.5L13 18l2.2-6H20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Activity',
  );

/** Thông báo */
export const IconBell: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <path
        d="M12 4.5a4.2 4.2 0 0 1 4.2 4.2v2.1c0 .9.3 1.7.9 2.4l.7.8H6.2l.7-.8c.6-.7.9-1.5.9-2.4V8.7A4.2 4.2 0 0 1 12 4.5z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M10 18.2a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Notifications',
  );

/** Cài đặt */
export const IconSettings: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M12 3.8v1.8M12 18.4v1.8M3.8 12h1.8M18.4 12h1.8M6.1 6.1l1.3 1.3M16.6 16.6l1.3 1.3M17.9 6.1l-1.3 1.3M7.4 16.6l-1.3 1.3"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </>,
    'Settings',
  );

/** Tìm kiếm */
export const IconSearch: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <circle cx="11" cy="11" r="5.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M15.5 15.5L20 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Search',
  );

/** Bảo mật / khóa */
export const IconLock: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <rect x="5.5" y="11" width="13" height="9" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 11V7.5a4 4 0 0 1 8 0V11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="15.2" r="1.3" fill="currentColor" />
    </>,
    'Security',
  );

/** Thời hạn lưu / đồng hồ */
export const IconClock: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 7.5V12l3.2 1.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Retention',
  );

/** Người dùng / trẻ em */
export const IconUsers: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <circle cx="9" cy="8.5" r="2.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.2 18.5c.6-2.8 2.5-4.3 4.8-4.3s4.2 1.5 4.8 4.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="16.3" cy="9" r="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M15 14.5c1.9.2 3.3 1.5 3.8 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Audience',
  );

/** Liên hệ / thư */
export const IconMail: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <rect x="4" y="6" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4.8 7l7.2 6 7.2-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </>,
    'Contact',
  );

/** Pipeline / chạy briefing */
export const IconPipeline: React.FC<IconProps> = ({ className = 'text-action-solid', size = 24 }) =>
  base(
    size,
    className,
    <>
      <circle cx="6" cy="7" r="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="2" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="18" cy="17" r="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M7.8 8.2L10.2 10.8M13.8 13.2L16.2 15.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </>,
    'Pipeline',
  );
