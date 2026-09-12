import React, { useCallback, useEffect, useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import { useAuthStore } from '../../stores/useAuthStore';
import { ApiError } from '../../lib/apiClient';
import {
  getLearningConsent,
  updateLearningConsent,
  listLearningCandidates,
  rejectLearningCandidate,
  resetLearning,
  listLearningAudit,
  type ConsentState,
  type LearningAuditEvent,
  type LearningCandidate,
  type LearningCapability,
  type LearningScope,
} from '../../lib/adaptiveLearningApi';
import { Toggle } from '../ui/Toggle';
import { Sparkles, Loader2, GraduationCap, RotateCcw } from 'lucide-react';

const CAPABILITIES: LearningCapability[] = [
  'chat_learning',
  'adaptive_style',
  'learned_skills',
  'routine_learning',
];

const RESET_SCOPES: LearningScope[] = ['style', 'skills', 'routines', 'all'];

// Nhãn thân thiện cho audit action — action lạ thì hiện nguyên văn thay vì trống.
function auditActionLabel(action: string, vi: boolean): string {
  const labels: Record<string, [string, string]> = {
    consent_enabled: ['Bật quyền học', 'Learning permission enabled'],
    consent_revoked: ['Thu hồi quyền học', 'Learning permission revoked'],
    candidate_rejected: ['Từ chối đề xuất', 'Suggestion rejected'],
    learning_reset: ['Đặt lại học thích ứng', 'Adaptive learning reset'],
  };
  const pair = labels[action];
  if (!pair) return action;
  return vi ? pair[0] : pair[1];
}

export const AdaptiveLearningSection: React.FC = () => {
  const { t, language } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const a = t.dataPrivacy.adaptiveLearning;

  const [consents, setConsents] = useState<ConsentState[]>([]);
  const [candidates, setCandidates] = useState<LearningCandidate[]>([]);
  const [events, setEvents] = useState<LearningAuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [resetScope, setResetScope] = useState<LearningScope>('all');

  const scopeLabels: Record<LearningScope, string> = {
    style: a.scopeStyle,
    skills: a.scopeSkills,
    routines: a.scopeRoutines,
    all: a.scopeAll,
  };

  const capabilityCopy: Record<LearningCapability, { label: string; desc: string }> = {
    chat_learning: { label: a.capabilityChatLearning, desc: a.capabilityChatLearningDesc },
    adaptive_style: { label: a.capabilityAdaptiveStyle, desc: a.capabilityAdaptiveStyleDesc },
    learned_skills: { label: a.capabilityLearnedSkills, desc: a.capabilityLearnedSkillsDesc },
    routine_learning: { label: a.capabilityRoutineLearning, desc: a.capabilityRoutineLearningDesc },
  };

  const enabledByCapability = (capability: LearningCapability): ConsentState | undefined =>
    consents.find((row) => row.capability === capability);

  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    try {
      const [consentRes, candidateRes, auditRes] = await Promise.all([
        getLearningConsent(accessToken),
        listLearningCandidates(accessToken),
        listLearningAudit(accessToken),
      ]);
      setConsents(consentRes.consents);
      setCandidates(candidateRes.candidates);
      setEvents(auditRes.events.slice(0, 5));
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.message : language === 'vi' ? 'Không tải được dữ liệu.' : 'Could not load data.',
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken, language]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const withBusy = async (key: string, action: () => Promise<unknown>) => {
    setBusyKey(key);
    try {
      await action();
      await reload();
    } catch (err) {
      // Cờ tổng đang tắt phía server trả 403 — khoá công tắc và nói rõ thay vì báo lỗi chung.
      if (err instanceof ApiError && err.status === 403) {
        setLocked(true);
        await reload();
      } else {
        throw err;
      }
    } finally {
      setBusyKey(null);
    }
  };

  const onToggleConsent = (capability: LearningCapability, next: boolean) =>
    withBusy(`consent:${capability}`, () => updateLearningConsent(capability, next, accessToken!));

  const onReject = (candidate: LearningCandidate) =>
    withBusy(`candidate:${candidate.id}`, () =>
      rejectLearningCandidate(candidate.id, ['user_rejected'], accessToken!),
    );

  const onReset = () => {
    if (!window.confirm(`${a.resetConfirmTitle}\n\n${a.resetConfirmDesc}`)) return;
    void withBusy('reset', () => resetLearning(resetScope, accessToken!));
  };

  // Payload là JSON có cấu trúc; ưu tiên các key dễ đọc, còn lại in gọn JSON.
  const describePayload = (candidate: LearningCandidate): string => {
    const payload = candidate.payload ?? {};
    const parts: string[] = [];
    if (typeof payload.dimension === 'string') parts.push(payload.dimension.replace(/_/g, ' '));
    if (payload.value !== undefined && payload.value !== null) parts.push(String(payload.value));
    if (typeof payload.rationale === 'string') parts.push(payload.rationale);
    if (parts.length === 0) parts.push(JSON.stringify(payload));
    return parts.join(': ');
  };

  return (
    <div className="space-y-4" data-testid="adaptive-learning-section">
      <div className="flex items-start gap-2 pt-2">
        <GraduationCap className="w-5 h-5 text-[var(--color-primary)] mt-1" />
        <div>
          <h3 className="text-lg font-semibold text-[var(--color-text-primary)] font-heading">{a.title}</h3>
          <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 max-w-2xl">{a.subtitle}</p>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-[var(--color-text-secondary)]">
          <Loader2 className="w-4 h-4 animate-spin" />
          {language === 'vi' ? 'Đang tải...' : 'Loading...'}
        </div>
      )}

      {!loading && loadError && (
        <div className="p-4 rounded-2xl border border-[var(--color-danger)] text-xs text-[var(--color-danger)]">
          {loadError}
        </div>
      )}

      {!loading && !loadError && (
        <>
          {/* Quyền học — bốn công tắc độc lập, mặc định tắt theo ADR-017 */}
          <div
            className="p-5 bg-[var(--color-surface-muted)] rounded-2xl border border-[var(--color-border)] space-y-4"
            data-tour-id="privacy-adaptive-consent"
          >
            <h4 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading">{a.consentTitle}</h4>
            {locked && (
              <div className="p-3 rounded-xl border border-[#D7B270] dark:border-[#1E2E4A] bg-[#F6EEDA] dark:bg-[#0F1F38] text-xs text-[#8A5712] dark:text-[#D7B270]" role="status">
                {a.lockedNotice}
              </div>
            )}
            <div className="space-y-3">
              {CAPABILITIES.map((capability) => {
                const state = enabledByCapability(capability);
                const checked = Boolean(state?.enabled);
                return (
                  <div key={capability} className="flex items-center justify-between gap-4">
                    <div className="space-y-0.5">
                      <span className="text-sm font-bold text-[var(--color-text-primary)] block">
                        {capabilityCopy[capability].label}
                      </span>
                      <span className="text-[11px] text-[var(--color-text-secondary)] block">
                        {capabilityCopy[capability].desc}
                      </span>
                    </div>
                    <Toggle
                      aria-label={`learning-consent-${capability}`}
                      checked={checked}
                      disabled={locked || busyKey !== null}
                      onChange={(next) => void onToggleConsent(capability, next)}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Inbox đề xuất — chưa duyệt thì không ảnh hưởng câu trả lời */}
          <div className="space-y-3" data-tour-id="privacy-adaptive-inbox">
            <h4 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#8A5712] dark:text-[#D7B270]" />
              {a.inboxTitle}
            </h4>

            {candidates.length === 0 ? (
              <p className="text-xs text-[var(--color-text-secondary)] bg-[var(--color-surface-muted)] rounded-xl p-4 border border-[var(--color-border)]">
                {a.emptyInbox}
              </p>
            ) : (
              candidates.map((candidate) => (
                <div
                  key={candidate.id}
                  className="p-4 bg-[#F6EEDA] dark:bg-[#0F1F38] border border-[#D7B270] dark:border-[#1E2E4A] rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-[var(--color-text-primary)] block">
                      {describePayload(candidate)}
                    </span>
                    <span className="text-[11px] text-[var(--color-text-secondary)] block">
                      {candidate.candidateType === 'style_preference'
                        ? scopeLabels.style
                        : candidate.candidateType === 'skill'
                          ? scopeLabels.skills
                          : scopeLabels.routines}
                      {' · '}
                      {a.confidenceLabel}: {Math.round((candidate.confidence ?? 0) * 100)}%
                    </span>
                  </div>
                  <button
                    onClick={() => void onReject(candidate)}
                    disabled={busyKey !== null}
                    className="px-3 py-1.5 bg-[#F9DEDE] dark:bg-[#0F1F38] text-[#A03D3D] dark:text-[#DC9A91] rounded-lg text-xs font-bold hover:bg-[#F0D8D3] transition-colors shrink-0 disabled:opacity-60"
                  >
                    {a.dontSuggestAgain}
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Reset theo lớp — không đụng task/lịch/dữ liệu nguồn */}
          <div
            className="p-5 bg-[var(--color-surface-muted)] rounded-2xl border border-[var(--color-border)] flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            data-tour-id="privacy-adaptive-reset"
          >
            <div className="space-y-0.5">
              <span className="text-sm font-bold text-[var(--color-text-primary)] block">{a.resetTitle}</span>
              <span className="text-[11px] text-[var(--color-text-secondary)] block">{a.resetConfirmDesc}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <select
                value={resetScope}
                onChange={(e) => setResetScope(e.target.value as LearningScope)}
                aria-label="learning-reset-scope"
                className="px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-xs font-semibold text-[var(--color-text-primary)]"
              >
                {RESET_SCOPES.map((scope) => (
                  <option key={scope} value={scope}>
                    {scopeLabels[scope]}
                  </option>
                ))}
              </select>
              <button
                onClick={onReset}
                disabled={busyKey !== null}
                className="px-3 py-2 rounded-xl text-xs font-bold border border-[var(--color-danger)] text-[#A03D3D] dark:text-[#DC9A91] hover:bg-[#F9DEDE] transition-colors flex items-center gap-1 disabled:opacity-60"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                {a.resetButton}
              </button>
            </div>
          </div>

          {/* Hoạt động gần đây — chỉ id/action/thời điểm, không có nội dung hội thoại */}
          {events.length > 0 && (
            <div className="space-y-2" data-tour-id="privacy-adaptive-audit">
              <h4 className="text-sm font-extrabold text-[var(--color-text-primary)] font-heading">
                {a.recentActivityTitle}
              </h4>
              <ul className="divide-y divide-[var(--color-border)] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-muted)]">
                {events.map((event) => (
                  <li key={event.id} className="px-4 py-2.5 flex items-center justify-between gap-3 text-xs">
                    <span className="font-semibold text-[var(--color-text-primary)]">
                      {auditActionLabel(event.action, language === 'vi')}
                    </span>
                    <span className="text-[var(--color-text-secondary)]">
                      {new Date(event.createdAt).toLocaleString(language === 'vi' ? 'vi-VN' : 'en-GB')}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
};
