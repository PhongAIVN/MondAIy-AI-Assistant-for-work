// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ProductivityApprovalCard } from '../src/components/briefing/ProductivityApprovalCard';
import type { ProductivityAction } from '../src/types/conversation';

const proposal: ProductivityAction = {
  status: 'pending_approval',
  kind: 'calendar_event',
  approval_id: 'approval-1',
  message: 'Chờ duyệt',
  draft: {
    title: 'Workshop',
    starts_at: '2026-08-11T20:00:00+07:00',
    ends_at: '2026-08-11T22:00:00+07:00',
    calendar_id: 'primary',
  },
};

describe('ProductivityApprovalCard', () => {
  afterEach(cleanup);

  it('shows a review preview and explicit approve/reject controls', async () => {
    const user = userEvent.setup();
    const approve = vi.fn();
    const reject = vi.fn();
    render(
      <ProductivityApprovalCard
        action={proposal}
        language="vi"
        onApprove={approve}
        onReject={reject}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Workshop' })).toBeTruthy();
    expect(screen.getByText('Chờ bạn duyệt')).toBeTruthy();
    expect(screen.getByText('Bắt đầu')).toBeTruthy();
    expect(screen.getByText('Kết thúc')).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Chấp nhận' }));
    await user.click(screen.getByRole('button', { name: 'Từ chối' }));
    expect(approve).toHaveBeenCalledOnce();
    expect(reject).toHaveBeenCalledOnce();
  });

  it('replaces controls with completed state and Calendar link', () => {
    render(
      <ProductivityApprovalCard
        action={{
          ...proposal,
          status: 'created',
          result: { calendar_url: 'https://calendar.google.com/calendar/event?eid=abc' },
        }}
        language="vi"
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText('Đã thực hiện')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Chấp nhận' })).toBeNull();
    expect(screen.getByRole('link', { name: /Mở trong Google Calendar/ }).getAttribute('href'))
      .toBe('https://calendar.google.com/calendar/event?eid=abc');
  });

  it('renders missing details as an editable draft and submits explicit follow-up details', async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    render(
      <ProductivityApprovalCard
        action={{
          status: 'needs_clarification',
          kind: 'calendar_event',
          message: 'Mình cần thời gian bắt đầu và thời lượng.',
          missing_fields: ['starts_at', 'end_or_duration'],
          draft: { title: 'Planning' },
        }}
        language="vi"
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onSubmitClarification={submit}
      />,
    );

    expect(screen.getByRole('heading', { name: /Mình đã hiểu yêu cầu/ })).toBeTruthy();
    await user.type(screen.getByLabelText(/Bắt đầu/), '2026-08-13T09:00');
    await user.type(screen.getByLabelText(/thời lượng/), '60');
    await user.click(screen.getByRole('button', { name: 'Gửi thông tin' }));

    expect(submit).toHaveBeenCalledOnce();
    expect(submit.mock.calls[0][0]).toContain('tiêu đề: Planning');
    expect(submit.mock.calls[0][0]).toContain('thời lượng: 60 phút');
  });

  it('shows an attendees row in the preview when the draft has invitees', () => {
    render(
      <ProductivityApprovalCard
        action={{ ...proposal, draft: { ...proposal.draft, attendees: ['lan@gmail.com', 'minh@gmail.com'] } }}
        language="vi"
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByText('Người tham dự')).toBeTruthy();
    expect(screen.getByText('lan@gmail.com, minh@gmail.com')).toBeTruthy();
  });

  it('does not render an attendees row when the draft has none', () => {
    render(<ProductivityApprovalCard action={proposal} language="vi" onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.queryByText('Người tham dự')).toBeNull();
  });

  it('lets the user add attendees in the clarification form and includes them in the follow-up message', async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    render(
      <ProductivityApprovalCard
        action={{
          status: 'needs_clarification',
          kind: 'calendar_event',
          message: 'Mình cần thời gian bắt đầu và thời lượng.',
          missing_fields: ['starts_at', 'end_or_duration'],
          draft: { title: 'Planning' },
        }}
        language="vi"
        onApprove={vi.fn()}
        onReject={vi.fn()}
        onSubmitClarification={submit}
      />,
    );

    await user.type(screen.getByLabelText(/Bắt đầu/), '2026-08-13T09:00');
    await user.type(screen.getByLabelText(/thời lượng/), '60');
    await user.type(screen.getByLabelText(/Người tham dự/), 'lan@gmail.com, minh@gmail.com');
    await user.click(screen.getByRole('button', { name: 'Gửi thông tin' }));

    expect(submit).toHaveBeenCalledOnce();
    expect(submit.mock.calls[0][0]).toContain('người tham dự: lan@gmail.com, minh@gmail.com');
  });

  it('translates the task deadline label instead of leaving it hardcoded in English', () => {
    const taskAction: ProductivityAction = {
      status: 'pending_approval',
      kind: 'task',
      approval_id: 'approval-2',
      message: 'Chờ duyệt',
      draft: { title: 'Nộp báo cáo', deadline: '2026-08-20T09:00:00+07:00' },
    };

    const { rerender } = render(
      <ProductivityApprovalCard action={taskAction} language="vi" onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.getByText('Hạn chót')).toBeTruthy();
    expect(screen.queryByText('Deadline')).toBeNull();

    rerender(
      <ProductivityApprovalCard action={taskAction} language="en" onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.getByText('Deadline')).toBeTruthy();
    expect(screen.queryByText('Hạn chót')).toBeNull();
  });

  it('translates the deadline field label in the clarification form for a non-calendar action', () => {
    const clarification: ProductivityAction = {
      status: 'needs_clarification',
      kind: 'task',
      message: 'Cần hạn chót.',
      missing_fields: ['deadline'],
      draft: { title: 'Ôn tập' },
    };

    render(
      <ProductivityApprovalCard action={clarification} language="en" onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(screen.getByLabelText(/Deadline/)).toBeTruthy();
  });
});
