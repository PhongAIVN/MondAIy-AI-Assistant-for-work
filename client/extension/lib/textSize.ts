import { storage } from "wxt/utils/storage";

export type TextSize = "sm" | "md" | "lg";

const TEXT_SIZE_CLASS: Record<TextSize, string> = {
  sm: "text-size-sm",
  md: "text-size-md",
  lg: "text-size-lg",
};

/** Lưu cỡ chữ người dùng chọn, riêng theo máy — cùng cơ chế với theme.ts. */
export const textSizeItem = storage.defineItem<TextSize>("local:textSize", {
  fallback: "md",
});

/** Ghi class text-size-* lên <html> để CSS trong tailwind.css áp đúng cỡ chữ
 * (cùng hệ số với web-app index.css html.text-size-*). */
export function applyTextSize(size: TextSize): void {
  const root = document.documentElement;
  for (const cls of Object.values(TEXT_SIZE_CLASS)) root.classList.remove(cls);
  root.classList.add(TEXT_SIZE_CLASS[size]);
}

export async function initTextSize(): Promise<TextSize> {
  const size = await textSizeItem.getValue();
  applyTextSize(size);
  return size;
}

export async function setTextSize(size: TextSize): Promise<void> {
  await textSizeItem.setValue(size);
  applyTextSize(size);
}
