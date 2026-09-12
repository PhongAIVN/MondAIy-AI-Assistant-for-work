import React, { useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { Dialog } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { ConfidenceBadge } from '../ui/Badge';
import { AlertTriangle, Copy, Check, ShieldAlert } from 'lucide-react';
import { resolveBrandIcon, VLearnIcon } from '../ui/BrandIcons';

export const ConflictCompareModal: React.FC = () => {
  const { activeModal, modalData, closeModal, addToast } = useAppStore();
  const [copied, setCopied] = useState(false);

  if (activeModal !== 'conflict_compare' || !modalData) return null;

  const item = modalData;
  const conflict = item.conflictDetails || {
    sourceA: {
      platform: 'Discord',
      location: '#announcements',
      value: 'July 29 · 11:59 PM',
      timestamp: 'July 27 · 9:15 AM',
      content:
        '"We are extending the Proposal submission deadline to July 29 at 11:59 PM UTC."',
    },
    sourceB: {
      platform: 'Learning Platform',
      location: 'Canvas Assignment #1',
      value: 'July 28 · 11:59 PM',
      timestamp: 'July 20 · 2:00 PM',
      content:
        '"Due Date: July 28, 2026, 23:59:00 EST. Submissions closed after deadline."',
    },
    mentorVerificationDraft:
      'Hi Dr. Chen, I noticed that Discord #announcements states the milestone deadline was extended to July 29 at 11:59 PM, but Canvas still displays July 28 at 11:59 PM. Could you please clarify which deadline is authoritative or if Canvas will be updated?',
  };

  const platformIcon = (platform: string) =>
    resolveBrandIcon(platform, 'w-4 h-4') ?? <VLearnIcon className="w-4 h-4" />;

  const handleCopyDraft = () => {
    navigator.clipboard.writeText(conflict.mentorVerificationDraft);
    setCopied(true);
    addToast({
      type: 'success',
      title: 'Draft Copied',
      message: 'Verification question copied to clipboard. Ready to paste into Email or Discord.',
    });
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog
      isOpen={activeModal === 'conflict_compare'}
      onClose={closeModal}
      title="Source Conflict Resolution"
      description="Connected sources disagree on program information. mondaiy will not pick an arbitrary winner without mentor verification."
      maxWidth="xl"
      footer={
        <div className="flex items-center justify-between w-full">
          <span className="text-[11px] text-[var(--color-text-secondary)] flex items-center gap-1">
            <ShieldAlert className="w-3.5 h-3.5 text-[var(--color-warning)]" /> User confirmation required to resolve source conflict
          </span>
          <Button variant="outline" size="sm" onClick={closeModal}>
            Close Comparison
          </Button>
        </div>
      }
    >
      <div className="space-y-4 text-xs">
        <div className="p-3 bg-[var(--color-warning-soft)] border border-[var(--color-warning)]/35 rounded-xl flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-[var(--color-warning)] font-bold">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>Discrepancy: Milestone 1 Submission Deadline</span>
          </div>
          <ConfidenceBadge level="ask_mentor" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-xl space-y-2 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="font-extrabold text-[var(--color-text-primary)] text-sm flex items-center gap-1.5 font-heading">
                {platformIcon(conflict.sourceA.platform)} {conflict.sourceA.platform}
              </span>
              <span className="text-[10px] bg-[var(--color-success-soft)] text-[var(--color-success)] font-bold px-2 py-0.5 rounded-full">
                Most Recent
              </span>
            </div>
            <p className="text-[11px] text-[var(--color-text-secondary)]">
              Channel: <strong>{conflict.sourceA.location}</strong>
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)]">Timestamp: {conflict.sourceA.timestamp}</p>

            <div className="pt-2 border-t border-[var(--color-border)]">
              <span className="text-[10px] text-[var(--color-text-muted)] font-medium block">Stated Deadline</span>
              <p className="text-sm font-extrabold text-[var(--color-success)]">{conflict.sourceA.value}</p>
            </div>

            <div className="p-2.5 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg text-[11px] text-[var(--color-text-secondary)] italic">
              {conflict.sourceA.content}
            </div>
          </div>

          <div className="p-4 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-xl space-y-2 shadow-xs">
            <div className="flex items-center justify-between">
              <span className="font-extrabold text-[var(--color-text-primary)] text-sm flex items-center gap-1.5 font-heading">
                {platformIcon(conflict.sourceB.platform)} {conflict.sourceB.platform}
              </span>
              <span className="text-[10px] bg-[#F9DEDE] text-[var(--color-danger)] font-bold px-2 py-0.5 rounded-full">
                Older Record
              </span>
            </div>
            <p className="text-[11px] text-[var(--color-text-secondary)]">
              Portal: <strong>{conflict.sourceB.location}</strong>
            </p>
            <p className="text-[11px] text-[var(--color-text-muted)]">Timestamp: {conflict.sourceB.timestamp}</p>

            <div className="pt-2 border-t border-[var(--color-border)]">
              <span className="text-[10px] text-[var(--color-text-muted)] font-medium block">Stated Deadline</span>
              <p className="text-sm font-extrabold text-[var(--color-danger)]">{conflict.sourceB.value}</p>
            </div>

            <div className="p-2.5 bg-[var(--color-accent-soft)] border border-[var(--color-border)] rounded-lg text-[11px] text-[var(--color-text-secondary)] italic">
              {conflict.sourceB.content}
            </div>
          </div>
        </div>

        <div className="p-4 bg-[var(--color-accent-soft)] border border-[var(--color-border-subtle)] rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-bold text-[var(--color-text-primary)] text-xs">
              mondaiy Drafted Verification Message
            </span>
            <Button
              variant="outline"
              size="sm"
              icon={copied ? <Check className="w-3.5 h-3.5 text-[var(--color-success)]" /> : <Copy className="w-3.5 h-3.5" />}
              onClick={handleCopyDraft}
            >
              {copied ? 'Copied!' : 'Copy Draft'}
            </Button>
          </div>

          <div className="p-3 bg-[var(--color-surface-muted)] border border-[var(--color-border)] rounded-lg text-xs text-[var(--color-text-primary)] leading-relaxed font-sans">
            "{conflict.mentorVerificationDraft}"
          </div>

          <p className="text-[11px] text-[var(--color-text-secondary)]">
            💡 <strong>mondaiy Rule:</strong> mondaiy will not send emails or messages automatically. Copy this message to send to your mentor or program TA directly.
          </p>
        </div>
      </div>
    </Dialog>
  );
};
