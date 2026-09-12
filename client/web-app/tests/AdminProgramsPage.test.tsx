// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminProgramsPage } from '../src/pages/admin/AdminProgramsPage';

const mocks = vi.hoisted(() => ({
  listProgramInformation: vi.fn(),
  listProgramInformationRequests: vi.fn(),
  createProgramInformation: vi.fn(),
  updateProgramInformation: vi.fn(),
  actOnProgramInformation: vi.fn(),
  resolveProgramInformationRequest: vi.fn(),
}));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) => selector({ accessToken: 'access-token' }),
}));

vi.mock('../src/lib/adminApi', () => mocks);

const informationItem = (patch: Partial<Record<string, unknown>> = {}) => ({
  id: 31,
  cohortSlug: 'cohort-III',
  category: 'policy',
  title: 'Quy định nộp weekly',
  body: 'Nộp trước 22:00 tối Chủ nhật.',
  aliases: ['weekly nộp khi nào'],
  sourceUrl: 'https://example.test/rules',
  visibility: 'program',
  status: 'published',
  version: 2,
  publishedVersion: 2,
  updatedAt: '2026-08-16T10:00:00Z',
  publishedAt: '2026-08-16T10:00:00Z',
  ...patch,
});

const questionRequest = (patch: Partial<Record<string, unknown>> = {}) => ({
  id: 51,
  sharedQuestion: 'Nếu trễ weekly thì liên hệ ai?',
  status: 'open',
  createdAt: '2026-08-16T11:00:00Z',
  resolvedItemId: null,
  ...patch,
});

const renderPage = () => render(<MemoryRouter><AdminProgramsPage /></MemoryRouter>);

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.listProgramInformation.mockResolvedValue({ items: [informationItem()], total: 1 });
  mocks.listProgramInformationRequests.mockResolvedValue({ items: [questionRequest()], total: 1 });
  mocks.createProgramInformation.mockResolvedValue(informationItem({ id: 32, status: 'draft' }));
  mocks.updateProgramInformation.mockResolvedValue(informationItem());
  mocks.actOnProgramInformation.mockResolvedValue(informationItem());
  mocks.resolveProgramInformationRequest.mockResolvedValue(questionRequest({ status: 'resolved', resolvedItemId: 31 }));
});

afterEach(cleanup);

describe('AdminProgramsPage', () => {
  it('shows only real verified information and no former fake program cards', async () => {
    renderPage();
    expect(await screen.findByText('Quy định nộp weekly')).toBeTruthy();
    expect(screen.queryByText('AI Product Development Program')).toBeNull();
    expect(screen.queryByText('42')).toBeNull();
    expect(mocks.listProgramInformation).toHaveBeenCalledWith('access-token', { limit: 200 });
    expect(mocks.listProgramInformationRequests).toHaveBeenCalledWith('access-token', { status: 'open', limit: 200 });
  });

  it('creates an unpublished information draft from the simple editor', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Quy định nộp weekly');
    await user.click(screen.getByRole('button', { name: 'Thêm thông tin' }));
    await user.type(screen.getByLabelText('Tiêu đề hoặc câu hỏi'), 'Đầu mối hỗ trợ');
    await user.type(screen.getByLabelText('Câu trả lời chính thức'), 'Liên hệ mentor phụ trách nhóm.');
    await user.click(screen.getByRole('button', { name: 'Tạo bản nháp' }));

    await waitFor(() => expect(mocks.createProgramInformation).toHaveBeenCalledWith(
      'access-token',
      expect.objectContaining({
        title: 'Đầu mối hỗ trợ',
        body: 'Liên hệ mentor phụ trách nhóm.',
        visibility: 'program',
      }),
    ));
    expect(mocks.actOnProgramInformation).not.toHaveBeenCalled();
  });

  it('preserves a drafted answer when the server rejects saving', async () => {
    mocks.createProgramInformation.mockRejectedValue(new Error('Có người vừa cập nhật dữ liệu.'));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Quy định nộp weekly');
    await user.click(screen.getByRole('button', { name: 'Thêm thông tin' }));
    await user.type(screen.getByLabelText('Tiêu đề hoặc câu hỏi'), 'Câu hỏi đang soạn');
    await user.type(screen.getByLabelText('Câu trả lời chính thức'), 'Nội dung không được mất');
    await user.click(screen.getByRole('button', { name: 'Tạo bản nháp' }));

    expect(await screen.findByText('Có người vừa cập nhật dữ liệu.')).toBeTruthy();
    expect(screen.getByRole('dialog', { name: 'Thêm thông tin chương trình' })).toBeTruthy();
    expect((screen.getByLabelText('Câu trả lời chính thức') as HTMLTextAreaElement).value).toBe('Nội dung không được mất');
  });

  it('prefills a new official answer from a question AI could not answer', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Quy định nộp weekly');
    await user.click(screen.getByRole('button', { name: /Câu hỏi chờ trả lời/ }));
    expect(await screen.findByText('Nếu trễ weekly thì liên hệ ai?')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Soạn câu trả lời mới' }));

    expect((screen.getByLabelText('Tiêu đề hoặc câu hỏi') as HTMLInputElement).value).toBe('Nếu trễ weekly thì liên hệ ai?');
  });

  it('resolves a queued question only against a published verified item', async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('Quy định nộp weekly');
    await user.click(screen.getByRole('button', { name: /Câu hỏi chờ trả lời/ }));
    await user.selectOptions(screen.getByLabelText('Thông tin trả lời cho: Nếu trễ weekly thì liên hệ ai?'), '31');
    await user.click(screen.getByRole('button', { name: 'Đánh dấu đã trả lời' }));

    await waitFor(() => expect(mocks.resolveProgramInformationRequest).toHaveBeenCalledWith('access-token', 51, 31, 2));
  });

  it('marks an edited published item as pending and keeps the publish action available', async () => {
    mocks.listProgramInformation.mockResolvedValue({
      items: [informationItem({ version: 3, publishedVersion: 2, status: 'published', title: 'Bản sửa mới' })],
      total: 1,
    });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('Bản mới chưa phát hành')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Phát hành' }));

    await waitFor(() => expect(mocks.actOnProgramInformation).toHaveBeenCalledWith(
      'access-token',
      31,
      'publish',
      3,
    ));
  });
});
