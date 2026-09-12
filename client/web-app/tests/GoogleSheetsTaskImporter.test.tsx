// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { GoogleSheetsTaskImporter } from '../src/components/sources/GoogleSheetsTaskImporter';

const mocks = vi.hoisted(() => ({
  scan: vi.fn(),
  create: vi.fn(),
}));

vi.mock('../src/lib/googleSheetsApi', () => ({ scanGoogleSheetTasks: mocks.scan }));
vi.mock('../src/lib/tasksApi', () => ({ createTaskFromSuggestion: mocks.create }));

describe('GoogleSheetsTaskImporter', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows a confirmation box for an ambiguous assignee and creates a proposed task after confirmation', async () => {
    mocks.scan.mockResolvedValue({
      spreadsheetId: 'sheet-id',
      sheetName: 'Backlog',
      timezone: 'Asia/Ho_Chi_Minh',
      proposals: [{
        rowNumber: 12,
        externalKey: 'T-001',
        title: 'Lập Project Charter',
        detail: 'Chốt phạm vi',
        assignee: 'An',
        dueAt: '2026-08-31T17:00:00Z',
        allDay: true,
        status: 'Chưa làm',
        matchedUser: false,
        needsConfirmation: true,
        clarificationQuestion: 'Đây có phải là việc của bạn không?',
        source: 'Google Sheets · Backlog',
        sourceUrl: 'https://docs.google.com/spreadsheets/d/sheet-id/edit#gid=0&range=12:12',
      }],
    });
    mocks.create.mockResolvedValue({ id: 1 });
    const user = userEvent.setup();

    render(<GoogleSheetsTaskImporter accessToken="token" />);
    await user.type(screen.getByLabelText('URL Google Sheets'), 'https://docs.google.com/spreadsheets/d/sheet-id/edit');
    await user.click(screen.getByRole('button', { name: 'Đọc & nhận diện' }));

    expect(await screen.findByText('Đây có phải là việc của bạn không?')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Xác nhận & thêm task' }));

    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Lập Project Charter', dueAt: '2026-08-31T17:00:00Z', allDay: true }),
      'token',
    );
    expect(await screen.findByText('Đã thêm vào task đề xuất')).toBeTruthy();
  });

  it('prefills a sheet from chat handoff and lets the user correct an invalid URL', async () => {
    const user = userEvent.setup();
    render(
      <GoogleSheetsTaskImporter
        accessToken="token"
        initialSpreadsheetUrl="https://docs.google.com/spreadsheets/d/from-chat/edit"
        initialSheetName="Giai đoạn 2"
      />,
    );

    expect(screen.getByLabelText('URL Google Sheets')).toHaveProperty('value', 'https://docs.google.com/spreadsheets/d/from-chat/edit');
    expect(screen.getByLabelText('Tên sheet')).toHaveProperty('value', 'Giai đoạn 2');
    await user.clear(screen.getByLabelText('URL Google Sheets'));
    await user.type(screen.getByLabelText('URL Google Sheets'), 'not-a-sheet');
    await user.click(screen.getByRole('button', { name: 'Đọc & nhận diện' }));

    expect((await screen.findByRole('alert')).textContent).toContain('URL Google Sheets chưa đúng');
    expect(mocks.scan).not.toHaveBeenCalled();
  });

  it('scans with a blank tab, shows detected tabs, and lets the user rescan another tab', async () => {
    mocks.scan
      .mockResolvedValueOnce({
        spreadsheetId: 'sheet-id',
        sheetName: 'Danh sách việc',
        availableSheetNames: ['Tổng quan', 'Danh sách việc'],
        timezone: 'Asia/Ho_Chi_Minh',
        proposals: [],
        truncated: false,
        quotaRemaining: 10,
      })
      .mockResolvedValueOnce({
        spreadsheetId: 'sheet-id',
        sheetName: 'Tổng quan',
        availableSheetNames: ['Tổng quan', 'Danh sách việc'],
        timezone: 'Asia/Ho_Chi_Minh',
        proposals: [],
        truncated: false,
        quotaRemaining: 9,
      });
    const user = userEvent.setup();

    render(<GoogleSheetsTaskImporter accessToken="token" initialSpreadsheetUrl="https://docs.google.com/spreadsheets/d/sheet-id/edit" />);

    const scanButton = screen.getByRole('button', { name: 'Đọc & nhận diện' });
    expect(scanButton).toHaveProperty('disabled', false);
    await user.click(scanButton);
    expect(mocks.scan).toHaveBeenNthCalledWith(
      1,
      'https://docs.google.com/spreadsheets/d/sheet-id/edit',
      '',
      'token',
    );
    expect(screen.getByLabelText('Tên sheet')).toHaveProperty('value', 'Danh sách việc');

    await user.selectOptions(screen.getByLabelText('Tên sheet'), 'Tổng quan');
    await user.click(scanButton);
    expect(mocks.scan).toHaveBeenNthCalledWith(
      2,
      'https://docs.google.com/spreadsheets/d/sheet-id/edit',
      'Tổng quan',
      'token',
    );
  });
});
