// @vitest-environment jsdom

// Hợp đồng vỏ PWA. Ba nhóm điều kiện:
//   manifest        — đủ trường để trình duyệt cho cài, icon phải là file có thật
//   service worker  — TUYỆT ĐỐI không cache /api/*, vì đệm sai phạm vi là rò
//                     dữ liệu giữa các tài khoản dùng chung một máy
//   InstallPrompt   — không làm phiền khi đã cài, có đường đi riêng cho iOS,
//                     và đã đóng thì không hiện lại

import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  API_PATH_PREFIX,
  pwaOptions,
  SHELL_GLOB_PATTERNS,
} from '../pwa.config';
import { InstallPrompt, PWA_INSTALL_DISMISSED_KEY } from '../src/components/pwa/InstallPrompt';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** Đọc manifest đúng như trình duyệt sẽ đọc: từ file tĩnh trong public/. */
const readManifest = () =>
  JSON.parse(readFileSync(path.join(projectRoot, 'public/manifest.webmanifest'), 'utf8'));

/** Đặt user agent cho một bài test — jsdom không cho gán trực tiếp. */
const setUserAgent = (value: string) => {
  Object.defineProperty(window.navigator, 'userAgent', { value, configurable: true });
};

/** Giả lập media query display-mode để phân biệt đang chạy standalone hay không. */
const setDisplayMode = (standalone: boolean) => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: (query: string) => ({
      matches: standalone && query.includes('standalone'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      onchange: null,
      dispatchEvent: () => false,
    }),
  });
};

/** Dựng sự kiện beforeinstallprompt giả, giữ tham chiếu để kiểm prompt() có được gọi. */
const createInstallPromptEvent = () => {
  const prompt = vi.fn(async () => {});
  const event = Object.assign(new Event('beforeinstallprompt'), {
    prompt,
    userChoice: Promise.resolve({ outcome: 'accepted' as const }),
  });
  return { event, prompt };
};

const USER_AGENT_ANDROID =
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36';
const USER_AGENT_IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

beforeEach(() => {
  localStorage.clear();
  setDisplayMode(false);
  setUserAgent(USER_AGENT_ANDROID);
});

afterEach(cleanup);

describe('manifest — đủ để trình duyệt cho cài', () => {
  it('có đủ trường bắt buộc và đúng bảng màu hiện tại', () => {
    const manifest = readManifest();

    expect(manifest.name).toBe('mondaiy');
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBeTruthy();
    expect(manifest.display).toBe('standalone');
    // Màu lấy từ biến CSS trong src/index.css, không bịa.
    expect(manifest.theme_color).toBe('#356F83');
    expect(manifest.background_color).toBe('#FFFFDD');
  });

  it('trỏ vào icon 192 và 512 có thật trong public/, kèm bản maskable', () => {
    const icons: Array<{ src: string; sizes: string; purpose?: string }> = readManifest().icons;

    for (const icon of icons) {
      expect(existsSync(path.join(projectRoot, 'public', icon.src))).toBe(true);
    }

    expect(icons.some((icon) => icon.sizes === '192x192')).toBe(true);
    expect(icons.some((icon) => icon.sizes === '512x512')).toBe(true);
    expect(icons.some((icon) => icon.purpose?.includes('maskable'))).toBe(true);
  });

  it('được khai báo trong index.html để trình duyệt tìm thấy', () => {
    const html = readFileSync(path.join(projectRoot, 'index.html'), 'utf8');
    expect(html).toContain('rel="manifest"');
    expect(html).toContain('/manifest.webmanifest');
  });
});

describe('service worker — không được chạm vào /api/*', () => {
  it('dùng service worker viết tay để nhận push', () => {
    expect(pwaOptions.strategies).toBe('injectManifest');
    expect(pwaOptions.srcDir).toBe('src');
    expect(pwaOptions.filename).toBe('sw.ts');
  });

  it('chỉ precache tài nguyên vỏ tĩnh, không có đường dẫn API', () => {
    for (const pattern of SHELL_GLOB_PATTERNS) {
      expect(pattern).not.toContain(API_PATH_PREFIX);
    }
    // Đuôi file được precache đều là tài sản build, không phải phản hồi JSON.
    expect(SHELL_GLOB_PATTERNS.join(',')).not.toContain('json');
    expect(SHELL_GLOB_PATTERNS.join(',')).toContain('mp3');
    expect(SHELL_GLOB_PATTERNS.join(',')).not.toContain('html');
    // Bundle phiên bản hóa phải luôn đi network. Precache bundle rồi dọn cache
    // trong lúc iOS khôi phục document cũ là nguyên nhân của màn hình trống.
    expect(SHELL_GLOB_PATTERNS.join(',')).not.toContain('js');
    expect(SHELL_GLOB_PATTERNS.join(',')).not.toContain('css');
  });

  it('không chặn navigation bằng index.html đã cache', () => {
    const serviceWorker = readFileSync(path.join(projectRoot, 'src/sw.ts'), 'utf8');

    expect(serviceWorker).not.toContain("from 'workbox-routing'");
    expect(serviceWorker).not.toContain('new NavigationRoute');
    expect(serviceWorker).not.toContain('createHandlerBoundToURL(');
    expect(serviceWorker).not.toContain("'/index.html'");
    expect(pwaOptions).not.toHaveProperty('workbox');
    expect(pwaOptions.injectManifest.globPatterns).toEqual(SHELL_GLOB_PATTERNS);
  });

  it('tự cập nhật khi có bản mới thay vì giữ vỏ cũ', () => {
    const serviceWorker = readFileSync(path.join(projectRoot, 'src/sw.ts'), 'utf8');

    expect(pwaOptions.registerType).toBe('autoUpdate');
    expect(serviceWorker).toContain('event.waitUntil(self.skipWaiting())');
    expect(serviceWorker).toContain('event.waitUntil(self.clients.claim())');
  });

  it('không cho CDN hoặc WebKit giữ script đăng ký service worker cũ', () => {
    const vercel = JSON.parse(readFileSync(path.join(projectRoot, 'vercel.json'), 'utf8'));
    const headers: Array<{ source: string; headers: Array<{ key: string; value: string }> }> =
      vercel.headers;

    for (const source of ['/sw.js', '/registerSW.js']) {
      const rule = headers.find((item) => item.source === source);
      expect(rule?.headers).toContainEqual({
        key: 'Cache-Control',
        value: 'no-cache, no-store, must-revalidate',
      });
    }
  });
});

describe('khởi động trên iPhone', () => {
  it('build xuống ES2019 để không loại Safari/iOS cũ trước khi React mount', () => {
    const viteConfig = readFileSync(path.join(projectRoot, 'vite.config.ts'), 'utf8');
    expect(viteConfig).toContain("target: 'es2019'");
  });

  it('có fallback HTML và nút dọn PWA nếu bundle lỗi trước React ErrorBoundary', () => {
    const html = readFileSync(path.join(projectRoot, 'index.html'), 'utf8');
    expect(html).toContain('id="app-boot-fallback"');
    expect(html).toContain('Mondaiy chưa mở được');
    expect(html).toContain('window.mondaiyRecover');
    expect(html).toContain('serviceWorker.getRegistrations');
    expect(html).toContain('window.caches.delete');
  });
});

describe('InstallPrompt', () => {
  it('không hiện gì khi app đã chạy ở chế độ standalone', async () => {
    setDisplayMode(true);
    const { event } = createInstallPromptEvent();

    render(<InstallPrompt />);
    window.dispatchEvent(event);

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('hiện nút cài khi trình duyệt phát beforeinstallprompt và gọi prompt() khi bấm', async () => {
    const { event, prompt } = createInstallPromptEvent();

    render(<InstallPrompt />);
    window.dispatchEvent(event);

    const installButton = await screen.findByRole('button', { name: 'Cài đặt' });
    await userEvent.click(installButton);

    await waitFor(() => expect(prompt).toHaveBeenCalledTimes(1));
  });

  it('hiện hướng dẫn thủ công trên iOS Safari vì Apple không phát sự kiện cài', async () => {
    setUserAgent(USER_AGENT_IPHONE);

    render(<InstallPrompt />);

    expect(await screen.findByText(/Thêm mondaiy vào Màn hình chính/)).toBeTruthy();
    expect(screen.getByText(/nút Chia sẻ trong Safari/)).toBeTruthy();
    // Không được vẽ nút cài trên iOS: bấm vào cũng không làm được gì.
    expect(screen.queryByRole('button', { name: 'Cài đặt' })).toBeNull();
  });

  it('người dùng đóng rồi thì không hiện lại ở lần mở app sau', async () => {
    setUserAgent(USER_AGENT_IPHONE);

    const { unmount } = render(<InstallPrompt />);
    await userEvent.click(screen.getByRole('button', { name: 'Đóng lời nhắc cài đặt' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    unmount();

    expect(localStorage.getItem(PWA_INSTALL_DISMISSED_KEY)).toBe('true');

    // Lần render sau mô phỏng mở lại app: lựa chọn phải còn được nhớ.
    render(<InstallPrompt />);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
