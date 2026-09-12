export function isApplePlatform(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent);
}

export function shortcutLabel(key: string): string {
  return isApplePlatform() ? `⌘${key}` : `Ctrl ${key}`;
}
