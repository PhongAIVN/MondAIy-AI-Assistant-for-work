import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { useMagnetic } from '../src/hooks/useMagnetic';

const { motionEnabled } = vi.hoisted(() => ({ motionEnabled: { value: true } }));

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => motionEnabled.value,
}));

function Harness() {
  const ref = useMagnetic<HTMLButtonElement>();
  return (
    <button ref={ref} type="button">
      Get Started
    </button>
  );
}

describe('useMagnetic', () => {
  afterEach(() => {
    cleanup();
    motionEnabled.value = true;
  });

  it('does not throw on mousemove/mouseleave while motion is enabled', () => {
    render(<Harness />);
    const button = screen.getByRole('button', { name: 'Get Started' });
    expect(() => {
      button.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 20, clientY: 10 }));
      button.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
    }).not.toThrow();
  });

  it('does not throw when motion is disabled (no tween wired)', () => {
    motionEnabled.value = false;
    render(<Harness />);
    const button = screen.getByRole('button', { name: 'Get Started' });
    expect(() => {
      button.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 20, clientY: 10 }));
    }).not.toThrow();
  });
});
