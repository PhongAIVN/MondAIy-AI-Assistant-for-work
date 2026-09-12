import { useEffect, useState } from "react";
import { Check, ExternalLink, Mail, Mic, Moon, Sun, Trash2 } from "lucide-react";
import { HeaderAvatar } from "@/components/HeaderAvatar";
import { Button } from "@/components/ui/Button";
import { Toggle } from "@/components/ui/Toggle";
import { ReminderPopupSetting } from "@/components/ReminderPopupSetting";
import { getSession, logout } from "@/lib/auth";
import { applyHighContrast, highContrastItem } from "@/lib/highContrast";
import { PALETTE_LABEL, PALETTE_NAMES, applyPalette, paletteItem } from "@/lib/palette";
import type { PaletteName } from "@/lib/palette";
import { autoOpenReminderPopupItem } from "@/lib/storage";
import { applyTextSize, textSizeItem } from "@/lib/textSize";
import type { TextSize } from "@/lib/textSize";
import { initTheme, toggleTheme } from "@/lib/theme";
import type { ThemeMode } from "@/lib/theme";
import { MIC_PERMISSION_KEY } from "@/types";
import type { AuthSession } from "@/types";

// Màu đại diện mỗi tông trên chấm chọn — Paper dùng nền giấy đặc trưng (chứ
// không phải primary teal của nó, không "đọc" được là Paper); 3 tông còn lại
// dùng primary vì đã đủ nổi bật để nhận ra. Giá trị lấy đúng từ tailwind.css.
const PALETTE_SWATCH: Record<PaletteName, string> = {
  paper: "#fffedd",
  jade: "#2f6b4f",
  plum: "#6b3f73",
  quartz: "#3d4a54",
};

const TEXT_SIZE_OPTIONS: { value: TextSize; label: string }[] = [
  { value: "sm", label: "S" },
  { value: "md", label: "M" },
  { value: "lg", label: "L" },
];

const WEB_APP_URL = import.meta.env.WXT_WEB_APP_URL;

function formatExpiry(expiresAt: number): string {
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(expiresAt));
}

function openWebApp(): void {
  void chrome.tabs.create({ url: WEB_APP_URL });
}

/**
 * Xin quyền micro ngay tại trang options.
 *
 * Bắt buộc phải làm ở đây chứ không phải trong offscreen document: offscreen
 * không hiện được hộp thoại xin quyền của Chrome, gọi getUserMedia ở đó khi
 * chưa có quyền là bị từ chối thẳng. Options page mở trong tab thật nên prompt
 * hiện được; xin xong ghi cờ vào storage cho popup đọc.
 */
async function requestMicPermission(): Promise<boolean> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  // Tắt ngay track vừa mở — chỉ cần cái quyền, không cần thu gì ở trang này.
  stream.getTracks().forEach((track) => track.stop());
  await chrome.storage.local.set({ [MIC_PERMISSION_KEY]: true });
  return true;
}

export function App() {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  const [pending, setPending] = useState(false);
  // undefined = chưa đọc xong storage, tránh nháy nhầm trạng thái "chưa cấp".
  const [micGranted, setMicGranted] = useState<boolean | undefined>(undefined);
  const [micError, setMicError] = useState("");
  const [autoOpenReminder, setAutoOpenReminder] = useState<boolean | undefined>(undefined);
  const [savingReminderSetting, setSavingReminderSetting] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>("light");
  const [palette, setPaletteState] = useState<PaletteName>("paper");
  const [textSize, setTextSizeState] = useState<TextSize>("md");
  const [highContrast, setHighContrastState] = useState(false);

  useEffect(() => {
    void getSession().then(setSession);
    void chrome.storage.local
      .get(MIC_PERMISSION_KEY)
      .then((stored) => setMicGranted(stored[MIC_PERMISSION_KEY] === true));
    void autoOpenReminderPopupItem.getValue().then(setAutoOpenReminder);
    void initTheme().then(setTheme);
    void paletteItem.getValue().then((value) => {
      setPaletteState(value);
      applyPalette(value);
    });
    void textSizeItem.getValue().then((value) => {
      setTextSizeState(value);
      applyTextSize(value);
    });
    void highContrastItem.getValue().then((value) => {
      setHighContrastState(value);
      applyHighContrast(value);
    });
    return autoOpenReminderPopupItem.watch((value) => setAutoOpenReminder(value));
  }, []);

  async function handleToggleTheme() {
    setTheme(await toggleTheme(theme));
  }

  async function handlePaletteChange(name: PaletteName) {
    setPaletteState(name);
    applyPalette(name);
    await paletteItem.setValue(name);
  }

  async function handleTextSizeChange(size: TextSize) {
    setTextSizeState(size);
    applyTextSize(size);
    await textSizeItem.setValue(size);
  }

  async function handleHighContrastChange(enabled: boolean) {
    setHighContrastState(enabled);
    applyHighContrast(enabled);
    await highContrastItem.setValue(enabled);
  }

  async function handleReminderPopupChange(checked: boolean) {
    setSavingReminderSetting(true);
    try {
      await autoOpenReminderPopupItem.setValue(checked);
      setAutoOpenReminder(checked);
    } finally {
      setSavingReminderSetting(false);
    }
  }

  async function handleGrantMic() {
    setMicError("");
    try {
      setMicGranted(await requestMicPermission());
    } catch {
      setMicGranted(false);
      setMicError("Chrome đã từ chối quyền micro. Mở khoá ở biểu tượng ổ khoá trên thanh địa chỉ rồi thử lại.");
    }
  }

  async function handleForget() {
    setPending(true);
    try {
      await logout();
      setSession(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="app-shell flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-md items-center justify-between gap-2.5 px-6 py-6">
        <div className="flex items-center gap-2.5">
          <img src="/mondaiy-mascot.png" width={28} height={28} alt="mondaiy" className="shrink-0" />
          <span className="font-heading text-lg font-semibold text-primary">
            mond<span className="text-focus">ai</span>y
          </span>
        </div>
        <div className="flex items-center gap-2">
          {session && <HeaderAvatar avatarUrl={session.avatarUrl} />}
          <button
            type="button"
            onClick={() => void handleToggleTheme()}
            aria-label="Đổi giao diện sáng/tối"
            title={`Giao diện: ${theme === "dark" ? "Tối" : "Sáng"}`}
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-focus/10 hover:text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus"
          >
            {theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          </button>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-6 pb-10">
        <div className="app-panel w-full max-w-sm rounded-2xl p-6 text-center sm:p-8">
          {session === undefined && <p className="text-xs text-muted">Đang kiểm tra...</p>}

          {session === null && (
            <div className="flex flex-col gap-5">
              <div className="space-y-1.5">
                <h1 className="font-heading text-lg font-semibold text-primary">Chưa đồng bộ</h1>
                <p className="text-xs text-secondary">
                  Extension tự lấy phiên đăng nhập từ mondaiy khi bạn mở web app trong 1 tab —
                  không có form đăng nhập riêng ở đây.
                </p>
              </div>
              <Button onClick={openWebApp} className="gap-2">
                Mở mondaiy để đăng nhập
                <ExternalLink className="h-4 w-4" />
              </Button>
            </div>
          )}

          {session && (
            <div className="flex flex-col gap-5">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-focus/15">
                {session.avatarUrl ? (
                  <img
                    src={session.avatarUrl}
                    alt="Ảnh đại diện"
                    width={48}
                    height={48}
                    referrerPolicy="no-referrer"
                    className="h-12 w-12 rounded-full object-cover"
                  />
                ) : (
                  <Mail className="h-5 w-5 text-primary" />
                )}
              </div>
              <div className="space-y-1">
                <h1 className="font-heading text-lg font-semibold text-primary">Đã đồng bộ</h1>
                <p className="text-xs text-secondary">
                  Phiên hết hạn: {formatExpiry(session.expiresAt)}
                </p>
              </div>
              <Button variant="secondary" onClick={() => void handleForget()} disabled={pending} className="gap-2">
                <Trash2 className="h-4 w-4" />
                Quên phiên đã đồng bộ
              </Button>
              <p className="text-[11px] text-muted">
                Chỉ xoá bản sao ở extension — không đăng xuất khỏi mondaiy trên web.
              </p>
            </div>
          )}
        </div>
      </main>

      <section className="mx-auto w-full max-w-sm px-6 pb-4">
        <div className="app-panel flex flex-col gap-5 rounded-2xl p-6">
          <h2 className="font-heading text-base font-semibold text-primary">Hiển thị</h2>

          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Tông màu</p>
            <div className="flex gap-3" role="radiogroup" aria-label="Tông màu">
              {PALETTE_NAMES.map((name) => (
                <button
                  key={name}
                  type="button"
                  role="radio"
                  aria-checked={palette === name}
                  aria-label={PALETTE_LABEL[name]}
                  title={PALETTE_LABEL[name]}
                  onClick={() => void handlePaletteChange(name)}
                  style={{ backgroundColor: PALETTE_SWATCH[name] }}
                  className={`flex h-9 w-9 items-center justify-center rounded-full border-2 transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${
                    palette === name ? "border-primary shadow-md" : "border-border"
                  }`}
                >
                  {palette === name && (
                    <Check
                      className="h-4 w-4"
                      style={{ color: name === "paper" ? "#356f83" : "#ffffff" }}
                      aria-hidden
                    />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">Cỡ chữ</p>
            <div className="flex rounded-lg border border-border bg-app-bg p-1" role="radiogroup" aria-label="Cỡ chữ">
              {TEXT_SIZE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="radio"
                  aria-checked={textSize === option.value}
                  onClick={() => void handleTextSizeChange(option.value)}
                  className={`flex-1 rounded-md py-1.5 text-sm font-semibold transition-colors ${
                    textSize === option.value
                      ? "bg-surface text-primary shadow-sm"
                      : "text-muted hover:text-secondary"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <span className="text-sm text-secondary">Độ tương phản cao</span>
            <Toggle
              aria-label="Độ tương phản cao"
              checked={highContrast}
              onChange={(enabled) => void handleHighContrastChange(enabled)}
            />
          </label>
        </div>
      </section>

      <section className="mx-auto w-full max-w-sm px-6 pb-4">
        <ReminderPopupSetting
          checked={autoOpenReminder ?? false}
          disabled={autoOpenReminder === undefined || savingReminderSetting}
          onChange={(checked) => void handleReminderPopupChange(checked)}
        />
      </section>

      <section className="mx-auto w-full max-w-sm px-6 pb-10">
        <div className="app-panel flex flex-col gap-3 rounded-2xl p-6 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-focus/15">
            <Mic className="h-5 w-5 text-primary" />
          </div>
          <div className="space-y-1">
            <h2 className="font-heading text-base font-semibold text-primary">Ghi âm cuộc họp</h2>
            <p className="text-xs text-secondary">
              Cần quyền micro một lần để ghi tiếng của bạn song song với tiếng từ tab cuộc họp.
            </p>
          </div>

          {micGranted === undefined && <p className="text-xs text-muted">Đang kiểm tra...</p>}

          {micGranted === true && (
            <p className="text-xs font-semibold text-primary">Đã cấp quyền micro.</p>
          )}

          {micGranted === false && (
            <Button onClick={() => void handleGrantMic()} className="gap-2">
              <Mic className="h-4 w-4" />
              Cấp quyền micro
            </Button>
          )}

          {micError && <p className="text-[11px] text-danger">{micError}</p>}

          <p className="text-[11px] text-muted">
            Chỉ ghi khi bạn tự bấm nút trong Side Panel, và dừng ngay khi bạn bấm dừng.
          </p>
        </div>
      </section>

      <footer className="pb-6 text-center text-[11px] text-muted">mondaiy — chỉ để thông báo</footer>
    </div>
  );
}
