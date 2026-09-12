/**
 * Catalog dịch theo ID ổn định — mock/API chỉ giữ key, UI resolve lúc render.
 * Đổi ngôn ngữ không cần sửa từng card.
 */

export type PrivacyControlCopy = { name: string; description: string };
export type PrivacyAuditCopy = {
  action: string;
  result: string;
  sourceName?: string;
  timestamp: string;
};

type PrivacyCatalog = {
  scopes: Record<string, string>;
  controls: Record<string, PrivacyControlCopy>;
  audits: Record<string, PrivacyAuditCopy>;
  sourceNames: Record<string, string>;
  timeLabels: Record<string, string>;
  runtime: {
    pausedAll: { action: string; result: string; sourceName: string };
    resumedAll: { action: string; result: string; sourceName: string };
    pausedSource: { action: string; result: string };
    resumedSource: { action: string; result: string };
    refreshedSource: { action: string; result: string };
    controlEnabled: { action: string; result: string };
    controlDisabled: { action: string; result: string };
  };
};

const en: PrivacyCatalog = {
  sourceNames: {
    'src-discord': 'Discord',
    'src-canvas': 'Canvas LMS',
    'src-email': 'Gmail',
    'src-calendar': 'Google Drive & Calendar',
  },
  timeLabels: {
    today935: 'Today, 9:35 AM',
    today700: 'Today, 7:00 AM',
    today815: 'Today, 8:15 AM',
    yesterday600: 'Yesterday, 6:00 PM',
    today942: 'Today, 9:42 AM',
    justNow: 'Just now',
  },
  scopes: {
    'discord.server': 'AI Accelerator Cohort Server',
    'discord.announcements': '#announcements channel',
    'discord.teamChat': '#team-chat channel',
    'discord.publicThreads': 'Public course discussion threads',
    'discord.dms': 'Private direct messages (DMs)',
    'discord.personalServers': 'Unselected personal Discord servers',
    'discord.voice': 'Voice channel audio stream',
    'discord.friends': 'Personal friend chats',
    'canvas.syllabus': 'Course Syllabus & Milestones',
    'canvas.assignments': 'Assignment Submission Portals & Deadlines',
    'canvas.gradebook': 'Gradebook & Instructor Feedback',
    'canvas.announcements': 'Course Announcements',
    'canvas.otherCourses': 'Other university course portals',
    'canvas.tuition': 'Personal tuition payment information',
    'canvas.peerGrades': 'Private peer grade data',
    'email.directors': 'Emails from program directors & mentors',
    'email.newsletter': 'Cohort weekly newsletter digest',
    'email.schedule': 'Program schedule notifications',
    'email.personal': 'Personal non-program inbox messages',
    'email.finance': 'Financial & banking emails',
    'email.security': 'Password resets or security tokens',
    'cal.events': 'Program Event Calendar',
    'cal.officeHours': 'Shared Mentor Office Hours schedule',
    'cal.driveFolders': 'Selected project shared Drive folders',
    'cal.privateEvents': 'Personal private Google Calendar events',
    'cal.unsharedDrive': 'Unshared Google Drive documents',
    'cal.photos': 'Google Photos & location history',
  },
  controls: {
    'gc-disc-announcements': {
      name: '#announcements channel',
      description: 'Official announcements from program director & TAs',
    },
    'gc-disc-teamchat': {
      name: '#team-chat channel',
      description: 'Team project collaboration messages',
    },
    'gc-disc-general': {
      name: '#general-help channel',
      description: 'Peer Q&A and general discussions',
    },
    'gc-disc-dms': {
      name: 'Direct Messages & Voice',
      description: 'Private 1-on-1 conversations and voice channels',
    },
    'gc-canvas-assignments': {
      name: 'Assignments & Deadlines',
      description: 'Gradebook deadlines, proposal dates, rubric requirements',
    },
    'gc-canvas-announcements': {
      name: 'Course Announcements',
      description: 'Official portal notifications from instructors',
    },
    'gc-canvas-discussions': {
      name: 'Discussion Boards',
      description: 'Course forum threads and peer replies',
    },
    'gc-email-director': {
      name: 'Program Director Emails',
      description: 'Official communications from Dr. Chen & program staff',
    },
    'gc-email-newsletter': {
      name: 'Weekly Newsletter Digest',
      description: 'Program announcements and upcoming event highlights',
    },
    'gc-email-personal': {
      name: 'Personal & Financial Mail',
      description: 'Non-program personal emails',
    },
    'gc-cal-officehours': {
      name: 'Mentor Office Hours',
      description: 'Shared calendar for TA and mentor slots',
    },
    'gc-cal-deadlines': {
      name: 'Deliverable Deadlines Calendar',
      description: 'Official program calendar feed',
    },
    'gc-drive-shared': {
      name: 'Shared Project Drive Folder',
      description: 'Draft pitch decks and proposal documents',
    },
  },
  audits: {
    'aud-1': {
      action: 'Paused Google Drive capture',
      sourceName: 'Google Drive & Calendar',
      result: 'Future data capture from Google Drive paused by user.',
      timestamp: 'Yesterday, 6:05 PM',
    },
    'aud-2': {
      action: 'Updated Discord channel permissions',
      sourceName: 'Discord',
      result: 'Disabled #general-help channel capture.',
      timestamp: 'July 28, 2026 · 2:10 PM',
    },
    'aud-3': {
      action: 'Confirmed memory record',
      sourceName: 'Gmail Newsletter Survey',
      result: 'Confirmed briefing preference time (8:00 AM PST).',
      timestamp: 'July 22, 2026 · 9:10 AM',
    },
  },
  runtime: {
    pausedAll: {
      action: 'Paused all data capture',
      result: 'Data capture paused globally across all sources.',
      sourceName: 'Global Controls',
    },
    resumedAll: {
      action: 'Resumed all data capture',
      result: 'Data capture resumed.',
      sourceName: 'Global Controls',
    },
    pausedSource: {
      action: 'Paused {source} capture',
      result: 'Processing new updates paused.',
    },
    resumedSource: {
      action: 'Resumed {source} capture',
      result: 'Processing new updates enabled.',
    },
    refreshedSource: {
      action: 'Refreshed {source} review',
      result: 'Source access status rechecked.',
    },
    controlEnabled: {
      action: 'Updated {source}: {control}',
      result: 'Access granted for future capture.',
    },
    controlDisabled: {
      action: 'Updated {source}: {control}',
      result: 'Access disabled for future capture.',
    },
  },
};

const vi: PrivacyCatalog = {
  sourceNames: {
    'src-discord': 'Discord',
    'src-canvas': 'Canvas LMS',
    'src-email': 'Gmail',
    'src-calendar': 'Google Drive & Lịch',
  },
  timeLabels: {
    today935: 'Hôm nay, 9:35',
    today700: 'Hôm nay, 7:00',
    today815: 'Hôm nay, 8:15',
    yesterday600: 'Hôm qua, 18:00',
    today942: 'Hôm nay, 9:42',
    justNow: 'Vừa xong',
  },
  scopes: {
    'discord.server': 'Máy chủ AI Accelerator Cohort',
    'discord.announcements': 'Kênh #announcements',
    'discord.teamChat': 'Kênh #team-chat',
    'discord.publicThreads': 'Chủ đề thảo luận khóa học công khai',
    'discord.dms': 'Tin nhắn trực tiếp (DM)',
    'discord.personalServers': 'Máy chủ Discord cá nhân chưa chọn',
    'discord.voice': 'Luồng âm thanh kênh thoại',
    'discord.friends': 'Chat bạn bè cá nhân',
    'canvas.syllabus': 'Đề cương & mốc khóa học',
    'canvas.assignments': 'Cổng nộp bài & hạn chót',
    'canvas.gradebook': 'Sổ điểm & phản hồi giảng viên',
    'canvas.announcements': 'Thông báo khóa học',
    'canvas.otherCourses': 'Cổng khóa học đại học khác',
    'canvas.tuition': 'Thông tin học phí cá nhân',
    'canvas.peerGrades': 'Điểm bạn học riêng tư',
    'email.directors': 'Email từ giám đốc chương trình & mentor',
    'email.newsletter': 'Bản tin tuần của cohort',
    'email.schedule': 'Thông báo lịch chương trình',
    'email.personal': 'Email cá nhân ngoài chương trình',
    'email.finance': 'Email tài chính & ngân hàng',
    'email.security': 'Đặt lại mật khẩu hoặc mã bảo mật',
    'cal.events': 'Lịch sự kiện chương trình',
    'cal.officeHours': 'Lịch giờ mentor dùng chung',
    'cal.driveFolders': 'Thư mục Drive dự án đã chọn',
    'cal.privateEvents': 'Sự kiện lịch Google riêng tư',
    'cal.unsharedDrive': 'Tài liệu Drive chưa chia sẻ',
    'cal.photos': 'Google Photos & lịch sử vị trí',
  },
  controls: {
    'gc-disc-announcements': {
      name: 'Kênh #announcements',
      description: 'Thông báo chính thức từ giám đốc chương trình & TA',
    },
    'gc-disc-teamchat': {
      name: 'Kênh #team-chat',
      description: 'Tin nhắn cộng tác dự án nhóm',
    },
    'gc-disc-general': {
      name: 'Kênh #general-help',
      description: 'Hỏi đáp và thảo luận chung giữa học viên',
    },
    'gc-disc-dms': {
      name: 'Tin nhắn trực tiếp & thoại',
      description: 'Hội thoại 1-1 riêng tư và kênh thoại',
    },
    'gc-canvas-assignments': {
      name: 'Bài tập & hạn chót',
      description: 'Hạn nộp, ngày đề xuất, yêu cầu rubric',
    },
    'gc-canvas-announcements': {
      name: 'Thông báo khóa học',
      description: 'Thông báo chính thức từ giảng viên trên cổng',
    },
    'gc-canvas-discussions': {
      name: 'Diễn đàn thảo luận',
      description: 'Chủ đề diễn đàn và phản hồi đồng môn',
    },
    'gc-email-director': {
      name: 'Email giám đốc chương trình',
      description: 'Liên lạc chính thức từ Dr. Chen & ban tổ chức',
    },
    'gc-email-newsletter': {
      name: 'Bản tin tuần',
      description: 'Thông báo chương trình và sự kiện sắp tới',
    },
    'gc-email-personal': {
      name: 'Thư cá nhân & tài chính',
      description: 'Email cá nhân ngoài chương trình',
    },
    'gc-cal-officehours': {
      name: 'Giờ mentor',
      description: 'Lịch dùng chung cho slot TA và mentor',
    },
    'gc-cal-deadlines': {
      name: 'Lịch hạn nộp sản phẩm',
      description: 'Nguồn lịch chính thức của chương trình',
    },
    'gc-drive-shared': {
      name: 'Thư mục Drive dự án dùng chung',
      description: 'Bản nháp pitch deck và tài liệu đề xuất',
    },
  },
  audits: {
    'aud-1': {
      action: 'Tạm dừng thu thập Google Drive',
      sourceName: 'Google Drive & Lịch',
      result: 'Người dùng đã tạm dừng thu thập dữ liệu Google Drive trong tương lai.',
      timestamp: 'Hôm qua, 18:05',
    },
    'aud-2': {
      action: 'Cập nhật quyền kênh Discord',
      sourceName: 'Discord',
      result: 'Đã tắt thu thập kênh #general-help.',
      timestamp: '28/07/2026 · 14:10',
    },
    'aud-3': {
      action: 'Xác nhận bản ghi nhớ',
      sourceName: 'Khảo sát bản tin Gmail',
      result: 'Đã xác nhận giờ briefing ưa thích (8:00 AM PST).',
      timestamp: '22/07/2026 · 09:10',
    },
  },
  runtime: {
    pausedAll: {
      action: 'Tạm dừng toàn bộ thu thập',
      result: 'Đã tạm dừng thu thập dữ liệu trên mọi nguồn.',
      sourceName: 'Điều khiển toàn cục',
    },
    resumedAll: {
      action: 'Bật lại toàn bộ thu thập',
      result: 'Đã bật lại thu thập dữ liệu.',
      sourceName: 'Điều khiển toàn cục',
    },
    pausedSource: {
      action: 'Tạm dừng thu thập {source}',
      result: 'Đã tạm dừng xử lý cập nhật mới.',
    },
    resumedSource: {
      action: 'Bật lại thu thập {source}',
      result: 'Đã bật xử lý cập nhật mới.',
    },
    refreshedSource: {
      action: 'Làm mới rà soát {source}',
      result: 'Đã kiểm tra lại trạng thái quyền truy cập nguồn.',
    },
    controlEnabled: {
      action: 'Cập nhật {source}: {control}',
      result: 'Đã cấp quyền thu thập trong tương lai.',
    },
    controlDisabled: {
      action: 'Cập nhật {source}: {control}',
      result: 'Đã tắt quyền thu thập trong tương lai.',
    },
  },
};

const catalogs: Record<'en' | 'vi', PrivacyCatalog> = { en, vi };

/** Nhãn Gmail hệ thống — map theo label id API, không theo chuỗi API trả về. */
const gmailLabels: Record<'en' | 'vi', Record<string, string>> = {
  en: {
    INBOX: 'Primary Inbox',
    CATEGORY_PROMOTIONS: 'Promotions',
    CATEGORY_SOCIAL: 'Social',
  },
  vi: {
    INBOX: 'Hộp thư chính',
    CATEGORY_PROMOTIONS: 'Quảng cáo',
    CATEGORY_SOCIAL: 'Mạng xã hội',
  },
};

export function getPrivacyCatalog(language: string): PrivacyCatalog {
  return catalogs[language === 'vi' ? 'vi' : 'en'];
}

export function localizeScope(key: string, language: string): string {
  return getPrivacyCatalog(language).scopes[key] ?? key;
}

export function localizeControl(id: string, language: string): PrivacyControlCopy {
  return (
    getPrivacyCatalog(language).controls[id] ?? {
      name: id,
      description: '',
    }
  );
}

export function localizeSourceName(sourceId: string, fallback: string, language: string): string {
  return getPrivacyCatalog(language).sourceNames[sourceId] ?? fallback;
}

export function localizeTimeLabel(key: string, language: string): string {
  return getPrivacyCatalog(language).timeLabels[key] ?? key;
}

export function localizeAudit(id: string, language: string): PrivacyAuditCopy | null {
  return getPrivacyCatalog(language).audits[id] ?? null;
}

export function localizeGmailLabel(labelId: string, fallbackName: string, language: string): string {
  return gmailLabels[language === 'vi' ? 'vi' : 'en'][labelId] ?? fallbackName;
}

export function fillTemplate(template: string, vars: Record<string, string>): string {
  return Object.entries(vars).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, value),
    template,
  );
}
