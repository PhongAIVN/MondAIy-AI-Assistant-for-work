/** Che số thẻ/tài khoản dài (13-19 chữ số liền nhau) trước khi rời khỏi trang
 * nguồn — cùng ngưỡng với client/Test extension/extension/lib/redact.ts.
 * Áp dụng trước khi gửi text lên backend tóm tắt (POST
 * /tasks/summarize-page-extraction), không phải sau. */
export function redactSensitive(text: string): string {
  return text
    .replace(/\beyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}\b/g, "[REDACTED_TOKEN]")
    .replace(/\b\d{13,19}\b/g, (match) => "*".repeat(match.length));
}

export interface ExtractedPageData {
  title: string;
  url: string;
  text: string;
  // Nhãn nhận diện nguồn cụ thể hơn url khi trang là SPA route tĩnh (vd Zalo
  // web luôn ở chat.zalo.me dù đang mở nhóm nào) — đoán bằng heading ngữ
  // nghĩa gần nhất (xem guessSourceContext() ở App.tsx), rỗng nếu không có.
  sourceContext: string;
}
