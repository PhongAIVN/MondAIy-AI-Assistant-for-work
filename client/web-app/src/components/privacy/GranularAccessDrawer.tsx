import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import {
  localizeControl,
  localizeScope,
  localizeSourceName,
} from '../../i18n/privacyCatalog';
import { type ConnectedSourceAccess } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import {
  X,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Info,
  Lock,
} from 'lucide-react';

interface GranularAccessDrawerProps {
  source: ConnectedSourceAccess | null;
  isOpen: boolean;
  onClose: () => void;
}

export const GranularAccessDrawer: React.FC<GranularAccessDrawerProps> = ({
  source,
  isOpen,
  onClose,
}) => {
  const { t, language } = useTranslation();
  const { updateSourceGranularControl } = useDataPrivacyStore();

  if (!isOpen || !source) return null;

  const sourceTitle = localizeSourceName(source.id, source.name, language);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="w-full max-w-lg bg-white dark:bg-[#122038] h-full shadow-2xl flex flex-col border-l border-[#E4EAF6] dark:border-[#1E2E4A] animate-in slide-in-from-right duration-300"
        role="dialog"
        aria-modal="true"
      >
        <div className="p-6 border-b border-[#E4EAF6] dark:border-[#1E2E4A] flex items-center justify-between bg-[#EDF2FB] dark:bg-[#0F1F38]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#E1EBFA] dark:bg-[#1A2A42] flex items-center justify-center text-[#0F1F38] dark:text-[#7EB0E8]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-extrabold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
                {t.dataPrivacy.granularDrawer.title.replace('{source}', sourceTitle)}
              </h2>
              <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC] mt-0.5">
                {source.accountEmailOrUser}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-[#5A6A85] dark:text-[#AEB9CC] hover:bg-[#E2E8F0] dark:hover:bg-[#1A2A42] rounded-xl transition-colors"
            aria-label="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="p-4 bg-[#E1EBFA] dark:bg-[#0F1F38] border border-[#D5DDEB] dark:border-[#1E2E4A] rounded-2xl flex items-start gap-3">
            <Info className="w-5 h-5 text-[#2563A6] dark:text-[#7EB0E8] shrink-0 mt-0.5" />
            <p className="text-xs text-[#0F1F38] dark:text-[#E1EBFA] font-medium leading-relaxed">
              {t.dataPrivacy.granularDrawer.futureImpactNote}
            </p>
          </div>

          <div>
            <h3 className="text-xs font-medium text-[#0F1F38] dark:text-[#E2E8F0] mb-3">
              {t.dataPrivacy.granularDrawer.configTitle}
            </h3>
            <div className="space-y-3">
              {source.permissions.granularControls.map((ctrl) => {
                const copy = localizeControl(ctrl.id, language);
                return (
                  <div
                    key={ctrl.id}
                    className="p-4 rounded-xl border border-[#E4EAF6] dark:border-[#1E2E4A] bg-white dark:bg-[#122038] flex items-center justify-between gap-4"
                  >
                    <div className="space-y-1 pr-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-[#0F1F38] dark:text-[#E2E8F0]">
                          {copy.name}
                        </span>
                        {ctrl.alwaysUnavailable && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-md bg-[#EBEFF8] dark:bg-[#0F1F38] text-[#5A6A85] dark:text-[#AEB9CC] border border-[#E4EAF6] dark:border-[#1E2E4A]">
                            <Lock className="w-3 h-3 text-[#A03D3D]" />
                            {t.dataPrivacy.granularDrawer.alwaysUnavailable}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[#5A6A85] dark:text-[#AEB9CC]">{copy.description}</p>
                    </div>

                    <label className="relative inline-flex items-center cursor-pointer shrink-0">
                      <input
                        type="checkbox"
                        disabled={ctrl.alwaysUnavailable}
                        checked={ctrl.enabled && !ctrl.alwaysUnavailable}
                        onChange={(e) =>
                          updateSourceGranularControl(source.id, ctrl.id, e.target.checked)
                        }
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-slate-200 dark:bg-[#1A2A42] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#0F1F38] dark:peer-checked:bg-[#2563A6] disabled:opacity-50 disabled:cursor-not-allowed"></div>
                    </label>
                  </div>
                );
              })}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-medium text-[#2A6B4F] dark:text-[#8CC3A2] mb-3 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              {t.dataPrivacy.granularDrawer.canAccess}
            </h3>
            <ul className="space-y-2 bg-[#DFF0E6] dark:bg-[#0F1F38] p-4 rounded-xl border border-[#C4DDCB] dark:border-[#1E2E4A]">
              {source.permissions.canAccess.map((item) => (
                <li
                  key={item}
                  className="text-xs text-[#0F1F38] dark:text-[#DFF0E6] font-medium flex items-center gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#2A6B4F] shrink-0" />
                  {localizeScope(item, language)}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-medium text-[#A03D3D] dark:text-[#DC9A91] mb-3 flex items-center gap-2">
              <XCircle className="w-4 h-4" />
              {t.dataPrivacy.granularDrawer.cannotAccess}
            </h3>
            <ul className="space-y-2 bg-[#F9DEDE] dark:bg-[#0F1F38] p-4 rounded-xl border border-[#F0D8D3] dark:border-[#1E2E4A]">
              {source.permissions.cannotAccess.map((item) => (
                <li
                  key={item}
                  className="text-xs text-[#0F1F38] dark:text-[#DC9A91] font-medium flex items-center gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[#A03D3D] shrink-0" />
                  {localizeScope(item, language)}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="p-4 border-t border-[#E4EAF6] dark:border-[#1E2E4A] bg-[#EDF2FB] dark:bg-[#0F1F38] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-[#0F1F38] dark:bg-[#2563A6] text-white rounded-xl font-bold text-xs shadow-2xs hover:bg-[#1E4E85] transition-colors"
          >
            {t.dataPrivacy.granularDrawer.done}
          </button>
        </div>
      </div>
    </div>
  );
};
