// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { AgentActivity } from '../src/components/briefing/AgentActivity';

describe('AgentActivity', () => {
  afterEach(cleanup);

  it('moves from thinking through a named tool call to response generation', () => {
    const { rerender } = render(<AgentActivity events={[{ phase: 'thinking' }]} language="vi" />);

    expect(screen.getByRole('status').getAttribute('aria-label')).toBe(
      'Tiến trình xử lý của mondaiy',
    );
    expect(screen.getByText('Đang suy nghĩ')).toBeTruthy();

    rerender(
      <AgentActivity
        language="vi"
        events={[
          { phase: 'thinking' },
          { phase: 'calling', tool: 'discord_search_my_messages' },
          { phase: 'observing', tool: 'discord_search_my_messages' },
          { phase: 'responding' },
        ]}
      />,
    );

    // Contract hiện tại: wording chung theo phase, không theo tên tool.
    // Contract hiện tại: component chỉ hiển thị event MỚI NHẤT (không liệt kê
    // toàn bộ timeline), event cuối của lượt là responding.
    expect(screen.getByText('Đang soạn câu trả lời')).toBeTruthy();
  });
});
