/** Intent gate: Gmail pipeline chỉ chạy khi user gọi rõ email/hộp thư. */
export function isGmailBriefingIntent(input: string): boolean {
  const text = input.normalize('NFKC').toLowerCase().trim();
  const folded = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  // A write/action request wins over the read-only Gmail briefing route. For
  // example, “thêm việc trong email vào lịch” must go to the productivity
  // proposal flow, not start a second mailbox fetch.
  const isProductivityWrite =
    /(?:them|tao|dat|ghi|len lich|nhac toi|create|add|schedule)/.test(folded) &&
    /(?:lich|calendar|event|meeting|workshop|task|todo|cong viec|nhiem vu)/.test(folded);
  if (isProductivityWrite) return false;
  const mentionsMailbox = /\b(gmail|email|e-mail|mail|inbox|hộp thư|thư điện tử)\b/.test(text);
  const asksForEvidence = /(tóm tắt|tong hop|tổng hợp|summary|brief|nội dung|deadline|hạn|việc cần làm|action|thay đổi|mâu thuẫn|conflict|email nào)/.test(text);
  return mentionsMailbox && asksForEvidence;
}
