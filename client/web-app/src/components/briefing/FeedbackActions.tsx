import React from 'react';
import { type FeedbackType } from '../../types/briefing';
import { useBriefingStore } from '../../stores/useBriefingStore';
import { useAppStore } from '../../stores/useAppStore';
import { ThumbsUp, ThumbsDown, AlertCircle, CheckCircle } from 'lucide-react';

export type ConversationFeedback = 'helpful' | 'partly' | 'incorrect';

interface FeedbackActionsProps {
  itemId: string;
  currentFeedback?: FeedbackType;
  /** Conversation mode: current feedback on a chat message */
  initialFeedback?: ConversationFeedback | null;
  /** Conversation mode: when provided, feedback is delegated instead of written to the briefing store */
  onFeedbackSelect?: (feedback: ConversationFeedback | null) => void;
}

export const FeedbackActions: React.FC<FeedbackActionsProps> = ({
  itemId,
  currentFeedback,
  initialFeedback,
  onFeedbackSelect,
}) => {
  const { updateItemFeedback } = useBriefingStore();
  const { addToast } = useAppStore();

  // Conversation mode: compact 3-option row wired to the conversation store
  if (onFeedbackSelect) {
    const convOptions: { type: ConversationFeedback; label: string; Icon: typeof ThumbsUp }[] = [
      { type: 'helpful', label: 'Helpful', Icon: ThumbsUp },
      { type: 'incorrect', label: 'Incorrect', Icon: ThumbsDown },
    ];

    return (
      <div className="flex items-center gap-1">
        {convOptions.map(({ type, label, Icon }) => {
          const active = initialFeedback === type;
          return (
            <button
              key={type}
              onClick={() => onFeedbackSelect(active ? null : type)}
              title={label}
              aria-label={label}
              aria-pressed={active}
              className={`inline-flex h-9 w-9 items-center justify-center rounded-xl transition-colors cursor-pointer ${
                active
                  ? 'bg-[var(--color-accent-soft)] text-[var(--color-primary)]'
                  : 'bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)]'
              }`}
            >
              {/* Đã chọn thì icon TÔ ĐẶC (fill) — dấu hiệu "đã bấm" phải sống
                  trên chính icon, không chỉ dựa hover đổi nền (biến mất ngay
                  khi rê chuột ra, người dùng quên mình đã bấm gì). */}
              <Icon className="h-3.5 w-3.5" fill={active ? 'currentColor' : 'none'} />
            </button>
          );
        })}
      </div>
    );
  }

  const handleFeedback = (type: FeedbackType, label: string) => {
    updateItemFeedback(itemId, type);
    addToast({
      type: 'success',
      title: 'Feedback Saved',
      message: `Marked as "${label}". mondaiy will refine future interpretations based on this.`,
    });
  };

  const feedbackOptions: { type: FeedbackType; label: string; icon: React.ReactNode }[] = [
    { type: 'relevant', label: 'Relevant', icon: <ThumbsUp className="w-3 h-3" /> },
    { type: 'not_relevant', label: 'Not relevant', icon: <ThumbsDown className="w-3 h-3" /> },
    { type: 'inaccurate', label: 'Inaccurate', icon: <AlertCircle className="w-3 h-3" /> },
    { type: 'already_knew', label: 'Already knew this', icon: <CheckCircle className="w-3 h-3" /> },
  ];

  if (currentFeedback) {
    const activeLabel = feedbackOptions.find((f) => f.type === currentFeedback)?.label || currentFeedback;
    return (
      <div className="flex items-center justify-between pt-2 border-t border-[var(--color-border)] text-xs">
        <span className="text-[11px] text-[var(--color-success)] dark:text-[#8CC3A2] font-semibold flex items-center gap-1">
          <CheckCircle className="w-3.5 h-3.5" /> Marked as "{activeLabel}" · Thanks for your feedback!
        </span>
        <button
          onClick={() => handleFeedback(currentFeedback === 'relevant' ? 'not_relevant' : 'relevant', 'Updated')}
          className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] dark:hover:text-white underline"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="pt-2 border-t border-[var(--color-border)] flex items-center justify-between flex-wrap gap-2 text-xs">
      <span className="text-[11px] font-medium text-[var(--color-text-muted)]">Is this briefing item accurate & helpful?</span>
      <div className="flex items-center gap-1.5 flex-wrap">
        {feedbackOptions.map((opt) => (
          <button
            key={opt.type}
            onClick={() => handleFeedback(opt.type, opt.label)}
            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-[var(--color-text-secondary)] bg-[var(--color-accent-soft)] hover:bg-[var(--color-accent-soft)] dark:hover:bg-[#2563A6]/30 hover:text-[var(--color-text-primary)] dark:hover:text-white rounded-md transition-colors cursor-pointer border border-[var(--color-border)]"
          >
            {opt.icon}
            <span>{opt.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
