import { storage } from "wxt/utils/storage";

export type ThemeMode = "light" | "dark";

/** Lưu lựa chọn sáng/tối của người dùng, riêng theo máy (không đồng bộ với web-app). */
export const themeItem = storage.defineItem<ThemeMode>("local:theme", {
  fallback: "light",
});

/** Ghi data-theme lên <html> để CSS trong tailwind.css áp đúng bộ màu. */
export function applyTheme(mode: ThemeMode): void {
  document.documentElement.setAttribute("data-theme", mode);
}

/** Đọc theme đã lưu và áp ngay lúc mount — dùng ở cả popup lẫn options. */
export async function initTheme(): Promise<ThemeMode> {
  const mode = await themeItem.getValue();
  applyTheme(mode);
  return mode;
}

/** Đảo sáng/tối, lưu lại rồi áp ngay — cùng cơ chế với nút theme bên web-app. */
export async function toggleTheme(current: ThemeMode): Promise<ThemeMode> {
  const next: ThemeMode = current === "dark" ? "light" : "dark";
  await themeItem.setValue(next);
  applyTheme(next);
  return next;
}
