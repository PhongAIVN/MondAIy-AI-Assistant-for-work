/** Optional web URL for OAuth handoff and public links; never the app shell. */
export const MOBILE_WEB_APP_URL =
  process.env.EXPO_PUBLIC_WEB_APP_URL || 'https://www.c3-app-004.io.vn';

/** Deep link để phiên OAuth quay lại đúng app native, không rơi vào web app. */
export const MOBILE_GOOGLE_CALLBACK_URI =
  process.env.EXPO_PUBLIC_GOOGLE_CALLBACK_URI?.trim() || 'mondaiy://auth/callback';
