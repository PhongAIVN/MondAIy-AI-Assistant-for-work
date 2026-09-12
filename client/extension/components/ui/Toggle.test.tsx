// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Toggle } from "./Toggle";

afterEach(cleanup);

describe("Toggle component", () => {
  it("render trạng thái tắt (aria-checked=false) và gọi onChange(true) khi bấm", () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} aria-label="Chế độ tối" />);

    const button = screen.getByRole("switch", { name: "Chế độ tối" });
    expect(button.getAttribute("aria-checked")).toBe("false");

    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("render trạng thái bật (aria-checked=true) và gọi onChange(false) khi bấm", () => {
    const onChange = vi.fn();
    render(<Toggle checked={true} onChange={onChange} aria-label="Độ tương phản cao" />);

    const button = screen.getByRole("switch", { name: "Độ tương phản cao" });
    expect(button.getAttribute("aria-checked")).toBe("true");

    fireEvent.click(button);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("không gọi onChange khi đang disabled", () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} disabled onChange={onChange} aria-label="Tự mở khi đến hạn" />);

    const button = screen.getByRole("switch", { name: "Tự mở khi đến hạn" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    fireEvent.click(button);
    expect(onChange).not.toHaveBeenCalled();
  });
});
