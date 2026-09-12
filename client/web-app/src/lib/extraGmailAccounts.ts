/** Tài khoản Gmail thêm (prototype local) — chưa OAuth đa account. TODO(multi-gmail-oauth) */

export type ExtraGmailAccount = {
  id: string;
  email: string;
  connectedAt: string;
};

const STORAGE_KEY = 'mondaiy.extraGmailAccounts.v1';

const normalizeEmail = (email: string): string => email.trim().toLowerCase();

export const listExtraGmailAccounts = (): ExtraGmailAccount[] => {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (row): row is ExtraGmailAccount =>
        typeof row?.id === 'string' &&
        typeof row?.email === 'string' &&
        typeof row?.connectedAt === 'string',
    );
  } catch {
    return [];
  }
};

const writeExtraGmailAccounts = (accounts: ExtraGmailAccount[]): void => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(accounts));
};

export const addExtraGmailAccount = (
  email: string,
  existingPrimaryEmail?: string | null,
): { ok: true; account: ExtraGmailAccount } | { ok: false; reason: 'empty' | 'invalid' | 'duplicate' } => {
  const normalized = normalizeEmail(email);
  if (!normalized) return { ok: false, reason: 'empty' };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) return { ok: false, reason: 'invalid' };

  const current = listExtraGmailAccounts();
  const primary = existingPrimaryEmail ? normalizeEmail(existingPrimaryEmail) : '';
  if (primary && primary === normalized) return { ok: false, reason: 'duplicate' };
  if (current.some((a) => normalizeEmail(a.email) === normalized)) {
    return { ok: false, reason: 'duplicate' };
  }

  const account: ExtraGmailAccount = {
    id: `extra-gmail-${Date.now()}`,
    email: normalized,
    connectedAt: new Date().toISOString(),
  };
  writeExtraGmailAccounts([account, ...current]);
  return { ok: true, account };
};

export const removeExtraGmailAccount = (id: string): void => {
  writeExtraGmailAccounts(listExtraGmailAccounts().filter((a) => a.id !== id));
};
