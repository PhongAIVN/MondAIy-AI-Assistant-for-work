import React, { useState, useMemo } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { type CapturedRecord } from '../../types/dataPrivacy';
import { useDataPrivacyStore } from '../../stores/useDataPrivacyStore';
import { CapturedRecordDrawer } from './CapturedRecordDrawer';
import { RedactionEditorModal } from './RedactionEditorModal';
import { BulkDeleteModal } from './BulkDeleteModal';
import {
  Search,
  Trash2,
  Scissors,
  Eye,
  FileText,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  HelpCircle
  } from 'lucide-react';

export const DataActivityTab: React.FC = () => {
  const { t, language } = useTranslation();
  const { records, deleteCapturedRecord } = useDataPrivacyStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSourceFilter, setSelectedSourceFilter] = useState<string>('all');
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>('all');
  const [selectedConfidenceFilter] = useState<string>('all');

  const [selectedRecordIds, setSelectedRecordIds] = useState<string[]>([]);
  const [activeDrawerRecord, setActiveDrawerRecord] = useState<CapturedRecord | null>(null);
  const [activeRedactRecord, setActiveRedactRecord] = useState<CapturedRecord | null>(null);
  const [activeBulkDeleteModal, setActiveBulkDeleteModal] = useState(false);

  const filteredRecords = useMemo(() => {
    return records.filter((rec) => {
      const matchesSearch =
        rec.contentPreview.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rec.extractedInformation.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rec.sourceName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rec.sourceLocation.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesSource =
        selectedSourceFilter === 'all' || rec.sourceId === selectedSourceFilter;

      const matchesStatus =
        selectedStatusFilter === 'all' || rec.processingStatus === selectedStatusFilter;

      const matchesConfidence =
        selectedConfidenceFilter === 'all' || rec.confidence === selectedConfidenceFilter;

      return matchesSearch && matchesSource && matchesStatus && matchesConfidence;
    });
  }, [records, searchQuery, selectedSourceFilter, selectedStatusFilter, selectedConfidenceFilter]);

  const toggleSelectRecord = (id: string) => {
    if (selectedRecordIds.includes(id)) {
      setSelectedRecordIds(selectedRecordIds.filter((r) => r !== id));
    } else {
      setSelectedRecordIds([...selectedRecordIds, id]);
    }
  };

  const getConfidenceBadge = (confidence: string) => {
    switch (confidence) {
      case 'Certain':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DFF0E6] text-[#2A6B4F] dark:bg-[#0F1F38] dark:text-[#8CC3A2]">
            <CheckCircle2 className="w-3 h-3" />
            {confidence}
          </span>
        );
      case 'Possible':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#F6EEDA] text-[#8A5712] dark:bg-[#0F1F38] dark:text-[#D7B270]">
            <AlertCircle className="w-3 h-3" />
            {confidence}
          </span>
        );
      case 'Ask Mentor':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#F9DEDE] text-[#A03D3D] dark:bg-[#0F1F38] dark:text-[#DC9A91]">
            <HelpCircle className="w-3 h-3" />
            {confidence}
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] font-heading">
          {t.dataPrivacy.activity.title}
        </h2>
        <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
          {t.dataPrivacy.activity.subtitle}
        </p>
      </div>

      {/* Filter Bar */}
      <div className="bg-[var(--color-surface-muted)] p-4 rounded-2xl border border-[var(--color-border)] shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row items-center gap-3">
          {/* Search Box */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t.dataPrivacy.activity.searchPlaceholder}
              className="w-full pl-9 pr-4 py-2 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[#0F1F38]"
            />
          </div>

          {/* Select Filters */}
          <div className="flex items-center gap-2 w-full sm:w-auto overflow-x-auto">
            {/* Source filter */}
            <select
              value={selectedSourceFilter}
              onChange={(e) => setSelectedSourceFilter(e.target.value)}
              className="p-2 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none shrink-0"
            >
              <option value="all">{t.dataPrivacy.activity.allSources}</option>
              <option value="src-discord">Discord</option>
              <option value="src-canvas">Canvas LMS</option>
              <option value="src-email">Gmail</option>
              <option value="src-calendar">Google Drive & Calendar</option>
            </select>

            {/* Status filter */}
            <select
              value={selectedStatusFilter}
              onChange={(e) => setSelectedStatusFilter(e.target.value)}
              className="p-2 bg-[var(--color-accent-soft)] rounded-xl border border-[var(--color-border)] text-xs font-semibold text-[var(--color-text-primary)] focus:outline-none shrink-0"
            >
              <option value="all">{t.dataPrivacy.activity.allStatuses}</option>
              <option value="used_in_briefing">{t.dataPrivacy.activity.usedInBriefing}</option>
              <option value="saved_as_memory">{t.dataPrivacy.activity.savedAsMemory}</option>
              <option value="pending_review">{t.dataPrivacy.activity.pendingReview}</option>
            </select>
          </div>
        </div>

        {/* Bulk Action Bar (when selected) */}
        {selectedRecordIds.length > 0 && (
          <div className="p-3 bg-[#E1EBFA] dark:bg-[#0F1F38] border border-[var(--color-border)] rounded-xl flex items-center justify-between gap-3 animate-in fade-in">
            <span className="text-xs font-bold text-[var(--color-text-primary)]">
              {selectedRecordIds.length} {language === 'vi' ? 'mục đã được chọn' : 'items selected'}
            </span>
            <button
              onClick={() => setActiveBulkDeleteModal(true)}
              className="px-3.5 py-1.5 bg-[#A03D3D] text-white rounded-lg text-xs font-bold hover:bg-[#8A3434] transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              {t.dataPrivacy.activity.bulkDelete.replace('{count}', String(selectedRecordIds.length))}
            </button>
          </div>
        )}
      </div>

      {/* Record List */}
      {filteredRecords.length === 0 ? (
        <div className="bg-[var(--color-surface-muted)] p-12 rounded-2xl border border-[var(--color-border)] text-center space-y-3">
          <FileText className="w-10 h-10 text-[var(--color-text-secondary)] mx-auto" />
          <h3 className="text-sm font-bold text-[var(--color-text-primary)]">
            {t.dataPrivacy.emptyStates.noDataTitle}
          </h3>
          <p className="text-xs text-[var(--color-text-secondary)] max-w-sm mx-auto">
            {t.dataPrivacy.emptyStates.noDataDesc}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredRecords.map((rec) => (
            <div
              key={rec.id}
              className={`bg-[var(--color-surface-muted)] p-5 rounded-2xl border transition-all space-y-3 ${
                selectedRecordIds.includes(rec.id)
                  ? 'border-[#0F1F38] dark:border-[#2563A6] bg-[#E1EBFA]/30 dark:bg-[#0F1F38]'
                  : 'border-[var(--color-border)] hover:border-[#0F1F38]/30'
              }`}
            >
              {/* Top Row: Checkbox, Source, Location, Timestamps, Confidence */}
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedRecordIds.includes(rec.id)}
                    onChange={() => toggleSelectRecord(rec.id)}
                    className="w-4 h-4 rounded border-[#E4EAF6] text-[#0F1F38] focus:ring-0 cursor-pointer"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[var(--color-text-primary)]">
                        {rec.sourceName}
                      </span>
                      <span className="text-xs text-[var(--color-text-secondary)]">
                        · {rec.sourceLocation}
                      </span>
                      {getConfidenceBadge(rec.confidence)}
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-[var(--color-text-secondary)] mt-0.5">
                      <span>{rec.originalTimestamp}</span>
                      <span>·</span>
                      <span>
                        {language === 'vi' ? 'Thu thập:' : 'Captured:'} {rec.capturedAt}
                      </span>
                    </div>
                  </div>
                </div>

                <span
                  className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border shrink-0 ${
                    rec.processingStatus === 'used_in_briefing'
                      ? 'bg-[#E1EBFA] text-[#2563A6] border-[#D5DDEB] dark:bg-[#0F1F38] dark:border-[#1E2E4A] text-[var(--color-primary)]'
                      : rec.processingStatus === 'saved_as_memory'
                      ? 'bg-[#DFF0E6] text-[#2A6B4F] border-[#C4DDCB] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#8CC3A2]'
                      : 'bg-[#F6EEDA] text-[#8A5712] border-[#D7B270] dark:bg-[#0F1F38] dark:border-[#1E2E4A] dark:text-[#D7B270]'
                  }`}
                >
                  {rec.processingStatus.replace(/_/g, ' ')}
                </span>
              </div>

              {/* Preview & Extracted info */}
              <div className="space-y-1.5 bg-[var(--color-accent-soft)] p-3.5 rounded-xl border border-[var(--color-border)]">
                <p className="text-xs text-[var(--color-text-primary)] font-medium leading-relaxed">
                  "{rec.contentPreview}"
                </p>
                <p className="text-[11px] font-bold text-[#2563A6] text-[var(--color-primary)] flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5" />
                  Extracted: {rec.extractedInformation}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-1 text-xs">
                <button
                  onClick={() => setActiveDrawerRecord(rec)}
                  className="text-[#2563A6] text-[var(--color-primary)] font-bold hover:underline flex items-center gap-1.5"
                >
                  <Eye className="w-3.5 h-3.5" />
                  {t.dataPrivacy.activity.viewEvidence}
                </button>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setActiveRedactRecord(rec)}
                    className="px-2.5 py-1 bg-[var(--color-surface-muted)] border border-[var(--color-border)] text-[var(--color-text-primary)] rounded-lg font-semibold text-[11px] hover:bg-[var(--color-surface-hover)] transition-colors flex items-center gap-1"
                  >
                    <Scissors className="w-3 h-3 text-[#2563A6]" />
                    {t.dataPrivacy.activity.editRetainedContent}
                  </button>

                  <button
                    onClick={() => deleteCapturedRecord(rec.id)}
                    className="p-1 text-[#A03D3D] dark:text-[#DC9A91] hover:bg-[#F9DEDE] rounded-lg transition-colors"
                    title={t.dataPrivacy.activity.deleteRecord}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Drawers & Modals */}
      <CapturedRecordDrawer
        record={activeDrawerRecord}
        isOpen={Boolean(activeDrawerRecord)}
        onClose={() => setActiveDrawerRecord(null)}
        onOpenRedactModal={(rec) => setActiveRedactRecord(rec)}
        onDeleteRecord={(id) => deleteCapturedRecord(id)}
      />

      <RedactionEditorModal
        record={activeRedactRecord}
        isOpen={Boolean(activeRedactRecord)}
        onClose={() => setActiveRedactRecord(null)}
      />

      <BulkDeleteModal
        selectedRecordIds={selectedRecordIds}
        isOpen={activeBulkDeleteModal}
        onClose={() => {
          setActiveBulkDeleteModal(false);
          setSelectedRecordIds([]);
        }}
      />
    </div>
  );
};
