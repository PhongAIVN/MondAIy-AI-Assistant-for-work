// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import React from 'react';

import { MarkdownBody } from '../src/components/marketing/MarkdownBody';

// vitest.config.ts không bật `globals: true`, nên RTL không tự nhận ra
// afterEach toàn cục để tự dọn DOM — không cleanup thì render() của test này
// còn lẫn trong DOM của test kế tiếp trong cùng file.
afterEach(cleanup);

describe('MarkdownBody', () => {
  it('renders assistant-style markdown lists and inline emphasis as semantic content', () => {
    render(
      <MarkdownBody
        source={'**Việc cần làm**\n\n- Xem [Canvas](https://canvas.example)\n- Hoàn thành *bài tập*'}
      />,
    );

    expect(screen.getByText('Việc cần làm').tagName).toBe('STRONG');
    expect(screen.getByRole('list')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Canvas' }).getAttribute('href')).toBe(
      'https://canvas.example',
    );
    expect(screen.getByText('bài tập').tagName).toBe('EM');
  });

  it('renders a numbered task list as separate items, not one merged paragraph', () => {
    // Regression: câu trả lời agenda/task đánh số "1. ... 2. ..." từng bị nối
    // lại thành một khối văn xuôi vì markdownToBlocks không có nhánh ordered
    // list, dòng đầu tiên trôi thẳng vào đoạn văn mặc định.
    render(
      <MarkdownBody
        source={
          '1. [CP2] Việc một - Hạn 12/08/2026. [Link chi tiết](https://a.test)\n' +
          '2. [Sprint 2] Việc hai - Hạn 15/08/2026. [Link chi tiết](https://b.test)'
        }
      />,
    );

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain('Việc một');
    expect(items[1].textContent).toContain('Việc hai');
    expect(items[0].textContent).not.toContain('Việc hai');
  });
});
