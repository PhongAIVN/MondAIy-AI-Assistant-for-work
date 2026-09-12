// @vitest-environment jsdom

import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { CommandPalette } from '../src/components/ui/CommandPalette';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';
import { usePipelineRunStore } from '../src/stores/usePipelineRunStore';

function renderPalette() {
  return render(
    <MemoryRouter>
      <CommandPalette isOpen onClose={() => {}} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  usePipelineRunStore.setState({ connections: [] });
  usePreferencesStore.setState({ onboardingDismissed: false });
});

afterEach(() => {
  cleanup();
});

describe('CommandPalette', () => {
  it('no longer shows a Tasks & Deliverables group — task previews were dropped from quick search', () => {
    renderPalette();

    expect(screen.queryByText('Tasks & Deliverables')).toBeNull();
    expect(screen.queryByText(/Gate 1/i)).toBeNull();
  });

  it('hides the onboarding wizard entry once onboarding is dismissed', () => {
    usePreferencesStore.setState({ onboardingDismissed: true });
    renderPalette();

    expect(screen.queryByText('Onboarding Setup Wizard')).toBeNull();
  });

  it('shows the onboarding wizard entry while onboarding is not yet dismissed', () => {
    usePreferencesStore.setState({ onboardingDismissed: false });
    renderPalette();

    expect(screen.getByText('Onboarding Setup Wizard')).toBeTruthy();
  });

  it('no longer lists the removed Program Calendar, Activity, or prototype test pages', () => {
    renderPalette();

    expect(screen.queryByText('Usability Test Console')).toBeNull();
    expect(screen.queryByText(/Program Calendar/i)).toBeNull();
    expect(screen.queryByText(/Activity & Audit Trail/i)).toBeNull();
  });

  it('no longer offers the destructive "Reset Data" prototype action', () => {
    renderPalette();

    expect(screen.queryByText('Reset Data')).toBeNull();
  });

  it('offers the Ask mondaiy action that replaced the sidebar Run Briefing entry', () => {
    renderPalette();

    // Contract UI hiện tại: action đầu tiên của palette là 'Hỏi mondaiy'
    // (t.nav.askNavigator), kế thừa chỗ của Run Briefing cũ.
    expect(screen.getByText('Hỏi mondaiy')).toBeTruthy();
  });
});
