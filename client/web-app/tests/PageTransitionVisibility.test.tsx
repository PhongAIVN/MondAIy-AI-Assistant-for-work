import React, { forwardRef } from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PageTransition } from '../src/components/layout/PageTransition';

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => true,
}));

vi.mock('motion/react', () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  motion: {
    div: forwardRef<
      HTMLDivElement,
      React.HTMLAttributes<HTMLDivElement> & { initial?: false | { opacity?: number } }
    >(({ initial, style, ...props }, ref) => (
      <div
        ref={ref}
        style={{ ...style, opacity: initial && typeof initial === 'object' ? initial.opacity : undefined }}
        {...props}
      />
    )),
  },
}));

vi.mock('motion', () => ({
  animate: () => ({ stop: () => undefined }),
  stagger: () => 0,
}));

describe('PageTransition visibility', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('never hides the first post-login route while its entrance animation starts', () => {
    render(
      <MemoryRouter initialEntries={['/onboarding']}>
        <Routes>
          <Route element={<PageTransition />}>
            <Route path="/onboarding" element={<div data-testid="onboarding-content">Set up Mondaiy</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('onboarding-content')).toBeTruthy();
    expect(document.querySelector<HTMLElement>('.page-transition-root')?.style.opacity).not.toBe('0');
  });
});
