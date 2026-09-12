import React from 'react';
import { ExternalLink, FileSpreadsheet } from 'lucide-react';
import { Button } from '../ui/Button';

type Props = {
  spreadsheetUrl: string;
  language: string;
  onOpenSources: () => void;
};

export const GoogleSheetsConnectCard: React.FC<Props> = ({ spreadsheetUrl, language, onOpenSources }) => (
  <div className="mt-3 max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3.5">
    <div className="flex items-start gap-3">
      <div className="rounded-lg bg-[var(--color-success-soft)] p-2 text-[var(--color-success)]">
        <FileSpreadsheet className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[var(--color-text-primary)]">
          {language === 'vi' ? 'Đã nhận diện một Google Sheet' : 'Google Sheet detected'}
        </p>
        <p className="mt-1 truncate text-xs text-[var(--color-text-secondary)]" title={spreadsheetUrl}>{spreadsheetUrl}</p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {language === 'vi'
            ? 'Mở Sources để kết nối Google (nếu cần), kiểm tra tên tab rồi quét task. Bạn có thể sửa URL hoặc tab trước khi đọc.'
            : 'Open Sources to connect Google if needed, verify the tab name, and scan tasks. You can edit the URL or tab before scanning.'}
        </p>
        <Button className="mt-3" size="xs" onClick={onOpenSources} icon={<ExternalLink className="h-3.5 w-3.5" />}>
          {language === 'vi' ? 'Mở và kết nối Google Sheets' : 'Open Google Sheets connection'}
        </Button>
      </div>
    </div>
  </div>
);
