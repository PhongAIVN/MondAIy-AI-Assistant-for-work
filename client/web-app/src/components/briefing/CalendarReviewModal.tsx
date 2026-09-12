import React, { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { Dialog } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { ConfidenceBadge } from '../ui/Badge';
import { SourceReference } from './SourceReference';
import { Calendar, Clock, ShieldCheck, CheckCircle2 } from 'lucide-react';

export const CalendarReviewModal: React.FC = () => {
  const { activeModal, modalData, closeModal, addToast } = useAppStore();
  const [eventDate, setEventDate] = useState('2026-07-30');
  const [eventTime, setEventTime] = useState('14:00');
  const [personalNote, setPersonalNote] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);

  if (activeModal !== 'calendar_event' || !modalData) return null;

  const event = modalData;

  const handleConfirmAndSync = () => {
    setIsSyncing(true);
    setTimeout(() => {
      setIsSyncing(false);
      closeModal();
      
      addToast({
        type: 'success',
        title: 'Calendar Event Synced',
        message: `"${event.title || 'Program Event'}" added to your personal calendar.`,
      });
    }, 450);
  };

  return (
    <Dialog
      isOpen={activeModal === 'calendar_event'}
      onClose={closeModal}
      title="Calendar Suggestion Review"
      description="Review event details and source evidence before explicitly adding to your personal calendar."
      maxWidth="lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <p className="text-[11px] text-[var(--color-text-secondary)] italic flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-[var(--color-success)]" /> Mandatory user confirmation required
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={closeModal}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<CheckCircle2 className="w-4 h-4" />}
              onClick={handleConfirmAndSync}
              disabled={isSyncing}
            >
              {isSyncing ? 'Syncing...' : 'Confirm & Add to Calendar'}
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        {/* Header Badge & Title */}
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2 py-0.5 bg-[var(--color-accent-soft)] text-[var(--color-primary)] text-[10px] font-medium rounded-md">
              {event.type || 'Program Deadline'}
            </span>
            <ConfidenceBadge level={event.confidence || 'certain'} />
          </div>

          <h4 className="text-base font-extrabold text-[var(--color-text-primary)] font-heading">
            {event.title}
          </h4>
          <p className="text-xs text-[var(--color-text-secondary)]">
            {event.summary || event.description || 'AI-suggested schedule milestone detected from program announcements.'}
          </p>
        </div>

        {/* User Control Safeguard Notice */}
        <div className="p-3 bg-[var(--color-success-soft)] border border-[var(--color-success)]/30 rounded-xl text-xs text-[var(--color-success)] font-semibold flex items-start gap-2">
          <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <span>No automatic creation: </span>
            <span className="font-normal text-[var(--color-text-primary)]">
              Mondaiy will not insert events into Program Calendar or iCal without your explicit click on "Confirm & Add to Calendar".
            </span>
          </div>
        </div>

        {/* Editable Schedule Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-xl">
          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-primary)] mb-1 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-[var(--color-primary)]" /> Event Date
            </label>
            <input
              type="date"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="w-full p-2 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-[var(--color-text-primary)] mb-1 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-[var(--color-primary)]" /> Event Time
            </label>
            <input
              type="time"
              value={eventTime}
              onChange={(e) => setEventTime(e.target.value)}
              className="w-full p-2 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>
        </div>

        {/* Personal Preparation Notes */}
        <div>
          <label className="block text-[11px] font-bold text-[var(--color-text-primary)] mb-1">
            Personal Event Notes or Reminder Lead Time
          </label>
          <input
            type="text"
            value={personalNote}
            onChange={(e) => setPersonalNote(e.target.value)}
            placeholder="e.g. Set 30-minute reminder before mentor check-in..."
            className="w-full p-2.5 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:bg-[var(--color-surface-muted)]"
          />
        </div>

        {/* Traceable Source Evidence */}
        <div className="pt-2 border-t border-[var(--color-border)]">
          <span className="text-xs font-bold text-[var(--color-text-primary)] block mb-1">Source Evidence</span>
          <SourceReference source={event.source || { platform: 'Program Calendar', location: 'Official Feed', timestamp: 'Today' }} />
        </div>
      </div>
    </Dialog>
  );
};
