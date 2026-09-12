export type GoogleDocPrefill = { documentUrl: string };

export const PENDING_GOOGLE_DOC_KEY = 'mondaiy.pendingGoogleDoc.v1';

const GOOGLE_DOCS_URL = /^https?:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9_-]+(?:[/?#].*)?$/i;

export const isGoogleDocsUrl = (value: string): boolean => GOOGLE_DOCS_URL.test(value.trim());

export const extractGoogleDocsUrl = (text: string): string | null => {
  const match = text.match(/https?:\/\/docs\.google\.com\/document\/d\/[a-zA-Z0-9_-]+(?:[/?#][^\s<>)]+)?/i);
  return match && isGoogleDocsUrl(match[0]) ? match[0].replace(/[.,;!?]+$/, '') : null;
};

export const readGoogleDocPrefill = (): GoogleDocPrefill | null => {
  try {
    const raw = sessionStorage.getItem(PENDING_GOOGLE_DOC_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GoogleDocPrefill>;
    if (typeof parsed.documentUrl !== 'string' || !isGoogleDocsUrl(parsed.documentUrl)) return null;
    return { documentUrl: parsed.documentUrl };
  } catch {
    return null;
  }
};

export const saveGoogleDocPrefill = (prefill: GoogleDocPrefill): void => {
  try {
    sessionStorage.setItem(PENDING_GOOGLE_DOC_KEY, JSON.stringify(prefill));
  } catch {
    // Private browsing may disable session storage; Sources remains usable.
  }
};
