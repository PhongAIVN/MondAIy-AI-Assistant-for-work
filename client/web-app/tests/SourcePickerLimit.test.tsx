// @vitest-environment jsdom
//
// Trần nguồn mỗi lần Sync phải nhìn thấy được TRƯỚC khi bấm. Trước đây FE cho
// tick thoải mái rồi backend mới trả 422, người dùng không biết bỏ bớt cái nào.

import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SourcePicker } from '../src/components/pipeline/SourcePicker';
import type { Integration, SyncSourceRef } from '../src/types/pipeline';

const integration: Integration = {
  id: 1,
  provider: 'google',
  accountLabel: 'me@example.test',
  expiresAt: null,
} as Integration;

const sources = {
  1: {
    loading: false,
    items: [
      { id: 'INBOX', name: 'Inbox', itemCount: null },
      { id: 'calendar:primary', name: 'Calendar', itemCount: null },
      { id: 'STARRED', name: 'Starred', itemCount: null },
    ],
  },
};

const renderPicker = (selected: SyncSourceRef[], maxSources: number, onToggle = vi.fn()) => {
  render(
    <MemoryRouter>
      <SourcePicker
        integrations={[integration]}
        sources={sources}
        selected={selected}
        loading={false}
        error={null}
        maxSources={maxSources}
        autoSyncEnabled={false}
        autoSyncIntervalMinutes={180}
        onToggle={onToggle}
        onReload={vi.fn()}
      />
    </MemoryRouter>,
  );
  return onToggle;
};

describe('SourcePicker — trần nguồn mỗi lần Sync', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('hiện bộ đếm số nguồn đã chọn trên tổng hạn mức', () => {
    renderPicker([{ connectionId: 1, sourceId: 'INBOX' }], 10);

    // Store ngôn ngữ mặc định là 'vi' trong môi trường test.
    expect(screen.getByText('1/10 nguồn')).toBeTruthy();
  });

  it('khoá các nguồn chưa tick khi đã chạm hạn mức', async () => {
    const onToggle = renderPicker(
      [
        { connectionId: 1, sourceId: 'INBOX' },
        { connectionId: 1, sourceId: 'calendar:primary' },
      ],
      2,
    );

    const blocked = screen.getByRole('checkbox', { name: /Starred/ });
    expect(blocked.hasAttribute('disabled')).toBe(true);

    await userEvent.click(blocked);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('vẫn cho bỏ tick nguồn đã chọn khi đang chạm hạn mức', async () => {
    // Nếu khoá cả ô đã tick thì danh sách bị kẹt cứng, không đổi được nguồn.
    const onToggle = renderPicker(
      [
        { connectionId: 1, sourceId: 'INBOX' },
        { connectionId: 1, sourceId: 'calendar:primary' },
      ],
      2,
    );

    await userEvent.click(screen.getByRole('checkbox', { name: /Inbox/ }));

    expect(onToggle).toHaveBeenCalledWith({ connectionId: 1, sourceId: 'INBOX' });
  });

  it('không hiện băng auto-sync khi tính năng đang tắt', () => {
    renderPicker([], 10);

    expect(screen.queryByText(/Tự động đồng bộ đang bật/)).toBeNull();
  });

  it('nói rõ nhịp làm mới khi auto-sync đang bật', () => {
    render(
      <MemoryRouter>
        <SourcePicker
          integrations={[integration]}
          sources={sources}
          selected={[]}
          loading={false}
          error={null}
          maxSources={10}
          autoSyncEnabled
          autoSyncIntervalMinutes={180}
          onToggle={vi.fn()}
          onReload={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/khoảng 3 giờ một lần/)).toBeTruthy();
  });
});
