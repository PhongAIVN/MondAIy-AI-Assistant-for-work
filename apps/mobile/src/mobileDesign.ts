/** Native mobile information architecture. Kept explicit so every primary state stays intentional. */
export const MOBILE_APP_SCREENS = [
  'onboarding',
  'authentication',
  'home',
  'discover',
  'content-detail',
  'search',
  'assistant',
  'notifications',
  'profile',
  'settings',
] as const;

export const MOBILE_PRODUCT_STATES = ['loading', 'empty', 'error', 'success'] as const;

/** Hai không gian thao tác độc lập ở đầu trang chủ, không trộn dữ liệu lịch với việc cần duyệt. */
export const MOBILE_HOME_VIEWS = ['tasks', 'calendar'] as const;

/** Câu hỏi khởi đầu chỉ dẫn người dùng vào các luồng có dữ liệu thật. */
export const MOBILE_CHAT_SUGGESTIONS = [
  'Hôm nay có gì mới?',
  'Deadline nào đang quan trọng?',
  'Tiếp theo tôi nên làm gì?',
  'Có nguồn nào đang mâu thuẫn không?',
  'Bản brief này được tạo như thế nào?',
  'Điều gì còn thiếu hoặc chưa chắc chắn?',
  'Cho tôi xem bằng chứng nguồn',
  'Giúp tôi soạn câu hỏi cho mentor',
] as const;
