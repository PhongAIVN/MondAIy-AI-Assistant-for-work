// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { CollapsibleSourceSection } from '../src/pages/SourceLibraryPage';

describe('CollapsibleSourceSection', () => {
  afterEach(cleanup);

  it('starts compact and lets the user expand then collapse the source list', async () => {
    const user = userEvent.setup();
    render(
      <CollapsibleSourceSection
        title="Nhãn Gmail đồng bộ"
        summary="Đã bật 6/18"
        expandLabel="Mở danh sách nguồn"
        collapseLabel="Thu gọn danh sách nguồn"
      >
        <span>Calendar · Study</span>
      </CollapsibleSourceSection>,
    );

    const expand = screen.getByRole('button', {
      name: 'Nhãn Gmail đồng bộ — Mở danh sách nguồn',
    });
    expect(expand.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByText('Calendar · Study')).toBeNull();

    await user.click(expand);
    expect(screen.getByText('Calendar · Study')).toBeTruthy();
    expect(expand.getAttribute('aria-expanded')).toBe('true');

    await user.click(expand);
    expect(screen.queryByText('Calendar · Study')).toBeNull();
  });
});
