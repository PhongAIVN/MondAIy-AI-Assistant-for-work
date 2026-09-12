import React from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { Dialog } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { ShieldAlert } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

export const SourceDetailModal: React.FC = () => {
  const { activeModal, modalData, closeModal, addToast } = useAppStore();
  const { language } = useTranslation();
  const vi = language === 'vi';

  if (activeModal !== 'source_detail' || !modalData) return null;

  const source = modalData;

  const handleCopyRaw = () => {
    if (source.rawContent) {
      navigator.clipboard.writeText(source.rawContent);
      addToast({
        type: 'info',
        title: vi ? 'Đã sao chép' : 'Copied to Clipboard',
        message: vi ? 'Đã sao chép trích đoạn nguồn gốc.' : 'Original source excerpt copied to clipboard.',
      });
    }
  };

  return (
    <Dialog
      isOpen={activeModal === 'source_detail'}
      onClose={closeModal}
      title={vi ? 'Bằng chứng nguồn gốc' : 'Original Source Evidence'}
      description={vi ? 'Tham chiếu có thể truy xuất từ các nguồn đã kết nối' : 'Traceable reference from connected platform feeds'}
      maxWidth="md"
      footer={
        <div className="flex items-center justify-between w-full">
          <span className="text-[11px] text-[var(--color-text-secondary)]">{vi ? 'Mã xác thực' : 'Verification Hash'}: #SRC-2026-9482</span>
          <Button variant="outline" size="sm" onClick={closeModal}>
            {vi ? 'Đóng' : 'Close'}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        <div className="p-3 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border-subtle)] space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[var(--color-text-primary)] text-sm">{source.platform}</span>
            <span className="text-[11px] text-[var(--color-text-muted)]">{source.timestamp}</span>
          </div>
          <p className="text-[var(--color-text-secondary)]">{vi ? 'Kênh / Nguồn' : 'Channel / Feed'}: <strong className="text-[var(--color-text-primary)]">{source.location}</strong></p>
          {source.author && <p className="text-[var(--color-text-secondary)]">{vi ? 'Tác giả' : 'Author'}: <strong className="text-[var(--color-text-primary)]">{source.author}</strong></p>}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="font-bold text-[var(--color-text-primary)] text-xs">{vi ? 'Bài đăng gốc, chưa chỉnh sửa' : 'Unedited Raw Source Post'}</label>
            <button
              onClick={handleCopyRaw}
              className="text-[11px] text-[var(--color-primary)] hover:underline font-semibold"
            >
              {vi ? 'Sao chép trích đoạn' : 'Copy Excerpt'}
            </button>
          </div>
          <div className="p-4 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl text-xs text-[var(--color-text-primary)] leading-relaxed whitespace-pre-wrap">
            {source.rawContent || (vi ? 'Không có đoạn trích thô đính kèm.' : 'No raw text snippet attached.')}
          </div>
        </div>

        <div className="p-3 bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-xl text-[11px] text-[var(--color-warning)] flex items-start gap-2">
          <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            <strong>{vi ? 'Cam kết minh bạch:' : 'Transparency Guarantee:'}</strong>{' '}
            {vi
              ? 'mondaiy hiển thị nguyên văn thông điệp gốc và không bao giờ chỉnh sửa lịch sử nguồn.'
              : 'mondaiy displays original source messages verbatim and never alters historical source records.'}
          </span>
        </div>
      </div>
    </Dialog>
  );
};
