// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ProductRatingModal } from '../src/components/ui/ProductRatingModal';

describe('ProductRatingModal', () => {
  afterEach(cleanup);

  it('keeps the modal open and explains when submission fails', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(
      new Error('ê chúng tôi đọc được buồn đó nha, đánh giá thật công tâm vào'),
    );
    render(
      <ProductRatingModal
        isOpen
        actionCount={5}
        onSubmit={onSubmit}
        onDismiss={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('radio', { name: '5 sao' }));
    await user.type(
      screen.getByPlaceholderText('Cho chúng tôi biết điều gì hữu ích hoặc khó hiểu…'),
      'Ứng dụng tốt tốt tốt tốt tốt tốt tốt tốt tốt tốt tốt tốt.',
    );
    await user.click(screen.getByRole('button', { name: 'Gửi phản hồi' }));

    expect((await screen.findByRole('alert')).textContent).toBe(
      'ê chúng tôi đọc được buồn đó nha, đánh giá thật công tâm vào',
    );
    expect(screen.getByText('Đánh giá để tiếp tục trải nghiệm')).toBeTruthy();
  });

  it('allows dismissal without requiring feedback and does not submit', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    const onSubmit = vi.fn();
    render(
      <ProductRatingModal
        isOpen
        actionCount={0}
        onSubmit={onSubmit}
        onDismiss={onDismiss}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Đóng' }));

    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('allows a short filled feedback note without the old 41-character gate', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <ProductRatingModal
        isOpen
        actionCount={3}
        onSubmit={onSubmit}
        onDismiss={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('radio', { name: '5 sao' }));
    await user.type(screen.getByRole('textbox'), 'Ổn');
    await user.click(screen.getByRole('button', { name: 'Gửi phản hồi' }));

    expect(onSubmit).toHaveBeenCalledWith(5, 'Ổn');
  });

  it('uses proactive feedback copy when opened from the account menu', () => {
    render(
      <ProductRatingModal
        isOpen
        isManual
        actionCount={0}
        onSubmit={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Gửi phản hồi' })).toBeTruthy();
    expect(
      screen.getByText('Chia sẻ điều hữu ích, khó hiểu hoặc bạn muốn mondaiy cải thiện.'),
    ).toBeTruthy();
    expect(screen.queryByText('Đánh giá để tiếp tục trải nghiệm')).toBeNull();
  });
});
