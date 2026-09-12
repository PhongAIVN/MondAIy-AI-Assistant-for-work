import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';

import {
  hasSeenTour,
  markTourSeen,
  resetTourSeen,
  useOnboardingTour,
} from '../src/hooks/useOnboardingTour';

const { driveMock, driverMock } = vi.hoisted(() => {
  const driveMock = vi.fn();
  const driverMock = vi.fn((config: Record<string, unknown>) => ({
    drive: driveMock,
    destroy: vi.fn(),
    __config: config,
  }));
  return { driveMock, driverMock };
});

vi.mock('driver.js', () => ({ driver: driverMock }));
vi.mock('driver.js/dist/driver.css', () => ({}));

const TourHarness = ({ tourId }: { tourId: string }) => {
  const { startTour } = useOnboardingTour(tourId);
  return (
    <button
      onClick={() =>
        startTour([{ element: '[data-tour-id="a"]', popover: { title: 'A' } }])
      }
    >
      start
    </button>
  );
};

describe('useOnboardingTour', () => {
  afterEach(() => {
    cleanup();
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('reports unseen by default, then seen after markTourSeen', () => {
    expect(hasSeenTour('welcome')).toBe(false);
    markTourSeen('welcome');
    expect(hasSeenTour('welcome')).toBe(true);
    resetTourSeen('welcome');
    expect(hasSeenTour('welcome')).toBe(false);
  });

  it('starts driver.js with the given steps and calls drive()', () => {
    render(<TourHarness tourId="welcome" />);
    screen.getByRole('button', { name: 'start' }).click();

    expect(driverMock).toHaveBeenCalledTimes(1);
    const config = driverMock.mock.calls[0][0];
    expect(config.steps).toEqual([{ element: '[data-tour-id="a"]', popover: { title: 'A' } }]);
    expect(driveMock).toHaveBeenCalledTimes(1);
  });

  it('marks the tour as seen once driver.js reports onDestroyed', () => {
    render(<TourHarness tourId="welcome" />);
    expect(hasSeenTour('welcome')).toBe(false);

    screen.getByRole('button', { name: 'start' }).click();
    const config = driverMock.mock.calls[0][0];
    config.onDestroyed();

    expect(hasSeenTour('welcome')).toBe(true);
  });
});
