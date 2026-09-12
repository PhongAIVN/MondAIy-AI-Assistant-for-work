import { afterEach, describe, expect, it, vi } from 'vitest';

import { runVisionAction } from '../src/lib/visionApi';

describe('runVisionAction', () => {
  afterEach(() => vi.restoreAllMocks());

  it('sends pasted image as JSON and returns text-first response', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ actionType: 'task', response: 'Gửi bản demo trước thứ 6' }), { status: 200 }),
    );
    const result = await runVisionAction('https://api.example.test', 'token', 'data:image/png;base64,Zm9v', 'Đọc ảnh');
    expect(result.response).toBe('Gửi bản demo trước thứ 6');
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/api/v1/vision/actions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ imageDataUrl: 'data:image/png;base64,Zm9v', message: 'Đọc ảnh' }),
      }),
    );
  });

  it('throws with server detail message when the request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Ảnh vượt quá giới hạn 8 MB.' }), { status: 422 }),
    );
    await expect(
      runVisionAction('https://api.example.test', 'token', 'data:image/png;base64,Zm9v', 'Đọc ảnh'),
    ).rejects.toThrow('Ảnh vượt quá giới hạn 8 MB.');
  });
});
