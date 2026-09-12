import { storage } from "wxt/utils/storage";

/** Lưu bật/tắt độ tương phản cao, riêng theo máy — cùng cơ chế với theme.ts. */
export const highContrastItem = storage.defineItem<boolean>("local:highContrast", {
  fallback: false,
});

/** Bật/tắt class high-contrast trên <html> để CSS trong tailwind.css ghi đè
 * viền/chữ về đen-trắng tuyệt đối (cùng cơ chế với web-app index.css). */
export function applyHighContrast(enabled: boolean): void {
  document.documentElement.classList.toggle("high-contrast", enabled);
}

export async function initHighContrast(): Promise<boolean> {
  const enabled = await highContrastItem.getValue();
  applyHighContrast(enabled);
  return enabled;
}

export async function setHighContrast(enabled: boolean): Promise<void> {
  await highContrastItem.setValue(enabled);
  applyHighContrast(enabled);
}
