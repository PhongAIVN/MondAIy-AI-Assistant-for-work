/**
 * Gom route con cùng “màn hình” để không animate lại khi chỉ đổi param
 * (vd. conversation id), nhưng vẫn animate khi đổi mục nav chính.
 */
export function getPageTransitionKey(pathname: string): string {
  const path = pathname.split('?')[0] || '/';
  const parts = path.split('/').filter(Boolean);

  if (parts.length === 0) return '/';

  if (parts[0] === 'briefing') return '/briefing';
  if (parts[0] === 'data-privacy') return '/data-privacy';
  if (parts[0] === 'blog' && parts.length >= 2) return '/blog';

  if (parts[0] === 'admin') {
    if (parts[1] === 'programs' && parts.length >= 3) return '/admin/programs';
    if (parts.length >= 2) return `/${parts[0]}/${parts[1]}`;
    return '/admin';
  }

  return `/${parts[0]}`;
}
