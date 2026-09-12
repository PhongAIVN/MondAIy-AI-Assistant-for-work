import React, { useState } from 'react';
import { MessageSquare, Sparkles, Star } from 'lucide-react';
import { Dialog } from './Dialog';
import { useTranslation } from '../../i18n/useTranslation';

type Props = {
  isOpen: boolean;
  actionCount: number;
  isManual?: boolean;
  onSubmit: (rating: number, feedback: string) => Promise<void>;
  onDismiss: () => void;
};

const MIN_FEEDBACK_LENGTH = 1;

export const ProductRatingModal: React.FC<Props> = ({
  isOpen,
  actionCount,
  isManual = false,
  onSubmit,
  onDismiss,
}) => {
  const { t } = useTranslation();
  const r = t.productRating;
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!rating || feedback.trim().length < MIN_FEEDBACK_LENGTH) return;
    setSaving(true);
    setError('');
    try {
      await onSubmit(rating, feedback);
      setRating(0);
      setFeedback('');
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : r.genericError);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onDismiss}
      maxWidth="sm"
      title={isManual ? r.modalTitleManual : r.modalTitleAuto}
      description={isManual ? r.descManual : r.descAuto}
      footer={(
        <>
          <button
            onClick={onDismiss}
            disabled={saving}
            className="px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {r.close}
          </button>
          <button
            onClick={submit}
            disabled={!rating || feedback.trim().length < MIN_FEEDBACK_LENGTH || saving}
            className="rounded-xl bg-[#23404D] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#315A68] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? r.saving : r.submit}
          </button>
        </>
      )}
    >
      <div className="rounded-2xl bg-[var(--color-surface-muted)] p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-[var(--color-action-tint)] p-2.5 text-[var(--color-action-solid)]"><Sparkles className="h-5 w-5" /></div>
          <div>
            <p className="font-semibold text-[var(--color-text-primary)]">{r.calloutTitle}</p>
            <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">
              {actionCount > 0 ? r.calloutBodyWithCount.replace('{count}', String(actionCount)) : ''}
              {r.calloutBodyTail}
            </p>
          </div>
        </div>
      </div>
      <div>
        <p className="mb-2 text-sm font-semibold text-[var(--color-text-primary)]">{r.overallExperience}</p>
        <div className="flex gap-1" role="radiogroup" aria-label={r.overallExperienceAria}>
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setRating(value)}
              aria-label={r.starAriaLabel.replace('{value}', String(value))}
              aria-checked={rating === value}
              role="radio"
              className="rounded-xl p-2 transition hover:bg-[var(--color-surface-hover)]"
            >
              <Star className={`h-7 w-7 ${value <= rating ? 'fill-[#D39B3D] text-[#D39B3D]' : 'text-[var(--color-border-strong)]'}`} />
            </button>
          ))}
        </div>
      </div>
      <label className="block">
        <span className="mb-2 flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]"><MessageSquare className="h-4 w-4" /> {r.improveLabel} <span className="font-normal text-[var(--color-text-muted)]">{r.requiredTag}</span></span>
        <textarea
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          maxLength={2000}
          rows={4}
          placeholder={r.placeholder}
          className="w-full resize-none rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm text-[var(--color-text-primary)] outline-none transition placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-action-solid)]"
        />
        <div className={`mt-1 text-right text-xs ${feedback.trim().length < MIN_FEEDBACK_LENGTH ? 'text-amber-600' : 'text-emerald-600'}`}>
          {r.charCount.replace('{count}', String(feedback.trim().length))}
        </div>
      </label>
      {error && (
        <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </Dialog>
  );
};
