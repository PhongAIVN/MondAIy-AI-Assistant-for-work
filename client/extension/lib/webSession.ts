// Đọc phiên đăng nhập web app trực tiếp từ localStorage/sessionStorage của
// chính trang đó (key "nav_session", xem client/web-app/src/stores/useAuthStore.ts).
// Dùng cho content script (đóng trong tab web app) — hàm này KHÔNG được gọi
// qua chrome.scripting.executeScript({func}) vì lúc đó Chrome tách hàm ra khỏi
// closure gốc, mọi import/hằng số ngoài thân hàm sẽ mất; side panel tự viết 1
// bản inline riêng cho trường hợp đó (xem entrypoints/sidepanel/App.tsx).
const WEB_SESSION_KEY = "nav_session";

export interface WebSession {
  accessToken: string;
  refreshToken: string;
}

export function readWebSessionFromPage(): WebSession | null {
  for (const storage of [window.localStorage, window.sessionStorage]) {
    try {
      const raw = storage.getItem(WEB_SESSION_KEY);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as Partial<WebSession>;
      if (typeof parsed.accessToken === "string" && typeof parsed.refreshToken === "string") {
        return { accessToken: parsed.accessToken, refreshToken: parsed.refreshToken };
      }
    } catch {
      // JSON hỏng — thử storage còn lại thay vì coi như đã đăng xuất.
    }
  }
  return null;
}
