import React from 'react';
import { ExternalLink, FileText } from 'lucide-react';
import { Button } from '../ui/Button';

type Props = { documentUrl: string; language: string; onOpenSources: () => void };

export const GoogleDocsConnectCard: React.FC<Props> = ({ documentUrl, language, onOpenSources }) => (
  <div className="mt-3 max-w-2xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3.5">
    <div className="flex items-start gap-3">
      <div className="rounded-lg bg-[var(--color-success-soft)] p-2 text-[var(--color-success)]">
        <FileText className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[var(--color-text-primary)]">
          {language === 'vi' ? 'Đã nhận diện một Google Docs' : 'Google Docs detected'}
        </p>
        <p className="mt-1 truncate text-xs text-[var(--color-text-secondary)]" title={documentUrl}>{documentUrl}</p>
        <p className="mt-2 text-xs leading-relaxed text-[var(--color-text-secondary)]">
          {language === 'vi'
            ? 'Mở Sources để kết nối Google và quét task từ tài liệu này.'
            : 'Open Sources to connect Google and scan tasks from this document.'}
        </p>
        <Button className="mt-3" size="xs" onClick={onOpenSources} icon={<ExternalLink className="h-3.5 w-3.5" />}>
          {language === 'vi' ? 'Mở và kết nối Google Docs' : 'Open Google Docs connection'}
        </Button>
      </div>
    </div>
  </div>
);
