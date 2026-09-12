import type { ButtonHTMLAttributes } from "react";

export interface ToggleProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  checked: boolean;
  onChange: (checked: boolean) => void;
  "aria-label": string;
  size?: "sm" | "md";
}

/**
 * Công tắc bật/tắt dạng pill switch cho giao diện cài đặt.
 * Căn chỉnh tuyệt đối bằng `left-1 top-1` và trượt bằng `translate-x`,
 * đảm bảo thumb nằm gọn bên trong rãnh và giữ đều khoảng cách 4px ở cả 2 trạng thái.
 */
export function Toggle({
  checked,
  onChange,
  disabled = false,
  "aria-label": ariaLabel,
  size = "md",
  className = "",
  ...props
}: ToggleProps) {
  const isSm = size === "sm";

  return (
    <button
      type="button"
      role="switch"
      aria-label={ariaLabel}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex shrink-0 items-center rounded-full border transition-colors duration-200 cursor-pointer disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${
        isSm ? "h-5 w-9" : "h-6 w-11"
      } ${
        checked ? "border-primary bg-primary" : "border-border bg-surface"
      } ${className}`}
      {...props}
    >
      <span
        aria-hidden
        className={`pointer-events-none absolute left-1 top-1 rounded-full shadow-sm transition-transform duration-200 ${
          isSm ? "h-3 w-3" : "h-4 w-4"
        } ${
          checked
            ? `${isSm ? "translate-x-4" : "translate-x-5"} bg-app-bg`
            : "translate-x-0 bg-muted"
        }`}
      />
    </button>
  );
}
