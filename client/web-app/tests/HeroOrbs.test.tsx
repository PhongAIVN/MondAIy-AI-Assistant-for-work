import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import { HeroOrbs } from '../src/components/marketing/HeroOrbs';

const { motionEnabled } = vi.hoisted(() => ({ motionEnabled: { value: true } }));

vi.mock('../src/hooks/useMotionEnabled', () => ({
  useMotionEnabled: () => motionEnabled.value,
}));

describe('HeroOrbs', () => {
  afterEach(() => {
    cleanup();
    motionEnabled.value = true;
  });

  it('renders and floats/parallaxes without throwing when motion is enabled', () => {
    expect(() => render(<HeroOrbs />)).not.toThrow();
    expect(() => {
      window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100, clientY: 100 }));
    }).not.toThrow();
  });

  it('renders without throwing when motion is disabled', () => {
    motionEnabled.value = false;
    expect(() => render(<HeroOrbs />)).not.toThrow();
    expect(() => {
      window.dispatchEvent(new MouseEvent('mousemove', { clientX: 100, clientY: 100 }));
    }).not.toThrow();
  });
});
