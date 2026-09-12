import React from 'react';
import { ExternalLink, FileText } from 'lucide-react';
import { useAppStore } from '../../stores/useAppStore';
import { resolveBrandIcon } from '../ui/BrandIcons';

export interface SourceReferenceProps {
  source: {
    platform: string;
    location: string;
    author?: string;
    timestamp: string;
    rawContent?: string;
  };
  onClickViewSource?: () => void;
}

export const SourceReference: React.FC<SourceReferenceProps> = ({
  source,
  onClickViewSource,
}) => {
  const { openModal } = useAppStore();

  const getSourceIcon = (platform: string) =>
    resolveBrandIcon(platform, 'w-3.5 h-3.5') ?? (
      <FileText className="w-3.5 h-3.5 text-[var(--color-primary)]" />
    );

  const handleSourceClick = () => {
    if (onClickViewSource) {
      onClickViewSource();
    } else {
      openModal('source_detail', source);
    }
  };

  return (
    <div className="bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg p-3 text-xs space-y-1.5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 font-medium text-[var(--color-text-primary)]">
          {getSourceIcon(source.platform)}
          <span className="font-bold text-[var(--color-text-primary)]">{source.platform}</span>
          <span className="text-[var(--color-text-muted)]">·</span>
          <span className="text-[var(--color-text-secondary)]">{source.location}</span>
          {source.author && (
            <>
              <span className="text-[var(--color-text-muted)]">·</span>
              <span className="text-[var(--color-text-secondary)] italic">by {source.author}</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[var(--color-text-muted)]">{source.timestamp}</span>
          <button
            onClick={handleSourceClick}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--color-primary)] hover:text-[var(--color-text-primary)] hover:underline cursor-pointer"
          >
            <span>View raw source</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        </div>
      </div>

      {source.rawContent && (
        <div className="mt-1 pt-1.5 border-t border-[var(--color-border)]/60 text-[11px] text-[var(--color-text-secondary)] bg-[var(--color-surface-muted)] p-2 rounded border border-[var(--color-border)]/40 italic">
          <span className="not-italic font-medium text-[10px] text-[var(--color-text-primary)] block mb-0.5">
            Original Source Content:
          </span>
          "{source.rawContent}"
        </div>
      )}
    </div>
  );
};
