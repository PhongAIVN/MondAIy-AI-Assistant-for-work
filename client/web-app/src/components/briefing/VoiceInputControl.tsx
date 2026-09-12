import React from 'react';
import { Check, Mic, MicOff, X } from 'lucide-react';

interface VoiceInputTriggerProps {
  language: 'vi' | 'en';
  /** Bắt đầu ghi âm thật (SpeechRecognition) ngay khi bấm — do trang cha sở hữu. */
  onStart: () => void;
  className?: string;
}

/**
 * Nút mic trên thanh soạn tin: bấm là ghi âm ngay, tự dùng micro mặc định
 * của hệ điều hành. Từng có popover chọn thiết bị thu, nhưng Web Speech API
 * không cho chọn thiết bị capture cụ thể — deviceId chọn ở đó chỉ đổi được
 * thanh preview, không đổi được nguồn ghi thật, nên bỏ hẳn cho gọn.
 */
export const VoiceInputTrigger: React.FC<VoiceInputTriggerProps> = ({ language, onStart, className = '' }) => (
  <button
    type="button"
    onClick={onStart}
    className={`p-2 rounded-xl text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-hover)] ${className}`}
    title={language === 'vi' ? 'Gửi bằng giọng nói' : 'Send with voice'}
    aria-label={language === 'vi' ? 'Gửi bằng giọng nói' : 'Send with voice'}
  >
    <Mic className="w-4 h-4" />
  </button>
);

interface VoiceListeningBarProps {
  language: 'vi' | 'en';
  levels: number[];
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Thay hẳn ô nhập liệu khi đang ghi âm — mascot bên trái, "Đang nghe..." +
 * waveform + Hủy/Xong bên phải. Mascot nằm chung khối này nên tắt/hiện luôn
 * đồng bộ với 2 hàng kia, không cần đồng bộ trạng thái riêng.
 */
export const VoiceListeningBar: React.FC<VoiceListeningBarProps> = ({
  language,
  levels,
  onCancel,
  onConfirm,
}) => (
  <div className="flex w-full items-center gap-3 py-0.5">
    <img
      src="/loadinggif2.gif"
      alt=""
      aria-hidden="true"
      className="h-14 w-14 shrink-0 animate-in fade-in zoom-in-95 duration-200"
    />
    <div className="flex min-w-0 flex-1 flex-col gap-2">
      <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-muted)]">
        <MicOff className="h-3.5 w-3.5 animate-pulse text-[var(--color-danger)]" />
        {language === 'vi' ? 'Đang nghe...' : 'Listening...'}
      </span>
      <div className="flex items-center gap-2">
        <div className="flex h-8 flex-1 items-center gap-[3px] overflow-hidden" aria-hidden="true">
          {levels.map((level, index) => (
            <span
              key={index}
              className="w-[3px] shrink-0 rounded-full bg-[var(--color-primary)] transition-[height] duration-75"
              style={{ height: `${Math.max(8, level * 100)}%` }}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="shrink-0 rounded-xl bg-[var(--color-surface-hover)] p-2 text-[var(--color-text-secondary)] transition-colors hover:bg-[#F9DEDE] hover:text-[var(--color-danger)]"
          aria-label={language === 'vi' ? 'Hủy ghi âm' : 'Cancel recording'}
          title={language === 'vi' ? 'Hủy' : 'Cancel'}
        >
          <X className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="shrink-0 rounded-xl bg-[var(--color-primary)] p-2 text-[var(--color-on-primary)] shadow-2xs transition-colors hover:bg-[var(--color-primary-hover)]"
          aria-label={language === 'vi' ? 'Xong, gửi giọng nói' : 'Done, send voice'}
          title={language === 'vi' ? 'Xong' : 'Done'}
        >
          <Check className="h-4 w-4" />
        </button>
      </div>
    </div>
  </div>
);
