import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import type { Plugin } from 'vite';

/**
 * Một build id, hai nơi tiêu thụ — và cố ý chỉ có MỘT nguồn sinh ra nó.
 *
 * `__BUILD_ID__` được nén thẳng vào bundle đang chạy; `version.json` nằm cạnh
 * nó trên server. Nếu hai giá trị này do hai chỗ khác nhau sinh ra thì chúng sẽ
 * lệch nhau vì lý do vô hại, và app sẽ báo "có bản mới" mãi mãi. Vì vậy hàm
 * `resolveBuildId()` là nơi duy nhất quyết định giá trị đó.
 */
export function resolveBuildId(): string {
  // Trên Vercel không có .git, nhưng có sẵn SHA trong biến môi trường.
  const fromCi = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA;
  if (fromCi) return fromCi.slice(0, 12);

  try {
    return execSync('git rev-parse --short=12 HEAD', {
      stdio: ['ignore', 'pipe', 'ignore'],
    })
      .toString()
      .trim();
  } catch {
    // Không có git và không có CI env: rơi về mốc build. Vẫn đổi mỗi lần build
    // nên vẫn phát hiện được lệch, chỉ là không truy ngược ra commit nào.
    return `t${Date.now().toString(36)}`;
  }
}

/**
 * Ghi `version.json` vào thư mục output sau khi build xong.
 *
 * Đặt trong `dist/` chứ không phải `public/`: file trong `public/` được commit
 * và sẽ mang giá trị của lần build gần nhất trên máy ai đó, tức là một nguồn
 * sự thật thứ hai đã cũ ngay từ lúc sinh ra.
 */
export function buildIdPlugin(buildId: string): Plugin {
  return {
    name: 'p004-build-id',
    apply: 'build',
    closeBundle() {
      const outDir = join(process.cwd(), 'dist');
      mkdirSync(outDir, { recursive: true });
      writeFileSync(
        join(outDir, 'version.json'),
        `${JSON.stringify({ buildId }, null, 2)}\n`,
        'utf8',
      );
    },
  };
}
