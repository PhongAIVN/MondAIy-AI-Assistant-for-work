import { describe, expect, it } from "vitest";
import { redactSensitive } from "./pageExtraction";

describe("redactSensitive", () => {
  it("che dãy số dài 13-19 chữ số", () => {
    expect(redactSensitive("Số thẻ 4111111111111111 hết hạn")).toBe(
      "Số thẻ **************** hết hạn",
    );
  });

  it("giữ nguyên số ngắn hơn 13 chữ số", () => {
    expect(redactSensitive("Mã đơn hàng 12345")).toBe("Mã đơn hàng 12345");
  });

  it("không đổi văn bản không chứa số dài", () => {
    expect(redactSensitive("Nội dung trang bình thường.")).toBe("Nội dung trang bình thường.");
  });
});
