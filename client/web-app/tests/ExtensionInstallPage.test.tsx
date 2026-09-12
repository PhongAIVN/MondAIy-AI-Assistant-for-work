// @vitest-environment jsdom

import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { translations } from '../src/i18n/translations';
import {
  EXTENSION_DOWNLOAD_PATH,
  ExtensionInstallPage,
} from '../src/pages/marketing/ExtensionInstallPage';

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ t: translations.vi }),
}));

afterEach(cleanup);

describe('ExtensionInstallPage', () => {
  it('offers the published ZIP with a stable download filename', () => {
    render(
      <MemoryRouter>
        <ExtensionInstallPage />
      </MemoryRouter>,
    );

    const download = screen.getByRole('link', { name: translations.vi.extensionInstall.download });
    expect(download.getAttribute('href')).toBe(EXTENSION_DOWNLOAD_PATH);
    expect(download.getAttribute('download')).toBe('mondaiy-extension-chrome.zip');
  });

  it('explains all observable manual-install steps and copies the Chrome extensions URL', async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    render(
      <MemoryRouter>
        <ExtensionInstallPage />
      </MemoryRouter>,
    );

    expect(screen.getAllByRole('listitem')).toHaveLength(5);
    expect(screen.getByText(translations.vi.extensionInstall.step1Title)).toBeTruthy();
    expect(screen.getByText(translations.vi.extensionInstall.step4Title)).toBeTruthy();
    expect(screen.getByText(/không chọn chính file ZIP/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /chrome:\/\/extensions/i }));
    expect(writeText).toHaveBeenCalledWith('chrome://extensions');
    expect(await screen.findByText(translations.vi.extensionInstall.copiedUrl)).toBeTruthy();
  });
});
