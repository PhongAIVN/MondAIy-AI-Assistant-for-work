import { describe, expect, it, vi } from 'vitest';

import { imageFileFromClipboard } from '../src/lib/imageClipboard';

describe('imageFileFromClipboard', () => {
  it('reads macOS-style image clipboard items even when files is empty', () => {
    const file = new File(['png'], 'screenshot.png', { type: 'image/png' });
    const data = { items: [{ kind: 'file', type: 'image/png', getAsFile: () => file }], files: [] } as unknown as DataTransfer;
    expect(imageFileFromClipboard(data)).toBe(file);
  });

  it('ignores text-only clipboard content', () => {
    const data = { items: [{ kind: 'string', type: 'text/plain', getAsFile: vi.fn() }], files: [] } as unknown as DataTransfer;
    expect(imageFileFromClipboard(data)).toBeNull();
  });

  it('falls back to files when items has no image entry', () => {
    const file = new File(['png'], 'from-finder.png', { type: 'image/png' });
    const data = { items: [], files: [file] } as unknown as DataTransfer;
    expect(imageFileFromClipboard(data)).toBe(file);
  });
});
