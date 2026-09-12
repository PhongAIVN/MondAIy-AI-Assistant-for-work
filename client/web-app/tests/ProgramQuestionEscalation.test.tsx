import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProgramQuestionEscalation } from '../src/components/briefing/ProgramQuestionEscalation';

describe('ProgramQuestionEscalation', () => {
  beforeEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('shares only the edited question after explicit consent', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        id: 7,
        status: 'open',
        sharedQuestion: 'Lịch gate mới là khi nào?',
        createdAt: '2026-08-16T00:00:00Z',
        resolvedItemId: null,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    render(
      <ProgramQuestionEscalation
        accessToken="token"
        initialQuestion="Lịch gate cũ?"
        language="vi"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Nhờ đội ngũ chương trình trả lời' }));
    fireEvent.change(screen.getByLabelText('Câu hỏi chia sẻ với đội ngũ'), {
      target: { value: 'Lịch gate mới là khi nào?' },
    });
    const submit = screen.getByRole('button', { name: 'Xác nhận gửi' });
    expect((submit as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(submit);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [, options] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(options?.body))).toEqual({
      sharedQuestion: 'Lịch gate mới là khi nào?',
      consentToShare: true,
    });
    expect(screen.getByRole('status').textContent).toContain('Đã chuyển câu hỏi');
  });

  it('keeps the edited question when the request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Tạm thời chưa gửi được.' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    render(
      <ProgramQuestionEscalation accessToken="token" initialQuestion="Câu hỏi cần giữ" language="vi" />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Nhờ đội ngũ chương trình trả lời' }));
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gửi' }));

    expect((await screen.findByRole('alert')).textContent).toContain('Tạm thời chưa gửi được.');
    expect(screen.getByDisplayValue('Câu hỏi cần giữ')).not.toBeNull();
  });
});
