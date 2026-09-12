/** Định dạng timestamp từ API để không lộ chuỗi ISO thô trong hội thoại. */
export function formatConversationTimestamp(value: string, language: 'en' | 'vi'): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const locale = language === 'vi' ? 'vi-VN' : 'en-GB';
  const now = new Date();
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  if (sameDay) {
    return date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
  }

  return date.toLocaleString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
