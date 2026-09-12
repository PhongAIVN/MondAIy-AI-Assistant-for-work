// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReminderPopupSetting } from "./ReminderPopupSetting";

afterEach(cleanup);

describe("ReminderPopupSetting", () => {
  it("hiện trạng thái tắt mặc định và yêu cầu bật khi người dùng bấm", () => {
    const onChange = vi.fn();
    render(<ReminderPopupSetting checked={false} onChange={onChange} />);

    const toggle = screen.getByRole("switch", { name: /tự mở side panel/i });
    expect(toggle.getAttribute("aria-checked")).toBe("false");

    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("yêu cầu tắt khi người dùng bấm lại trạng thái đang bật", () => {
    const onChange = vi.fn();
    render(<ReminderPopupSetting checked onChange={onChange} />);

    fireEvent.click(screen.getByRole("switch", { name: /tự mở side panel/i }));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});
