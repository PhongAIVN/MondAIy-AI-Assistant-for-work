// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GoogleDriveFilePicker } from '../src/components/sources/GoogleDriveFilePicker';
import { ApiError } from '../src/lib/apiClient';

const mocks = vi.hoisted(() => ({
  listFiles: vi.fn(),
  scanDoc: vi.fn(),
  scanSheetById: vi.fn(),
  createTask: vi.fn(),
}));

vi.mock('../src/lib/googleDriveApi', () => ({ listGoogleDriveFiles: mocks.listFiles }));
vi.mock('../src/lib/googleDocsApi', () => ({ scanGoogleDocTasks: mocks.scanDoc }));
vi.mock('../src/lib/googleSheetsApi', () => ({ scanGoogleSheetTasksById: mocks.scanSheetById }));
vi.mock('../src/lib/tasksApi', () => ({ createTaskFromSuggestion: mocks.createTask }));

const docFile = {
  id: 'doc-1',
  name: 'Kế hoạch Q3',
  kind: 'document' as const,
  modifiedTime: '2026-08-01T00:00:00Z',
  webViewLink: 'https://docs.google.com/document/d/doc-1',
};

const openPickerAndListDoc = async () => {
  mocks.listFiles.mockResolvedValue({ files: [docFile], nextPageToken: null });
  const user = userEvent.setup();
  render(<GoogleDriveFilePicker accessToken="token" />);
  await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));
  expect(await screen.findByText('Kế hoạch Q3')).toBeTruthy();
  return user;
};

describe('GoogleDriveFilePicker', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('chọn file Docs từ Drive gọi task-proposals bằng documentId và hiện đề xuất', async () => {
    const user = await openPickerAndListDoc();
    mocks.scanDoc.mockResolvedValue({
      documentId: 'doc-1',
      timezone: 'Asia/Ho_Chi_Minh',
      proposals: [
        {
          paragraphIndex: 2,
          title: 'Viết báo cáo tuần',
          detail: 'Tổng hợp số liệu',
          assignee: null,
          dueAt: null,
          allDay: false,
          matchedUser: false,
          needsConfirmation: false,
          clarificationQuestion: null,
          source: 'Google Docs · Kế hoạch Q3',
          sourceUrl: 'https://docs.google.com/document/d/doc-1',
        },
      ],
      truncated: false,
      quotaRemaining: 15,
    });
    mocks.createTask.mockResolvedValue({ id: 1 });

    await user.click(screen.getByRole('button', { name: 'Chọn' }));

    expect(await screen.findByText('Viết báo cáo tuần')).toBeTruthy();
    expect(mocks.scanDoc).toHaveBeenCalledWith({ documentId: 'doc-1' }, 'token');
    // Không có quotaRemaining thấp -> không hiện banner còn lượt.
    expect(screen.queryByText(/Còn \d+ lượt đọc/)).toBeNull();

    await user.click(screen.getByRole('button', { name: 'Thêm task' }));
    expect(mocks.createTask).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Viết báo cáo tuần' }),
      'token',
    );
    expect(await screen.findByText('Đã thêm vào task đề xuất')).toBeTruthy();
  });

  it('báo rõ khi tài liệu bị cắt (truncated) và khi quota còn thấp', async () => {
    const user = await openPickerAndListDoc();
    mocks.scanDoc.mockResolvedValue({
      documentId: 'doc-1',
      timezone: 'Asia/Ho_Chi_Minh',
      proposals: [],
      truncated: true,
      quotaRemaining: 3,
    });

    await user.click(screen.getByRole('button', { name: 'Chọn' }));

    expect(await screen.findByText(/tài liệu quá dài/i)).toBeTruthy();
    expect(screen.getByText('Còn 3 lượt đọc Docs/Sheets hôm nay.')).toBeTruthy();
  });

  it('hết quota (429) hiện thông báo còn bao lâu nữa reset và khoá thao tác đọc tiếp', async () => {
    const user = await openPickerAndListDoc();
    mocks.scanDoc.mockRejectedValue(new ApiError(429, 'Bạn đã dùng hết 20 lượt đọc Google Docs/Sheets hôm nay. Quay lại sau 0:00 (giờ Việt Nam).'));

    await user.click(screen.getByRole('button', { name: 'Chọn' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Quay lại sau 0:00');
    expect(screen.getByRole('button', { name: 'Chọn' })).toHaveProperty('disabled', true);
    // Không tự động gọi lại API khi đã khoá quota.
    expect(mocks.scanDoc).toHaveBeenCalledTimes(1);
  });

  it('chưa cấp quyền Drive (409) hiện rõ lý do thay vì danh sách trống im lặng', async () => {
    mocks.listFiles.mockRejectedValue(new ApiError(409, 'Kết nối Google chưa có quyền đọc Drive; hãy cấp lại quyền Google.'));
    const user = userEvent.setup();
    render(<GoogleDriveFilePicker accessToken="token" />);
    await user.click(screen.getByRole('button', { name: 'Duyệt file trong Drive' }));

    expect(await screen.findByText('Kết nối Google chưa có quyền đọc Drive; hãy cấp lại quyền Google.')).toBeTruthy();
  });
});
