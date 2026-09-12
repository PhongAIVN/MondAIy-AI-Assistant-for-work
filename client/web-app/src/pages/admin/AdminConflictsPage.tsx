import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import { AdminMockBanner } from '../../components/admin/AdminStates';

type ConflictItem = {
  id: string;
  title: string;
  program: string;
  sourceA: string;
  valueA: string;
  sourceB: string;
  valueB: string;
  detectedAt: string;
  status: 'unresolved' | 'assigned' | 'resolved';
  assignee?: string;
  resolutionReason?: string;
};

const INITIAL_CONFLICTS: ConflictItem[] = [
  {
    id: 'cnf-101',
    title: 'Milestone 2 Proposal Deadline Discrepancy',
    program: 'AI Product Development',
    sourceA: 'Discord #announcements (Dr. Chen, 09:30 AM)',
    valueA: 'July 29, 2026 at 5:00 PM EST',
    sourceB: 'Canvas LMS Assignment Module',
    valueB: 'August 01, 2026 at 11:59 PM EST',
    detectedAt: '2 hours ago',
    status: 'unresolved',
  },
  {
    id: 'cnf-102',
    title: 'Thursday Mentorship Office Hours Shift',
    program: 'AI Product Development',
    sourceA: 'Program Calendar Event',
    valueA: 'Thursday 3:00 PM EST',
    sourceB: 'Mentor Email Digest (Dr. Chen)',
    valueB: 'Thursday 4:30 PM EST',
    detectedAt: 'Yesterday',
    status: 'assigned',
    assignee: 'Dr. Chen',
  },
  {
    id: 'cnf-103',
    title: 'Required Deliverable Format Specification',
    program: 'Scholar Research Incubator',
    sourceA: 'Canvas Syllabus PDF',
    valueA: 'Slide Deck PDF only',
    sourceB: 'Discord #general chat',
    valueB: 'Interactive Loom Video link',
    detectedAt: '3 days ago',
    status: 'resolved',
    assignee: 'Program Admin',
    resolutionReason: 'Dr. Chen verified that Slide Deck PDF is mandatory while video demo link is optional bonus.',
  },
];

export const AdminConflictsPage: React.FC = () => {
  const { t } = useTranslation();
  const [conflicts, setConflicts] = useState<ConflictItem[]>(INITIAL_CONFLICTS);
  const [selectedForResolve, setSelectedForResolve] = useState<ConflictItem | null>(null);
  const [reason, setReason] = useState('');

  const handleResolveClick = (c: ConflictItem) => {
    setSelectedForResolve(c);
    setReason('');
  };

  const confirmResolution = () => {
    if (selectedForResolve && reason.trim()) {
      setConflicts(
        conflicts.map((c) =>
          c.id === selectedForResolve.id
            ? { ...c, status: 'resolved', resolutionReason: reason }
            : c
        )
      );
      setSelectedForResolve(null);
    }
  };

  return (
    <div className="space-y-6">
      <AdminMockBanner lyDo="Backend chưa có model Conflict; số mâu thuẫn thật hiện chỉ suy ra từ việc có thời gian chưa rõ (xem trang Tổng quan)." />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.conflicts}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Review, assign, and transparently resolve discrepancies detected between connected sources.
          </p>
        </div>
      </div>

      {/* Conflicts List */}
      <div className="space-y-4">
        {conflicts.map((c) => (
          <div
            key={c.id}
            className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4 shadow-xs"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle
                  className={`w-4 h-4 ${
                    c.status === 'resolved' ? 'text-emerald-500' : 'text-amber-500'
                  }`}
                />
                <h3 className="font-bold text-sm text-[#0F1F38] dark:text-white">{c.title}</h3>
              </div>

              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  c.status === 'resolved'
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300'
                    : c.status === 'assigned'
                    ? 'bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300'
                    : 'bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300'
                }`}
              >
                {c.status}
              </span>
            </div>

            {/* Source Comparison Cards */}
            <div className="grid md:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 space-y-1">
                <span className="text-[10px] font-medium text-rose-700 dark:text-rose-400 block">
                  Source A: {c.sourceA}
                </span>
                <p className="font-semibold text-[#0F1F38] dark:text-white">{c.valueA}</p>
              </div>

              <div className="p-3 rounded-xl bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 space-y-1">
                <span className="text-[10px] font-medium text-blue-700 dark:text-blue-400 block">
                  Source B: {c.sourceB}
                </span>
                <p className="font-semibold text-[#0F1F38] dark:text-white">{c.valueB}</p>
              </div>
            </div>

            {c.resolutionReason && (
              <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-xs text-emerald-900 dark:text-emerald-200 space-y-1">
                <span className="font-bold block">Resolution Reason (Verified by Admin):</span>
                <p>{c.resolutionReason}</p>
              </div>
            )}

            <div className="flex items-center justify-between pt-2 border-t border-[#E1EBFA] dark:border-[#1A2A42] text-xs">
              <span className="text-[11px] text-[#5A6A85]">Detected: {c.detectedAt} · Program: {c.program}</span>

              {c.status !== 'resolved' && (
                <Button
                  size="xs"
                  onClick={() => handleResolveClick(c)}
                  className="bg-[#2563A6] text-white font-bold"
                >
                  Resolve Conflict
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Resolution Modal */}
      {selectedForResolve && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-white dark:bg-[#122038] rounded-2xl border border-[#D5DDEB] dark:border-[#1A2A42] p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-[#0F1F38] dark:text-white">
              Resolve Source Conflict
            </h3>

            <p className="text-xs text-[#5A6A85] leading-relaxed">
              No conflict is silently resolved. You must provide a verified resolution reason explaining which source statement prevails and why.
            </p>

            <div>
              <label className="block text-xs font-semibold text-[#0F1F38] dark:text-slate-300 mb-1.5">
                Resolution Reason / Mentor Verification Note
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                placeholder="e.g. Verified with Dr. Chen via email announcement that..."
                className="w-full p-3 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6]"
                required
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setSelectedForResolve(null)}>
                {t.actions.cancel}
              </Button>
              <Button
                onClick={confirmResolution}
                disabled={!reason.trim()}
                className="bg-[#2563A6] text-white font-bold"
              >
                Save & Resolve Conflict
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
