import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-app-bg shadow-md hover:brightness-110",
  secondary: "border border-border bg-surface text-secondary hover:brightness-95",
  danger: "bg-danger text-app-bg shadow-md hover:brightness-110",
};

export function Button({
  variant = "primary",
  type = "button",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus ${VARIANT_CLASS[variant]} ${className}`}
      {...props}
    />
  );
}
