import { describe, expect, it } from 'vitest';

import { resolveConnectFailMessage } from '../src/pages/SourceLibraryPage';
import { translations } from '../src/i18n/translations';

// Regression: toast lỗi kết nối phải phản ánh nguyên nhân thật (message param
// từ backend `_finish(..., message=...)`), không chỉ hiện text chung chung.
describe('resolveConnectFailMessage', () => {
  const t = translations.en;

  it('maps a known message value (exchange_failed) to a specific reason', () => {
    const specific = resolveConnectFailMessage('exchange_failed', 'discord', t);
    const generic = resolveConnectFailMessage(null, 'discord', t);

    expect(specific).toContain('Discord');
    expect(specific).not.toBe(generic);
    expect(specific).toBe(t.sourcesPage.connectFailReasonExchangeFailed.replace('{provider}', 'Discord'));
  });

  it('maps another known message value (verify_failed) to its own specific reason', () => {
    const exchangeFailed = resolveConnectFailMessage('exchange_failed', 'telegram', t);
    const verifyFailed = resolveConnectFailMessage('verify_failed', 'telegram', t);

    expect(verifyFailed).not.toBe(exchangeFailed);
    expect(verifyFailed).toBe(t.sourcesPage.connectFailReasonVerifyFailed.replace('{provider}', 'Telegram'));
  });

  it('falls back to the generic message when message is missing', () => {
    const result = resolveConnectFailMessage(null, 'google', t);
    expect(result).toBe(t.sourcesPage.connectFailMsg.replace('{provider}', 'Google'));
  });

  it('falls back to the generic message for an unrecognised message value without crashing', () => {
    const result = resolveConnectFailMessage('some_future_reason_not_yet_known', 'jira', t);
    expect(result).toBe(t.sourcesPage.connectFailMsg.replace('{provider}', 'Jira'));
    expect(result).not.toContain('undefined');
  });

  it('also maps the known reasons in Vietnamese', () => {
    const tv = translations.vi;
    const specific = resolveConnectFailMessage('exchange_failed', 'discord', tv);
    const generic = resolveConnectFailMessage(null, 'discord', tv);
    expect(specific).not.toBe(generic);
  });
});
