import React from 'react';
import discordIconUrl from '../../assets/discord-icon.png';
import gmailIconUrl from '../../assets/gmail-icon.png';
import outlookIconUrl from '../../assets/outlook-icon.png';
import slackIconUrl from '../../assets/slack-icon.png';
import vlearnIconUrl from '../../assets/vlearn-icon.png';
import { MondaiyMark } from './MondaiyMark';

interface BrandIconProps {
  className?: string;
  title?: string;
}

const imgClass = (className: string) => `${className} shrink-0 object-contain`;

export const DiscordIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5', title = 'Discord' }) => (
  <img src={discordIconUrl} alt={title} title={title} className={imgClass(className)} draggable={false} />
);

export const GmailIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5', title = 'Gmail' }) => (
  <img src={gmailIconUrl} alt={title} title={title} className={imgClass(className)} draggable={false} />
);

/**
 * Placeholder SVG — chưa có file PNG chính thức như Discord/Gmail. Thay bằng
 * `jira-icon.png` (asset thật, xem `discord-icon.png`) khi Nhi cấp.
 */
export const JiraIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5' }) => (
  <svg viewBox="0 0 24 24" className={`${className} object-contain`} aria-label="Jira" role="img">
    <path
      d="M11.53 2 3 10.53a1.5 1.5 0 0 0 0 2.12l3.5 3.5 5.03-5.03 5.03 5.03 3.5-3.5a1.5 1.5 0 0 0 0-2.12L12.47 2a.67.67 0 0 0-.94 0Z"
      fill="#2684FF"
    />
    <path d="M11.53 8.62 6.5 13.65l5.03 5.03 5.03-5.03Z" fill="#2684FF" opacity="0.6" />
  </svg>
);

export const OutlookIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5', title = 'Outlook' }) => (
  <img src={outlookIconUrl} alt={title} title={title} className={imgClass(className)} draggable={false} />
);

export const SlackIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5', title = 'Slack' }) => (
  <img src={slackIconUrl} alt={title} title={title} className={imgClass(className)} draggable={false} />
);

/** VLearn / LMS — thay GraduationCap Lucide. */
export const VLearnIcon: React.FC<BrandIconProps> = ({ className = 'w-5 h-5', title = 'VLearn' }) => (
  <img src={vlearnIconUrl} alt={title} title={title} className={imgClass(className)} draggable={false} />
);

/** Google Calendar mark (SVG) — chưa có PNG trong assets. */
export const GoogleCalendarIcon: React.FC<BrandIconProps> = ({
  className = 'w-5 h-5',
  title = 'Google Calendar',
}) => (
  <svg
    viewBox="0 0 24 24"
    className={imgClass(className)}
    role="img"
    aria-label={title}
  >
    <title>{title}</title>
    <path fill="#FFFFFF" d="M5 3.5h14A2.5 2.5 0 0 1 21.5 6v12A2.5 2.5 0 0 1 19 20.5H5A2.5 2.5 0 0 1 2.5 18V6A2.5 2.5 0 0 1 5 3.5z" />
    <path fill="#1A73E8" d="M5 3.5h14A2.5 2.5 0 0 1 21.5 6v2.2H2.5V6A2.5 2.5 0 0 1 5 3.5z" />
    <path fill="#EA4335" d="M7.2 2.2h1.8v3.2H7.2z" />
    <path fill="#EA4335" d="M15 2.2h1.8v3.2H15z" />
    <path fill="#34A853" d="M11.2 12.1h1.6v1.6h-1.6z" />
    <path fill="#FBBC04" d="M14.2 12.1h1.6v1.6h-1.6z" />
    <path fill="#EA4335" d="M8.2 15.1h1.6v1.6H8.2z" />
    <path fill="#1A73E8" d="M11.2 15.1h1.6v1.6h-1.6z" />
    <path fill="#34A853" d="M14.2 15.1h1.6v1.6h-1.6z" />
    <path fill="#4285F4" d="M8.2 12.1h1.6v1.6H8.2z" />
    <path
      fill="none"
      stroke="#DADCE0"
      strokeWidth="1"
      d="M5 3.5h14A2.5 2.5 0 0 1 21.5 6v12A2.5 2.5 0 0 1 19 20.5H5A2.5 2.5 0 0 1 2.5 18V6A2.5 2.5 0 0 1 5 3.5z"
    />
  </svg>
);

export type BrandSourceKey =
  | 'discord'
  | 'gmail'
  | 'google'
  | 'email'
  | 'jira'
  | 'outlook'
  | 'slack'
  | 'vlearn'
  | 'lms'
  | 'canvas'
  | 'learning platform'
  | 'calendar'
  | 'google calendar'
  | 'program calendar';

/** Map platform / icon key → brand asset. Trả null nếu không phải brand. */
export function resolveBrandIcon(
  key: string,
  className = 'w-5 h-5',
): React.ReactNode | null {
  const k = key.trim().toLowerCase();

  if (k === 'mondaiy') {
    return <MondaiyMark size={20} className={className} title="Mondaiy reminder" />;
  }
  if (k === 'discord' || k === 'messagesquare') {
    return <DiscordIcon className={className} />;
  }
  if (k === 'gmail' || k === 'google' || k === 'email' || k === 'mail') {
    return <GmailIcon className={className} />;
  }
  if (k === 'jira') {
    return <JiraIcon className={className} />;
  }
  if (k === 'outlook') {
    return <OutlookIcon className={className} />;
  }
  if (k === 'slack') {
    return <SlackIcon className={className} />;
  }
  if (
    k === 'vlearn' ||
    k === 'lms' ||
    k === 'canvas' ||
    k === 'canvas lms' ||
    k === 'learning platform' ||
    k === 'graduationcap'
  ) {
    return <VLearnIcon className={className} />;
  }
  if (
    k === 'calendar' ||
    k === 'google calendar' ||
    k === 'program calendar' ||
    k === 'googlecalendar'
  ) {
    return <GoogleCalendarIcon className={className} />;
  }
  return null;
}
