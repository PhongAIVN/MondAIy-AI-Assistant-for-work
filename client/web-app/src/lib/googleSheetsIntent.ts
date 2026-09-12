export type GoogleSheetPrefill = {
  spreadsheetUrl: string;
  sheetName: string;
};

export const PENDING_GOOGLE_SHEET_KEY = 'mondaiy.pendingGoogleSheet.v1';

const GOOGLE_SHEETS_URL = /^https?:\/\/(?:docs\.)?google\.com\/spreadsheets\/d\/[a-zA-Z0-9_-]+(?:[/?#].*)?$/i;

export const isGoogleSheetsUrl = (value: string): boolean => GOOGLE_SHEETS_URL.test(value.trim());

export const extractGoogleSheetsUrl = (text: string): string | null => {
  const match = text.match(/https?:\/\/(?:docs\.)?google\.com\/spreadsheets\/d\/[a-zA-Z0-9_-]+(?:[/?#][^\s<>)]+)?/i);
  return match && isGoogleSheetsUrl(match[0]) ? match[0].replace(/[.,;!?]+$/, '') : null;
};

export const readGoogleSheetPrefill = (): GoogleSheetPrefill | null => {
  try {
    const raw = sessionStorage.getItem(PENDING_GOOGLE_SHEET_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GoogleSheetPrefill>;
    if (typeof parsed.spreadsheetUrl !== 'string' || !isGoogleSheetsUrl(parsed.spreadsheetUrl)) return null;
    return { spreadsheetUrl: parsed.spreadsheetUrl, sheetName: typeof parsed.sheetName === 'string' && parsed.sheetName.trim() ? parsed.sheetName : 'Backlog' };
  } catch {
    return null;
  }
};

export const saveGoogleSheetPrefill = (prefill: GoogleSheetPrefill): void => {
  try {
    sessionStorage.setItem(PENDING_GOOGLE_SHEET_KEY, JSON.stringify(prefill));
  } catch {
    // Private browsing may disable session storage; the Sources page remains usable.
  }
};
