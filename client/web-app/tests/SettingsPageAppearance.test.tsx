// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { SettingsPage } from '../src/pages/SettingsPage';
import { usePreferencesStore } from '../src/stores/usePreferencesStore';

beforeEach(() => {
  usePreferencesStore.getState().resetAllPrototypeData();
});

afterEach(cleanup);

describe('SettingsPage — appearance tab', () => {
  it('drops the appearance tab entirely, since theme mode now lives only in the user menu', () => {
    render(<SettingsPage />);

    expect(screen.queryByText('Giao diện')).toBeNull();
    expect(screen.queryByRole('button', { name: /Giao diện/ })).toBeNull();
    for (const label of ['Sáng', 'Tối', 'Trắng tinh', 'Đen tuyệt đối', 'Hệ thống']) {
      expect(screen.queryByRole('button', { name: label })).toBeNull();
    }
    // Trang vẫn mở được, chỉ khởi động ở tab Ngôn ngữ thay vì Giao diện đã mất.
    expect(screen.getAllByText('Ngôn ngữ').length).toBeGreaterThan(0);
  });
});
