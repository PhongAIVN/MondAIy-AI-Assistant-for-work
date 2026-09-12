// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ExcelTaskImporter } from '../src/components/sources/ExcelTaskImporter';

const mocks = vi.hoisted(() => ({ upload: vi.fn(), create: vi.fn() }));

vi.mock('../src/lib/excelTasksApi', () => ({ uploadExcelTaskFile: mocks.upload }));
vi.mock('../src/lib/tasksApi', () => ({ createTaskFromSuggestion: mocks.create }));

describe('ExcelTaskImporter', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('uploads a DOCX, shows the agent analysis and creates only after confirmation', async () => {
    mocks.upload.mockResolvedValue({
      fileNames: ['cong-viec.xlsx'], timezone: 'Asia/Ho_Chi_Minh', agentResponse: 'Ưu tiên việc có hạn.', agentAnalysis: '', agentWarning: null,
      searchedName: '', needsNameQuery: false, suggestedNames: [],
      proposals: [{
        rowNumber: 3, externalKey: 'Tuần 31-row-3', title: 'Chốt kế hoạch', detail: 'Liên hệ chính (A): Kế hoạch (A)',
        assignee: 'Đức', dueAt: null, allDay: false, status: null, matchedUser: false, matchKind: 'possible',
        needsConfirmation: true, clarificationQuestion: 'Bạn xác nhận đây là việc của mình nhé.', source: 'Excel · cong-viec.xlsx · Tuần 31', sourceUrl: '',
      }],
    });
    mocks.create.mockResolvedValue({ id: 1 });
    const user = userEvent.setup();
    render(<ExcelTaskImporter accessToken="token" />);

    await user.upload(screen.getByLabelText('Tệp công việc'), new File(['table'], 'cong-viec.docx', { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }));
    await user.click(screen.getByRole('button', { name: 'Phân tích tệp' }));

    expect(await screen.findByText('Ưu tiên việc có hạn.')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Xác nhận & thêm task' }));
    expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ title: 'Chốt kế hoạch' }), 'token');
  });

  it('keeps selected files in memory and filters immediately after selecting a suggested name', async () => {
    mocks.upload.mockResolvedValue({
      fileNames: ['cong-viec.docx'], timezone: 'Asia/Ho_Chi_Minh', agentResponse: 'Bạn muốn tìm theo tên nào?', agentAnalysis: '', agentWarning: null,
      searchedName: '', needsNameQuery: true, suggestedNames: ['Nguyễn Hồng Đức'], proposals: [],
    });
    const user = userEvent.setup();
    render(<ExcelTaskImporter accessToken="token" />);
    await user.upload(screen.getByLabelText('Tệp công việc'), new File(['table'], 'cong-viec.docx'));
    await user.click(screen.getByRole('button', { name: 'Phân tích tệp' }));
    await user.click(await screen.findByRole('button', { name: 'Nguyễn Hồng Đức' }));

    expect(mocks.upload).toHaveBeenLastCalledWith(expect.any(Array), 'token', 'Nguyễn Hồng Đức');
  });

  it('rejects a file larger than 200 KB before uploading', async () => {
    const user = userEvent.setup();
    render(<ExcelTaskImporter accessToken="token" />);
    await user.upload(screen.getByLabelText('Tệp công việc'), new File([new Uint8Array(200 * 1024 + 1)], 'large.docx'));

    expect((await screen.findByRole('alert')).textContent).toContain('vượt quá giới hạn 200 KB');
    expect(mocks.upload).not.toHaveBeenCalled();
  });
});
