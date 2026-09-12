// @vitest-environment jsdom
/**
 * Lane B2 — bằng chứng đối chiếu FE↔BE: mock ở tầng `global.fetch` (không
 * mock lib client) bằng ĐÚNG body JSON đã lấy từ backend THẬT đang chạy cục
 * bộ (uvicorn thật, router/quota/cache/DB thật, chỉ biên Google + LLM bị giả
 * lập — xem scratchpad/gdrive-e2e/server.py). Payload dán nguyên văn từ:
 *
 *   curl http://127.0.0.1:8091/api/v1/google-drive/files ...
 *   curl -X POST http://127.0.0.1:8091/api/v1/google-docs/task-proposals ...
 *
 * chạy lúc 2026-08-19 21:28-21:32 (giờ VN), userId=1/2, GOOGLE_DOCUMENT_READS_PER_DAY=2.
 * Test này vì vậy xác nhận cả (a) UI hiển thị đúng và (b) apiClient.ts parse
 * đúng hình dạng JSON thật mà backend trả — không phải hình dạng tôi đoán.
 */
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { GoogleDriveFilePicker } from '../src/components/sources/GoogleDriveFilePicker';

// --- Response thật, lấy nguyên văn từ backend (xem docstring trên) ---------

const REAL_DRIVE_FILES_LIST = {
  files: [
    {
      id: 'e2e-doc-short-000000000001',
      name: 'Kế hoạch tuần (ngắn)',
      kind: 'document',
      modifiedTime: '2026-08-19T02:00:00Z',
      webViewLink: 'https://docs.google.com/document/d/e2e-doc-short-000000000001/edit',
    },
    {
      id: 'e2e-doc-long-0000000000001',
      name: 'Biên bản họp (dài, sẽ bị cắt)',
      kind: 'document',
      modifiedTime: '2026-08-18T02:00:00Z',
      webViewLink: 'https://docs.google.com/document/d/e2e-doc-long-0000000000001/edit',
    },
    {
      id: 'e2e-sheet-1-00000000000001',
      name: 'Backlog nhóm',
      kind: 'spreadsheet',
      modifiedTime: '2026-08-16T02:00:00Z',
      webViewLink: 'https://docs.google.com/spreadsheets/d/e2e-sheet-1-00000000000001/edit',
    },
  ],
  nextPageToken: null,
};

const REAL_NORMAL_SCAN = {
  documentId: 'e2e-doc-short-000000000001',
  timezone: 'Asia/Ho_Chi_Minh',
  proposals: [
    {
      paragraphIndex: 0,
      title: '[E2E] Hoàn thành báo cáo tuần trước thứ Sáu',
      detail: 'Trích từ Google Docs — LLM extraction bị giả lập cho lượt kiểm chứng này.',
      assignee: null,
      dueAt: null,
      allDay: false,
      matchedUser: false,
      needsConfirmation: false,
      clarificationQuestion: null,
      dateAmbiguous: false,
      source: 'Google Docs',
      sourceUrl: 'https://docs.google.com/document/d/e2e-doc-short-000000000001/edit',
    },
  ],
  truncated: false,
  quotaRemaining: 1,
};

const REAL_TRUNCATED_SCAN = {
  documentId: 'e2e-doc-long-0000000000001',
  timezone: 'Asia/Ho_Chi_Minh',
  proposals: [
    {
      paragraphIndex: 0,
      title: '[E2E] Nội dung biên bản họp rất dài để kiểm tra cắt bớt trước khi',
      detail: 'Trích từ Google Docs — LLM extraction bị giả lập cho lượt kiểm chứng này.',
      assignee: null,
      dueAt: null,
      allDay: false,
      matchedUser: false,
      needsConfirmation: false,
      clarificationQuestion: null,
      dateAmbiguous: false,
      source: 'Google Docs',
      sourceUrl: 'https://docs.google.com/document/d/e2e-doc-long-0000000000001/edit',
    },
  ],
  truncated: true,
  quotaRemaining: 0,
};

// curl -i .../task-proposals lần thứ 3 -> HTTP/1.1 429, body nguyên văn:
const REAL_QUOTA_429_BODY = {
  detail:
    'Bạn đã dùng hết 2 lượt đọc Google Docs/Sheets trong hôm nay. Hạn mức được cấp lại lúc 00:00 ngày 2026-08-20 (giờ Asia/Ho_Chi_Minh).',
};

// 30 lượt liên tiếp GET /google-drive/files -> HTTP/1.1 429, body nguyên văn
// (slowapi's default handler — KHÁC shape với quota 429 ở trên, {"error"}
// chứ không phải {"detail"}; apiClient.ts phải đọc được cả hai).
const REAL_RATE_LIMIT_429_BODY = { error: 'Rate limit exceeded: 30 per 1 minute' };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('GoogleDriveFilePicker đối chiếu với response THẬT từ backend đang chạy', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('trạng thái bình thường: liệt kê + chọn file trả đúng thứ backend thật trả về', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (String(url).includes('/google-drive/files')) return Promise.resolve(jsonResponse(REAL_DRIVE_FILES_LIST));
      if (String(url).includes('/google-docs/task-proposals') && init?.method === 'POST') {
        expect(JSON.parse(String(init.body))).toEqual({ documentId: 'e2e-doc-short-000000000001' });
        return Promise.resolve(jsonResponse(REAL_NORMAL_SCAN));
      }
      throw new Error(`unmocked fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<GoogleDriveFilePicker accessToken="token" />);
    await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));

    // Danh sách thật: 2 Docs + 1 Sheets từ backend.
    expect(await screen.findByText('Kế hoạch tuần (ngắn)')).toBeTruthy();
    expect(screen.getByText('Biên bản họp (dài, sẽ bị cắt)')).toBeTruthy();
    expect(screen.getByText('Backlog nhóm')).toBeTruthy();

    await user.click(screen.getAllByRole('button', { name: 'Chọn' })[0]);

    expect(await screen.findByText('[E2E] Hoàn thành báo cáo tuần trước thứ Sáu')).toBeTruthy();
    expect(screen.queryByText(/tài liệu quá dài/i)).toBeNull();
    // quotaRemaining=1 vì test env hạ GOOGLE_DOCUMENT_READS_PER_DAY=2 để demo
    // nhanh — banner còn-lượt vẫn hiện đúng theo số backend trả về thật.
    expect(screen.getByText('Còn 1 lượt đọc Docs/Sheets hôm nay.')).toBeTruthy();
  });

  it('trạng thái truncated=true: đúng cờ + câu cảnh báo backend thật trả về', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/google-drive/files')) return Promise.resolve(jsonResponse(REAL_DRIVE_FILES_LIST));
      if (String(url).includes('/google-docs/task-proposals')) return Promise.resolve(jsonResponse(REAL_TRUNCATED_SCAN));
      throw new Error(`unmocked fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<GoogleDriveFilePicker accessToken="token" />);
    await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));
    await screen.findByText('Biên bản họp (dài, sẽ bị cắt)');
    await user.click(screen.getAllByRole('button', { name: 'Chọn' })[1]);

    expect(await screen.findByText(/tài liệu quá dài/i)).toBeTruthy();
    expect(screen.getByText('Còn 0 lượt đọc Docs/Sheets hôm nay.')).toBeTruthy();
  });

  it('429 hết quota đọc trong ngày: hiện nguyên văn detail thật (giờ reset) và khoá thao tác đọc tiếp', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/google-drive/files')) return Promise.resolve(jsonResponse(REAL_DRIVE_FILES_LIST));
      if (String(url).includes('/google-docs/task-proposals')) return Promise.resolve(jsonResponse(REAL_QUOTA_429_BODY, 429));
      throw new Error(`unmocked fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<GoogleDriveFilePicker accessToken="token" />);
    await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));
    await screen.findByText('Kế hoạch tuần (ngắn)');
    await user.click(screen.getAllByRole('button', { name: 'Chọn' })[0]);

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain(
      'Bạn đã dùng hết 2 lượt đọc Google Docs/Sheets trong hôm nay. Hạn mức được cấp lại lúc 00:00 ngày 2026-08-20',
    );
    expect(screen.getByText('Đã hết lượt đọc Google Docs/Sheets hôm nay.')).toBeTruthy();
    for (const button of screen.getAllByRole('button', { name: 'Chọn' })) {
      expect(button).toHaveProperty('disabled', true);
    }
  });

  it('429 rate-limit khi duyệt Drive (shape {"error"} của slowapi, KHÁC shape quota) vẫn hiện đúng nội dung — không rơi về statusText chung chung', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/google-drive/files')) return Promise.resolve(jsonResponse(REAL_RATE_LIMIT_429_BODY, 429));
      throw new Error(`unmocked fetch: ${url}`);
    });

    const user = userEvent.setup();
    render(<GoogleDriveFilePicker accessToken="token" />);
    await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Rate limit exceeded: 30 per 1 minute');
    expect(screen.getByText('Đang duyệt Drive quá nhanh — chờ một chút rồi thử lại.')).toBeTruthy();
  });
});
