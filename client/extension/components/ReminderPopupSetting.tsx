import { BellRing } from "lucide-react";
import { Toggle } from "./ui/Toggle";

interface ReminderPopupSettingProps {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}

export function ReminderPopupSetting({
  checked,
  disabled = false,
  onChange,
}: ReminderPopupSettingProps) {
  return (
    <section className="app-panel flex items-center gap-4 rounded-2xl p-5 sm:p-6">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-focus/15">
        <BellRing className="h-5 w-5 text-primary" aria-hidden />
      </div>

      <div className="min-w-0 flex-1">
        <h2 className="font-heading text-base font-semibold text-primary">Tự mở khi đến hạn</h2>
        <p className="mt-1 text-xs leading-relaxed text-secondary">
          Tự bung Side Panel và hiện việc đang được nhắc. Nếu Chrome không thể mở,
          thông báo hệ điều hành vẫn xuất hiện.
        </p>
      </div>

      <Toggle
        aria-label="Tự mở Side Panel khi reminder đến hạn"
        checked={checked}
        disabled={disabled}
        onChange={onChange}
      />
    </section>
  );
}
