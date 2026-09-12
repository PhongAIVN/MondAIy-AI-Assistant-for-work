import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { MagneticWrap } from '../src/components/ui/MagneticWrap';

const { motionEnabled } = vi.hoisted(() => ({ motionEnabled: { value: true } }));

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => motionEnabled.value,
}));

describe('MagneticWrap', () => {
  afterEach(() => {
    cleanup();
    motionEnabled.value = true;
  });

  it('renders children unchanged when motion is enabled', () => {
    render(
      <MagneticWrap>
        <button>Bắt đầu</button>
      </MagneticWrap>,
    );
    expect(screen.getByRole('button', { name: 'Bắt đầu' })).toBeTruthy();
  });

  it('does not throw on mouse move/leave while motion is enabled', () => {
    render(
      <MagneticWrap className="wrap">
        <button>Bắt đầu</button>
      </MagneticWrap>,
    );
    const button = screen.getByRole('button', { name: 'Bắt đầu' });
    const wrap = button.parentElement as HTMLElement;

    expect(() => {
      wrap.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 40, clientY: 20 }));
      wrap.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
    }).not.toThrow();
  });

  it('falls back to a plain wrapper (no motion.div) when motion is disabled', () => {
    motionEnabled.value = false;
    render(
      <MagneticWrap className="wrap">
        <button>Bắt đầu</button>
      </MagneticWrap>,
    );
    const button = screen.getByRole('button', { name: 'Bắt đầu' });
    expect(button.parentElement?.className).toBe('wrap');
  });
});
