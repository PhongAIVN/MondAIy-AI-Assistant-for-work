// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminDiscordAnnouncementPage } from '../src/pages/admin/AdminDiscordAnnouncementPage';

const mocks = vi.hoisted(() => ({ preview: vi.fn(), publish: vi.fn() }));

vi.mock('../src/stores/useAuthStore', () => ({
  useAuthStore: (selector: (state: { accessToken: string }) => unknown) =>
    selector({ accessToken: 'admin-token' }),
}));

vi.mock('../src/lib/adminApi', async () => {
  const actual = await vi.importActual<typeof import('../src/lib/adminApi')>('../src/lib/adminApi');
  return {
    ...actual,
    previewDiscordAnnouncement: mocks.preview,
    publishDiscordAnnouncement: mocks.publish,
  };
});

const candidate = {
  id: 17,
  status: 'draft',
  rawText: '📢 THÔNG BÁO\nNộp bài cuối kỳ 30/08/2026 23:59',
  evidence: { sourceLevel: 'A' as const, channel: '#announcements' },
  preview: {
    title: 'Hạn nộp bài cuối kỳ',
    body: 'Nộp bài cuối kỳ 30/08/2026 23:59',
    category: 'submission' as const,
    aliases: ['deadline cuối kỳ'],
    items: [{ kind: 'task', title: 'Nộp bài', dueAt: '2026-08-30T23:59:00+07:00', ambiguous: false }],
    timezone: 'Asia/Ho_Chi_Minh',
    extractionMethod: 'llm' as const,
    fallbackReason: null,
  },
  informationItemId: null,
};

beforeEach(() => {
  mocks.preview.mockReset();
  mocks.publish.mockReset();
  mocks.preview.mockResolvedValue(candidate);
  mocks.publish.mockResolvedValue({ ...candidate, status: 'published', informationItemId: 99 });
});

afterEach(cleanup);

describe('AdminDiscordAnnouncementPage', () => {
  it('keeps the LLM result as a draft and publishes admin-reviewed category and aliases', async () => {
    const user = userEvent.setup();
    render(<AdminDiscordAnnouncementPage />);

    await user.type(screen.getByLabelText('Discord announcement'), candidate.rawText);
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    expect(await screen.findByText('LLM')).toBeTruthy();
    // Tiêu đề giờ là ô nhập để admin sửa trước khi đăng, không còn là text thuần.
    expect((screen.getByLabelText('Tiêu đề sẽ publish') as HTMLInputElement).value)
      .toBe(candidate.preview.title);
    expect(screen.getByText(candidate.preview.body)).toBeTruthy();
    expect(mocks.publish).not.toHaveBeenCalled();
    await user.selectOptions(screen.getByLabelText('Category đề xuất'), 'policy');
    const aliases = screen.getByLabelText('Aliases đề xuất');
    await user.clear(aliases);
    await user.type(aliases, 'quy định cuối kỳ\nhạn chót cuối kỳ');
    await user.click(screen.getByRole('button', { name: 'Xác nhận và phát hành' }));

    // Hợp đồng publish giờ mang cả `title` và `items` vì admin sửa được chúng
    // trước khi đăng — không chỉ category/aliases như bản trước.
    expect(mocks.publish).toHaveBeenCalledWith('admin-token', 17, {
      title: candidate.preview.title,
      category: 'policy',
      aliases: ['quy định cuối kỳ', 'hạn chót cuối kỳ'],
      items: [{
        title: 'Nộp bài',
        kind: 'task',
        dueAt: '2026-08-30T23:59:00+07:00',
        allDay: undefined,
      }],
    });
  });

  it('shows an observable fallback state', async () => {
    mocks.preview.mockResolvedValue({
      ...candidate,
      preview: { ...candidate.preview, extractionMethod: 'regex_fallback', fallbackReason: 'RuntimeError' },
    });
    const user = userEvent.setup();
    render(<AdminDiscordAnnouncementPage />);

    await user.type(screen.getByLabelText('Discord announcement'), 'Thông báo');
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    expect(await screen.findByText('Regex fallback (RuntimeError)')).toBeTruthy();
  });

  it('binds an all-day ISO date to datetime-local at midnight', async () => {
    mocks.preview.mockResolvedValue({
      ...candidate,
      preview: { ...candidate.preview, items: [{ ...candidate.preview.items[0], dueAt: '2026-08-30' }] },
    });
    const user = userEvent.setup();
    render(<AdminDiscordAnnouncementPage />);

    await user.type(screen.getByLabelText('Discord announcement'), 'Thông báo');
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    expect((await screen.findByLabelText('Action 1 due date') as HTMLInputElement).value)
      .toBe('2026-08-30T00:00');
  });

  it('sends the selected reference date and never publishes during preview', async () => {
    const user = userEvent.setup();
    render(<AdminDiscordAnnouncementPage />);
    fireEvent.change(screen.getByLabelText('Reference date'), {
      target: { value: '2026-08-24T15:27' },
    });
    await user.type(screen.getByLabelText('Discord announcement'), 'OH 13');
    await user.click(screen.getByRole('button', { name: 'Xem trước' }));

    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith(
      'admin-token',
      { rawText: 'OH 13', referenceDate: '2026-08-24T15:27:00+07:00' },
    ));
    expect(mocks.publish).not.toHaveBeenCalled();
  });
});
