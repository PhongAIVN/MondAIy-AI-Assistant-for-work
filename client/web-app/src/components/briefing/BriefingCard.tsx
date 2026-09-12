import React from 'react';
import { type BriefingItem } from '../../types/briefing';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { ConfidenceBadge, CommitmentBadge, PriorityBadge } from '../ui/Badge';
import { SourceReference } from './SourceReference';
import { FeedbackActions } from './FeedbackActions';
import { useAppStore } from '../../stores/useAppStore';
import { useBriefingStore } from '../../stores/useBriefingStore';
import { ArrowRight, Eye, Calendar, Sparkles, X, AlertTriangle, MessageSquareCode } from 'lucide-react';

interface BriefingCardProps {
  item: BriefingItem;
}

export const BriefingCard: React.FC<BriefingCardProps> = ({ item }) => {
  const { openModal, addToast } = useAppStore();
  const { dismissItem } = useBriefingStore();

  if (item.dismissed) return null;

  const getAccentBorder = () => {
    if (item.confidence === 'ask_mentor') return 'warning';
    if (item.priority === 'urgent') return 'urgent';
    if (item.priority === 'important') return 'info';
    if (item.priority === 'update') return 'success';
    return 'none';
  };

  const handleReviewTask = () => {
    openModal('task_review', item);
  };

  const handleViewSource = () => {
    openModal('source_detail', item.source);
  };

  const handleReviewSchedule = () => {
    openModal('calendar_event', item);
  };

  const handleCompareSources = () => {
    openModal('conflict_compare', item);
  };

  const handleDismissDraft = () => {
    dismissItem(item.id);
    addToast({
      type: 'info',
      title: 'Suggestion Dismissed',
      message: 'Draft task suggestion was removed from your briefing.',
    });
  };

  return (
    <Card accentBorder={getAccentBorder()} className="space-y-4">
      {/* Header Badges & Title */}
      <div className="space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <PriorityBadge priority={item.priority} />
            <ConfidenceBadge level={item.confidence} />
            <CommitmentBadge level={item.commitment} />
          </div>

          {item.commitment === 'draft' && (
            <button
              onClick={handleDismissDraft}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] flex items-center gap-1 p-1 rounded hover:bg-[#F9DEDE] transition-colors"
              title="Dismiss draft suggestion"
            >
              <X className="w-3.5 h-3.5" /> Dismiss suggestion
            </button>
          )}
        </div>

        <h3 className="text-base font-bold text-[var(--color-text-primary)] font-heading flex items-center gap-2">
          {item.title}
          {item.dueDate && (
            <span className="text-xs font-semibold px-2 py-0.5 bg-[var(--color-accent-soft)] text-[var(--color-text-primary)] rounded-md border border-[var(--color-border)]">
              {item.dueDate}
            </span>
          )}
        </h3>
      </div>

      {/* Summary & Discrepancy details */}
      <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
        {item.summary}
      </p>

      {/* Previous vs Current Value (for changes) */}
      {item.previousValue && item.currentValue && (
        <div className="bg-[var(--color-accent-soft)] border border-[var(--color-border-subtle)] rounded-lg p-3 text-xs flex items-center justify-between gap-4">
          <div>
            <span className="text-[10px] font-medium text-[var(--color-text-secondary)] block">Previous</span>
            <span className="line-through text-[var(--color-danger)] font-medium">{item.previousValue}</span>
          </div>
          <ArrowRight className="w-4 h-4 text-[var(--color-primary)] shrink-0" />
          <div>
            <span className="text-[10px] font-medium text-[var(--color-success)] block">Current</span>
            <span className="text-[var(--color-success)] font-bold">{item.currentValue}</span>
          </div>
        </div>
      )}

      {/* Structured Answer: Why relevant & Next action */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="bg-[var(--color-accent-soft)] p-3 rounded-lg border border-[var(--color-border-subtle)]">
          <span className="text-[10px] font-medium text-[#1E4E85] block mb-1">
            2. Why is it relevant to me?
          </span>
          <p className="text-[var(--color-text-primary)] font-medium">{item.relevance}</p>
        </div>

        <div className="bg-[var(--color-success-soft)] p-3 rounded-lg border border-[var(--color-success)]/30">
          <span className="text-[10px] font-medium text-[var(--color-success)] block mb-1">
            3. What should I do next?
          </span>
          <p className="text-[var(--color-text-primary)] font-medium">{item.nextAction}</p>
        </div>
      </div>

      {/* Conflict Special Callout */}
      {item.conflictDetails && (
        <div className="bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-lg p-3 text-xs space-y-2">
          <div className="flex items-center gap-2 font-bold text-[var(--color-warning)]">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>Connected sources disagree regarding deadline</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
            <div className="p-2 bg-[var(--color-surface-muted)] rounded border border-[var(--color-border)]">
              <span className="font-bold text-[var(--color-text-primary)]">{item.conflictDetails.sourceA.platform}</span> ({item.conflictDetails.sourceA.location}):
              <p className="font-semibold text-[var(--color-success)] mt-0.5">{item.conflictDetails.sourceA.value}</p>
            </div>
            <div className="p-2 bg-[var(--color-surface-muted)] rounded border border-[var(--color-border)]">
              <span className="font-bold text-[var(--color-text-primary)]">{item.conflictDetails.sourceB.platform}</span> ({item.conflictDetails.sourceB.location}):
              <p className="font-semibold text-[var(--color-danger)] mt-0.5">{item.conflictDetails.sourceB.value}</p>
            </div>
          </div>
        </div>
      )}

      {/* Source Reference Block */}
      <SourceReference source={item.source} onClickViewSource={handleViewSource} />

      {/* Interactive Action Buttons */}
      <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
        <div className="flex items-center gap-2 flex-wrap">
          {item.conflictDetails ? (
            <>
              <Button
                variant="warning"
                size="sm"
                icon={<AlertTriangle className="w-3.5 h-3.5" />}
                onClick={handleCompareSources}
              >
                Compare sources
              </Button>
              <Button
                variant="outline"
                size="sm"
                icon={<MessageSquareCode className="w-3.5 h-3.5" />}
                onClick={handleCompareSources}
              >
                Draft verification question
              </Button>
            </>
          ) : (
            <>
              {item.category === 'possible_tasks' ? (
                <Button
                  variant="primary"
                  size="sm"
                  icon={<Sparkles className="w-3.5 h-3.5" />}
                  onClick={handleReviewTask}
                >
                  Review draft task
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  icon={<ArrowRight className="w-3.5 h-3.5" />}
                  onClick={handleReviewTask}
                >
                  Review task
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                icon={<Eye className="w-3.5 h-3.5" />}
                onClick={handleViewSource}
              >
                View source
              </Button>

              <Button
                variant="ghost"
                size="sm"
                icon={<Calendar className="w-3.5 h-3.5" />}
                onClick={handleReviewSchedule}
              >
                Review schedule
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Feedback Bar */}
      <FeedbackActions itemId={item.id} currentFeedback={item.userFeedback} />
    </Card>
  );
};
