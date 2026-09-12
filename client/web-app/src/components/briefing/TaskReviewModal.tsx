import React, { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { Dialog } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { ConfidenceBadge, CommitmentBadge, PriorityBadge } from '../ui/Badge';
import { SourceReference } from './SourceReference';
import { type BriefingItem } from '../../types/briefing';
import { CheckCircle2, ShieldCheck, Clock } from 'lucide-react';

export const TaskReviewModal: React.FC = () => {
  const { activeModal, modalData, closeModal, addToast } = useAppStore();
  const [prepNotes, setPrepNotes] = useState('');
  const [isConfirming, setIsConfirming] = useState(false);

  if (activeModal !== 'task_review' || !modalData) return null;

  const item: BriefingItem = modalData;

  const handleConfirmTask = () => {
    setIsConfirming(true);
    setTimeout(() => {
      setIsConfirming(false);
      addToast({
        type: 'success',
        title: 'Task Confirmed',
        message: `"${item.title}" saved to My Tasks with Committed status.`,
      });
      closeModal();
    }, 400);
  };

  return (
    <Dialog
      isOpen={activeModal === 'task_review'}
      onClose={closeModal}
      title="Task Review & Confirmation"
      description="mondaiy identified this item. Review details before saving to your persistent task tracker."
      maxWidth="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <p className="text-[11px] text-[var(--color-text-secondary)] italic flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" /> Explicit confirmation required to add to My Tasks
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<CheckCircle2 className="w-4 h-4" />}
              onClick={handleConfirmTask}
              disabled={isConfirming}
            >
              {isConfirming ? 'Confirming...' : 'Confirm & Save to My Tasks'}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {/* Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <PriorityBadge priority={item.priority} />
          <ConfidenceBadge level={item.confidence} />
          <CommitmentBadge level={item.commitment} />
        </div>

        {/* Task Title & Summary */}
        <div>
          <h4 className="text-base font-bold text-[var(--color-text-primary)] font-heading">{item.title}</h4>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">{item.summary}</p>
        </div>

        {/* Relevance and Next Actions */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="p-3 bg-[var(--color-accent-soft)] rounded-lg border border-[var(--color-border-subtle)]">
            <span className="font-bold text-[var(--color-text-primary)] block mb-1">Relevance to Program</span>
            <p className="text-[var(--color-text-primary)]">{item.relevance}</p>
          </div>

          <div className="p-3 bg-[var(--color-success-soft)] rounded-lg border border-[var(--color-success)]/30">
            <span className="font-bold text-[var(--color-success)] block mb-1">Recommended Action</span>
            <p className="text-[var(--color-text-primary)]">{item.nextAction}</p>
          </div>
        </div>

        {/* Due date & preparation estimate */}
        <div className="flex items-center justify-between p-3 bg-[var(--color-accent-soft)] rounded-lg border border-[var(--color-border)]">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[var(--color-primary)]" />
            <div>
              <span className="text-[10px] text-[var(--color-text-muted)] font-medium block">Target Due Date</span>
              <span className="font-bold text-[var(--color-text-primary)]">{item.dueDate || 'Today · 11:59 PM'}</span>
            </div>
          </div>
          <div className="text-right">
            <span className="text-[10px] text-[var(--color-text-muted)] font-medium block">Estimated Preparation</span>
            <span className="font-semibold text-[var(--color-text-primary)]">45 minutes</span>
          </div>
        </div>

        {/* Add User Notes */}
        <div>
          <label className="block text-xs font-bold text-[var(--color-text-primary)] mb-1">
            Personal Preparation Notes (Optional)
          </label>
          <textarea
            rows={2}
            value={prepNotes}
            onChange={(e) => setPrepNotes(e.target.value)}
            placeholder="Add links, draft text, or reminders before confirming..."
            className="w-full p-2.5 text-xs bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:bg-[var(--color-surface-muted)]"
          />
        </div>

        {/* Source Evidence */}
        <div className="pt-2">
          <span className="text-xs font-bold text-[var(--color-text-primary)] block mb-1">Traceable Source Evidence</span>
          <SourceReference source={item.source} />
        </div>
      </div>
    </Dialog>
  );
};
