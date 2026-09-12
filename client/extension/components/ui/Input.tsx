import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement>;

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className = "", ...props },
  ref
) {
  return (
    <input
      ref={ref}
      className={`w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-secondary shadow-inner transition-shadow placeholder:text-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-focus ${className}`}
      {...props}
    />
  );
});
