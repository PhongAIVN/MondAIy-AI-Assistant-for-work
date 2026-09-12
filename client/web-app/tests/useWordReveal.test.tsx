import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { useWordReveal } from '../src/hooks/useWordReveal';

const { motionEnabled } = vi.hoisted(() => ({ motionEnabled: { value: true } }));

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => motionEnabled.value,
}));

function Harness({ text }: { text: string }) {
  const { containerRef, words } = useWordReveal<HTMLHeadingElement>(text);
  return (
    <h1 ref={containerRef} data-testid="title">
      {words.map((word, i) => (
        <span key={i} data-word>
          {word}
          {i < words.length - 1 ? ' ' : ''}
        </span>
      ))}
    </h1>
  );
}

describe('useWordReveal', () => {
  afterEach(() => {
    cleanup();
    motionEnabled.value = true;
  });

  it('splits text into word spans that reconstruct the original string, motion enabled', () => {
    expect(() => render(<Harness text="mondaiy tổng hợp nguồn thật" />)).not.toThrow();
    expect(screen.getByTestId('title').textContent).toBe('mondaiy tổng hợp nguồn thật');
  });

  it('renders the full text without animating when motion is disabled', () => {
    motionEnabled.value = false;
    expect(() => render(<Harness text="mondaiy tổng hợp nguồn thật" />)).not.toThrow();
    expect(screen.getByTestId('title').textContent).toBe('mondaiy tổng hợp nguồn thật');
  });
});
