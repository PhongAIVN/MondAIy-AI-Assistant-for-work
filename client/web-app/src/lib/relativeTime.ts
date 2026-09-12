/** Định dạng thời gian tương đối ngắn gọn từ một mốc ISO thật (vd. "5p"/"5m",
 * "2g"/"2h") — thay cho chuỗi tiếng Anh cứng kiểu "2 hours ago" trước đây. */
export function formatRelativeTime(iso: string, language: 'en' | 'vi'): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;

  const diffMin = Math.floor((Date.now() - then) / 60000);
  if (diffMin < 1) return language === 'vi' ? 'vừa' : 'now';
  if (diffMin < 60) return language === 'vi' ? `${diffMin}p` : `${diffMin}m`;

  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return language === 'vi' ? `${diffHour}g` : `${diffHour}h`;

  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return language === 'vi' ? `${diffDay}ng` : `${diffDay}d`;

  return new Date(iso).toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-GB', {
    day: '2-digit',
    month: 'short',
  });
}
