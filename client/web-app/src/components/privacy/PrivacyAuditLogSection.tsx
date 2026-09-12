import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { localizeAudit } from '../../i18n/privacyCatalog';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { History, Clock } from 'lucide-react';

export const PrivacyAuditLogSection: React.FC = () => {
  const { t, language } = useTranslation();
  const { auditLogs } = useDataPrivacyStore();

  return (
    <div className="bg-[var(--color-surface-muted)] p-6 rounded-2xl border border-[var(--color-border)] shadow-2xs space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--color-accent-soft)] flex items-center justify-center text-[var(--color-primary)]">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-extrabold text-[var(--color-text-primary)] font-heading">
              {t.dataPrivacy.auditLog.title}
            </h2>
            <p className="text-xs text-[var(--color-text-secondary)]">
              {t.dataPrivacy.auditLog.subtitle}
            </p>
          </div>
        </div>
      </div>

      {auditLogs.length === 0 ? (
        <p className="text-xs text-[var(--color-text-secondary)] py-4 text-center">
          {t.dataPrivacy.auditLog.empty}
        </p>
      ) : (
        <div className="space-y-2">
          {auditLogs.map((log) => {
            const copy = localizeAudit(log.id, language);
            const action = copy?.action || log.action;
            const result = copy?.result || log.result;
            const sourceName = copy?.sourceName || log.sourceName;
            const timestamp = copy?.timestamp || log.timestamp;

            return (
              <div
                key={log.id}
                className="p-3.5 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] flex items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-[var(--color-text-primary)]">{action}</span>
                    {sourceName && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
                        {sourceName}
                      </span>
                    )}
                  </div>
                  <p className="text-[var(--color-text-secondary)]">{result}</p>
                </div>

                <span className="text-[var(--color-text-secondary)] shrink-0 flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-[#5A6A85]" />
                  {timestamp}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
