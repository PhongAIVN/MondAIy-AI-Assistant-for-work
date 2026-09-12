import React, { forwardRef } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MarketingLayout } from '../src/components/layout/MarketingLayout';

vi.mock('motion/react', () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  motion: {
    div: forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { initial?: unknown; animate?: unknown; exit?: unknown }>(
      ({ initial: _initial, animate: _animate, exit: _exit, ...props }, ref) => <div ref={ref} {...props} />,
    ),
  },
  useReducedMotion: () => false,
}));

vi.mock('motion', () => ({
  animate: () => ({ stop: () => undefined }),
  stagger: () => 0,
}));

function renderAt(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/" element={<MarketingLayout />}>
          <Route index element={<div data-testid="landing-content">Landing</div>} />
          <Route path="blog" element={<div data-testid="blog-content">Blog</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('MarketingLayout — cuộn về đầu trang khi đổi route', () => {
  afterEach(cleanup);

  it('gọi scrollTo(0,0) khi điều hướng từ landing sang một trang marketing khác', () => {
    const scrollToSpy = vi.fn();
    window.scrollTo = scrollToSpy as unknown as typeof window.scrollTo;
    renderAt('/');
    expect(screen.getByTestId('landing-content')).toBeTruthy();
    scrollToSpy.mockClear();

    fireEvent.click(screen.getByRole('button', { name: 'Blog' }));

    expect(screen.getByTestId('blog-content')).toBeTruthy();
    expect(scrollToSpy).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }));
  });

  it('hiện nút back-to-top sau khi cuộn xuống, và bấm nút gọi scrollTo về đầu trang', () => {
    const scrollToSpy = vi.fn();
    window.scrollTo = scrollToSpy as unknown as typeof window.scrollTo;
    renderAt('/');

    expect(screen.queryByRole('button', { name: 'Lên đầu trang' })).toBeNull();

    Object.defineProperty(window, 'scrollY', { value: 900, configurable: true });
    fireEvent.scroll(window);

    const backToTop = screen.getByRole('button', { name: 'Lên đầu trang' });
    scrollToSpy.mockClear();
    fireEvent.click(backToTop);
    expect(scrollToSpy).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }));
  });
});
