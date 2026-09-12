import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { LandingUseCases } from '../src/components/marketing/LandingSections';

const { motionEnabled } = vi.hoisted(() => ({ motionEnabled: { value: true } }));

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => motionEnabled.value,
}));

describe('landing scroll-reveal + hover (GSAP)', () => {
  afterEach(() => {
    cleanup();
    motionEnabled.value = true;
  });

  it('renders use-case cards with reveal/hover wired when motion is enabled', () => {
    expect(() => render(<LandingUseCases />)).not.toThrow();
    expect(screen.getAllByRole('heading', { level: 3 }).length).toBeGreaterThan(0);
  });

  it('renders the same content when motion is disabled, without animation props', () => {
    motionEnabled.value = false;
    expect(() => render(<LandingUseCases />)).not.toThrow();
    expect(screen.getAllByRole('heading', { level: 3 }).length).toBeGreaterThan(0);
  });

  it('does not throw when the mouse moves over a tilted card', () => {
    render(<LandingUseCases />);
    const card = screen.getAllByRole('heading', { level: 3 })[0].closest('div');
    expect(card).toBeTruthy();
    expect(() => {
      card!.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 10, clientY: 10 }));
      card!.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
    }).not.toThrow();
  });
});
