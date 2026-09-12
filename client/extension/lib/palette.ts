import { storage } from "wxt/utils/storage";

export type PaletteName = "paper" | "jade" | "plum" | "quartz";

export const PALETTE_NAMES: PaletteName[] = ["paper", "jade", "plum", "quartz"];

export const PALETTE_LABEL: Record<PaletteName, string> = {
  paper: "Paper",
  jade: "Ngọc bích",
  plum: "Mận",
  quartz: "Thạch anh",
};

/** Lưu tông màu người dùng chọn, riêng theo máy — cùng cơ chế với theme.ts
 * (data-palette độc lập với data-theme sáng/tối, xem tailwind.css). */
export const paletteItem = storage.defineItem<PaletteName>("local:palette", {
  fallback: "paper",
});

/** Ghi data-palette lên <html> để CSS trong tailwind.css áp đúng bộ màu. */
export function applyPalette(name: PaletteName): void {
  document.documentElement.setAttribute("data-palette", name);
}

/** Đọc tông đã lưu và áp ngay lúc mount — dùng ở cả sidepanel lẫn options. */
export async function initPalette(): Promise<PaletteName> {
  const name = await paletteItem.getValue();
  applyPalette(name);
  return name;
}

export async function setPalette(name: PaletteName): Promise<void> {
  await paletteItem.setValue(name);
  applyPalette(name);
}
