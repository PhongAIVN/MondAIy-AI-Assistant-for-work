import React from 'react';
import { Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { ConfidenceBadge } from '../components/ui/Badge';
import { useTranslation } from '../i18n/useTranslation';
import { Activity, ShieldCheck, CheckCircle2, Layers } from 'lucide-react';
import { type ActivityLog } from '../types/activity';

export const ActivityPage: React.FC = () => {
  const { t } = useTranslation();

  const auditTrail: ActivityLog[] = [
    {
      id: 'act-1',
      type: 'update_detected',
      title: 'Milestone 2 Proposal Extension Detected',
      description: 'mondaiy identified 24h deadline extension from Discord #announcements.',
      timestamp: 'July 27 · 9:15 AM',
      source: { platform: 'Discord', location: '#announcements' },
      confidence: 'certain',
      userConfirmed: true,
    },
    {
      id: 'act-2',
      type: 'conflict_identified',
      title: 'Source Conflict Flagged',
      description: 'Discord states July 29 deadline; Canvas displays July 28. Marked as "Ask your mentor".',
      timestamp: 'July 28 · 10:15 AM',
      source: { platform: 'Discord vs Canvas', location: '#announcements / Canvas LMS' },
      confidence: 'ask_mentor',
      userConfirmed: false,
    },
    {
      id: 'act-3',
      type: 'task_created',
      title: 'Draft Task Suggestion Generated',
      description: 'Generated "Prepare presentation outline" draft from Discord #team-chat.',
      timestamp: 'July 28 · 4:18 PM',
      source: { platform: 'Discord', location: '#team-chat' },
      confidence: 'possible',
      userConfirmed: false,
    },
    {
      id: 'act-4',
      type: 'feedback_submitted',
      title: 'User Briefing Rating Logged',
      description: 'User marked Daily Briefing items as "Relevant".',
      timestamp: 'Today · 8:10 AM',
      source: { platform: 'Daily Briefing UI', location: 'User Session' },
      confidence: 'certain',
      userConfirmed: true,
    },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <Activity className="w-4 h-4" /> {t.activityPage.transparencyLog}
            <span className="text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border border-[var(--color-border)] text-[var(--color-text-muted)]">
              {t.activityPage.demoBadge}
            </span>
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            {t.activityPage.title}
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">
            {t.activityPage.subtitle}
          </p>
          <p className="text-xs text-[var(--color-text-muted)] mt-2">
            {t.activityPage.privacyAuditNote}{' '}
            <Link
              to="/data-privacy"
              className="text-[var(--color-primary)] font-semibold hover:underline"
            >
              {t.activityPage.privacyAuditLink}
            </Link>
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs bg-[var(--color-accent-soft)] border border-[var(--color-border-subtle)] p-2.5 rounded-xl text-[var(--color-primary)] font-bold shrink-0">
          <ShieldCheck className="w-4 h-4 text-[var(--color-success)]" /> {t.activityPage.traceableHistory}
        </div>
      </div>

      <Card className="p-6 space-y-6">
        <div className="relative border-l-2 border-[var(--color-border)] ml-3 pl-6 space-y-6">
          {auditTrail.map((log) => (
            <div key={log.id} className="relative group">
              <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-[var(--color-app-bg)] border-2 border-[var(--color-primary)] group-hover:scale-125 transition-transform" />

              <div className="space-y-1.5">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-[var(--color-text-primary)] font-heading">{log.title}</h3>
                    {log.confidence && <ConfidenceBadge level={log.confidence} />}
                  </div>
                  <span className="text-xs text-[var(--color-text-muted)] font-medium">{log.timestamp}</span>
                </div>

                <p className="text-xs text-[var(--color-text-secondary)]">{log.description}</p>

                <div className="flex items-center gap-4 text-[11px] pt-1 flex-wrap">
                  <span className="text-[var(--color-text-primary)] font-bold flex items-center gap-1">
                    <Layers className="w-3.5 h-3.5 text-[var(--color-primary)]" /> Source: {log.source.platform} ({log.source.location})
                  </span>
                  <span className={`font-semibold flex items-center gap-1 ${log.userConfirmed ? 'text-[#2A6B4F]' : 'text-[#8A5712]'}`}>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {log.userConfirmed ? t.activityPage.userConfirmed : t.activityPage.pendingReview}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
