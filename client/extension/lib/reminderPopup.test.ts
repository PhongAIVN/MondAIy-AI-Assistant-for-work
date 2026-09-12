import { describe, expect, it, vi } from "vitest";
import { maybeOpenReminderPopup, shouldAutoOpenReminderPopup } from "./reminderPopup";
import type { NotificationBundle } from "@/types";

function makeBundle(bundleKey: string): NotificationBundle {
  return { bundleKey, scheduledAt: "2026-08-15T00:00:00Z", reminderIds: [1], tasks: [] };
}

describe("maybeOpenReminderPopup", () => {
  it("không tự mở khi người dùng chưa bật tuỳ chọn", async () => {
    const openPopup = vi.fn(async () => undefined);

    await expect(maybeOpenReminderPopup(false, openPopup)).resolves.toBe("disabled");
    expect(openPopup).not.toHaveBeenCalled();
  });

  it("tự mở đúng một lần khi tuỳ chọn đã bật", async () => {
    const openPopup = vi.fn(async () => undefined);

    await expect(maybeOpenReminderPopup(true, openPopup)).resolves.toBe("opened");
    expect(openPopup).toHaveBeenCalledTimes(1);
  });

  it("trả fallback thay vì làm hỏng luồng reminder khi Chrome không mở được", async () => {
    const openPopup = vi.fn(async () => {
      throw new Error("This API is not supported");
    });

    await expect(maybeOpenReminderPopup(true, openPopup)).resolves.toBe("unavailable");
  });
});

describe("shouldAutoOpenReminderPopup", () => {
  it("mo khi chua co bundle nao dang active", () => {
    expect(shouldAutoOpenReminderPopup(makeBundle("b1"), null)).toBe(true);
  });

  it("mo khi bundle moi khac bundle dang active", () => {
    expect(shouldAutoOpenReminderPopup(makeBundle("b2"), makeBundle("b1"))).toBe(true);
  });

  it("KHONG mo lai khi bundle trung voi bundle dang active - chan poll lap lai luc dang nhap ep mo popup nhieu lan", () => {
    expect(shouldAutoOpenReminderPopup(makeBundle("b1"), makeBundle("b1"))).toBe(false);
  });
});
