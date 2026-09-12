import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { useAuthStore } from '../../stores/useAuthStore';
import {
  listLongTermMemory,
  confirmLongTermMemory,
  rejectLongTermMemory,
  deleteLongTermMemory,
  editLongTermMemory,
  clearLongTermMemory,
  type MemoryItem,
} from '../../lib/memoryApi';
import { ApiError } from '../../lib/apiClient';
import { MemoryDetailDrawer } from './MemoryDetailDrawer';
import { AdaptiveLearningSection } from './AdaptiveLearningSection';
import { MemoryGraphView } from './MemoryGraphView';
import { MemoryConflictProposal } from './MemoryConflictProposal';
import {
  Brain,
  CheckCircle2,
  XCircle,
  Clock,
  Trash2,
  Eye,
  Sparkles,
  Loader2,
  RotateCcw,
} from 'lucide-react';

// Predicate là định danh tiếng Anh nội bộ (vd. "response_style"), không có
// câu tự nhiên nào lưu sẵn ở backend — hiển thị predicate + value thật, không
// bịa câu văn hoa mỹ như bản mock trước đó.
function memoryLabel(memory: MemoryItem): string {
  const readablePredicate = memory.predicate.replace(/_/g, ' ');
  const value = typeof memory.value === 'string' ? memory.value : JSON.stringify(memory.value);
  return `${readablePredicate}: ${value}`;
}

export const MemoryInspectorTab: React.FC = () => {
  const { t, language } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);

  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [activeDetailMemory, setActiveDetailMemory] = useState<MemoryItem | null>(null);

  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    try {
      const { memories: rows } = await listLongTermMemory(accessToken);
      setMemories(rows);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : (language === 'vi' ? 'Không tải được bộ nhớ.' : 'Could not load memory.'));
    } finally {
      setLoading(false);
    }
  }, [accessToken, language]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const withBusy = async (key: string, action: () => Promise<unknown>) => {
    setBusyKey(key);
    setActionError(null);
    try {
      await action();
      await reload();
      setActiveDetailMemory(null);
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.message
          : language === 'vi'
            ? 'Không thực hiện được thay đổi. Vui lòng thử lại.'
            : 'The change could not be completed. Please try again.',
      );
    } finally {
      setBusyKey(null);
    }
  };

  const resetAll = () => {
    const confirmed = window.confirm(
      language === 'vi'
        ? 'Xóa toàn bộ điều mondaiy đã ghi nhớ về bạn? Dữ liệu nguồn và lịch sử chat không bị xóa.'
        : 'Delete everything mondaiy remembers about you? Source data and chat history will not be deleted.',
    );
    if (confirmed) void withBusy('reset-all', () => clearLongTermMemory(accessToken!));
  };

  const pendingCandidates = memories.filter((m) => m.status === 'candidate');
  const disputedGroups = Array.from(
    memories.filter((m) => m.status === 'disputed').reduce((groups, memory) => {
      const current = groups.get(memory.key) ?? [];
      current.push(memory);
      groups.set(memory.key, current);
      return groups;
    }, new Map<string, MemoryItem[]>()),
  ).map(([, group]) => group);
  const canonicalMemories = memories.filter((m) => m.status === 'confirmed');

  const confirmedCount = memories.filter((m) => m.status === 'confirmed').length;
  const disputedCount = memories.filter((m) => m.status === 'disputed').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-[var(--color-text-primary)] font-heading">
            {t.dataPrivacy.memory.title}
          </h2>
          <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
            {t.dataPrivacy.memory.subtitle}
          </p>
        </div>
        <button
          type="button"
          onClick={resetAll}
          disabled={busyKey === 'reset-all' || memories.length === 0}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#F0D8D3] bg-[#F9DEDE] px-3.5 py-2 text-xs font-bold text-[#A03D3D] transition-colors hover:bg-[#F0D8D3] disabled:opacity-50 dark:border-[#5A3038] dark:bg-[#281B2A] dark:text-[#DC9A91]"
        >
          <RotateCcw className="h-4 w-4" />
          {language === 'vi' ? 'Reset điều đã nhớ' : 'Reset learned memory'}
        </button>
      </div>

      {/* Summary Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3" data-tour-id="privacy-memory-summary">
        <div className="p-4 bg-[var(--color-surface-muted)] rounded-2xl border border-[var(--color-border)] shadow-2xs">
          <span className="text-xs text-[var(--color-text-secondary)] block font-medium">
            {language === 'vi' ? 'Ghi nhớ đã xác nhận' : 'Confirmed Memories'}
          </span>
          <span className="text-2xl font-semibold text-[#2A6B4F] dark:text-[#8CC3A2] font-heading mt-1 block">
            {confirmedCount}
          </span>
        </div>

        <div className="p-4 bg-[var(--color-surface-muted)] rounded-2xl border border-[var(--color-border)] shadow-2xs">
          <span className="text-xs text-[var(--color-text-secondary)] block font-medium">
            {language === 'vi' ? 'Chờ xem xét' : 'Pending Review'}
          </span>
          <span className="text-2xl font-semibold text-[#8A5712] dark:text-[#D7B270] font-heading mt-1 block">
            {pendingCandidates.length}
          </span>
        </div>

        <div className="p-4 bg-[var(--color-surface-muted)] rounded-2xl border border-[var(--color-border)] shadow-2xs">
          <span className="text-xs text-[var(--color-text-secondary)] block font-medium">
            {language === 'vi' ? 'Đang mâu thuẫn' : 'Disputed'}
          </span>
          <span className="text-2xl font-semibold text-[#A03D3D] dark:text-[#DC9A91] font-heading mt-1 block">
            {disputedCount}
          </span>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-[var(--color-text-secondary)]">
          <Loader2 className="w-4 h-4 animate-spin" />
          {language === 'vi' ? 'Đang tải...' : 'Loading...'}
        </div>
      )}

      {!loading && loadError && (
        <div className="p-4 rounded-2xl border border-[var(--color-danger)] text-xs text-[var(--color-danger)]">
          {loadError}
        </div>
      )}

      {actionError && (
        <div role="alert" className="p-4 rounded-2xl border border-[var(--color-danger)] text-xs text-[var(--color-danger)]">
          {actionError}
        </div>
      )}

      {!loading && !loadError && (
        <>
          <MemoryGraphView language={language} />
          {disputedGroups.map((group) => (
            <MemoryConflictProposal
              key={group[0]?.key}
              memories={group}
              language={language}
              busyKey={busyKey}
              onChoose={(key, version) => void withBusy(key, () => confirmLongTermMemory(key, accessToken!, version))}
              onDelete={(key) => void withBusy(key, () => deleteLongTermMemory(key, accessToken!))}
            />
          ))}
          {/* Pending Candidates Section */}
          {pendingCandidates.length > 0 && (
            <div
              className="p-5 bg-[#F6EEDA] dark:bg-[#0F1F38] border border-[#D7B270] dark:border-[#1E2E4A] rounded-2xl space-y-4"
              data-tour-id="privacy-memory-pending"
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[#8A5712] dark:text-[#D7B270]" />
                <h3 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading">
                  {t.dataPrivacy.memory.candidateNotice}
                </h3>
              </div>

              <div className="space-y-3">
                {pendingCandidates.map((cand) => (
                  <div
                    key={cand.key}
                    className="p-4 bg-[var(--color-surface-muted)] rounded-xl border border-[var(--color-border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <span className="text-xs font-bold text-[var(--color-text-primary)]">
                        {memoryLabel(cand)}
                      </span>
                      <p className="text-[11px] text-[var(--color-text-secondary)]">
                        {cand.kind} · {cand.source}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => setActiveDetailMemory(cand)}
                        className="px-3 py-1.5 bg-[var(--color-accent-soft)] text-[var(--color-text-primary)] rounded-lg text-xs font-bold transition-colors flex items-center gap-1"
                      >
                        <Eye className="w-3.5 h-3.5 text-[#2563A6]" />
                        {language === 'vi' ? 'Xem nguồn' : 'View source'}
                      </button>
                      <button
                        onClick={() => void withBusy(cand.key, () => confirmLongTermMemory(cand.key, accessToken!))}
                        disabled={busyKey === cand.key}
                        className="px-3 py-1.5 bg-[#2A6B4F] text-white rounded-lg text-xs font-bold hover:bg-[#27573F] transition-colors flex items-center gap-1 disabled:opacity-60"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {t.dataPrivacy.memory.confirm}
                      </button>
                      <button
                        onClick={() => void withBusy(cand.key, () => rejectLongTermMemory(cand.key, accessToken!))}
                        disabled={busyKey === cand.key}
                        className="px-3 py-1.5 bg-[#F9DEDE] dark:bg-[#0F1F38] text-[#A03D3D] dark:text-[#DC9A91] rounded-lg text-xs font-bold hover:bg-[#F0D8D3] transition-colors flex items-center gap-1 disabled:opacity-60"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                        {t.dataPrivacy.memory.reject}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Canonical Memories List */}
          <div className="space-y-3" data-tour-id="privacy-memory-canonical">
            <h3 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading">
              {language === 'vi' ? 'Thông tin ghi nhớ chính thức' : 'Canonical Retained Memories'}
            </h3>

            {canonicalMemories.length === 0 ? (
              <div className="bg-[var(--color-surface-muted)] p-12 rounded-2xl border border-[var(--color-border)] text-center space-y-3">
                <Brain className="w-10 h-10 text-[#5A6A85] mx-auto" />
                <h4 className="text-sm font-bold text-[var(--color-text-primary)]">
                  {t.dataPrivacy.emptyStates.noMemoriesTitle}
                </h4>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  {t.dataPrivacy.emptyStates.noMemoriesDesc}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {canonicalMemories.map((mem) => (
                  <div
                    key={mem.key}
                    className="bg-[var(--color-surface-muted)] p-5 rounded-2xl border border-[var(--color-border)] shadow-2xs hover:border-[#0F1F38]/30 transition-all space-y-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold px-2.5 py-0.5 rounded-md bg-[var(--color-accent-soft)] text-[var(--color-primary)]">
                            {mem.kind}
                          </span>
                          <span className="text-xs text-[var(--color-text-secondary)]">· {mem.source}</span>
                        </div>
                        <p className="text-sm font-bold text-[var(--color-text-primary)] leading-relaxed pt-1">
                          {memoryLabel(mem)}
                        </p>
                      </div>

                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DFF0E6] text-[#2A6B4F] dark:bg-[#0F1F38] dark:text-[#8CC3A2] shrink-0">
                        <CheckCircle2 className="w-3 h-3" />
                        {mem.status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs pt-2 border-t border-[var(--color-border)]">
                      <span className="flex items-center gap-1 text-[var(--color-text-secondary)]">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(mem.lastReinforcedAt).toLocaleDateString(language === 'vi' ? 'vi-VN' : 'en-GB')}
                      </span>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setActiveDetailMemory(mem)}
                          className="px-2.5 py-1 bg-[var(--color-accent-soft)] text-[var(--color-text-primary)] rounded-lg font-semibold text-xs hover:bg-[var(--color-surface-hover)] transition-colors flex items-center gap-1"
                        >
                          <Eye className="w-3.5 h-3.5 text-[#2563A6]" />
                          {language === 'vi' ? 'Xem chi tiết' : 'View Details'}
                        </button>

                        <button
                          onClick={() => void withBusy(mem.key, () => deleteLongTermMemory(mem.key, accessToken!))}
                          disabled={busyKey === mem.key}
                          className="p-1 text-[#A03D3D] dark:text-[#DC9A91] hover:bg-[#F9DEDE] rounded-lg transition-colors disabled:opacity-60"
                          title={t.dataPrivacy.memory.deleteMemory}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Học thích ứng — cùng trang privacy, không phải trang riêng (FR-111) */}
      <div className="border-t border-[var(--color-border-subtle)] pt-6">
        <AdaptiveLearningSection />
      </div>

      <MemoryDetailDrawer
        memory={activeDetailMemory}
        isOpen={Boolean(activeDetailMemory)}
        onClose={() => setActiveDetailMemory(null)}
        onConfirm={(key) => void withBusy(key, () => confirmLongTermMemory(key, accessToken!))}
        onReject={(key) => void withBusy(key, () => rejectLongTermMemory(key, accessToken!))}
        onDelete={(key) => void withBusy(key, () => deleteLongTermMemory(key, accessToken!))}
        onEdit={(key, value) => void withBusy(key, () => editLongTermMemory(key, value, accessToken!))}
        busy={Boolean(busyKey)}
      />
    </div>
  );
};
