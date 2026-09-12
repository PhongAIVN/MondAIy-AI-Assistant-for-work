import React, { useEffect, useState } from 'react';
import { FolderPlus, X } from 'lucide-react';

import { useTranslation } from '../../i18n/useTranslation';
import {
  addConversationToProject,
  fetchProjectSuggestion,
  type ProjectSuggestion,
} from '../../lib/projectsApi';
import { useAppStore } from '../../stores/useAppStore';
import { useAuthStore } from '../../stores/useAuthStore';

type Props = {
  conversationId: string | undefined;
  /** Số lượt đã có trong hội thoại — dưới ngưỡng thì chưa đủ nội dung để so. */
  turnCount: number;
};

/** Đã bỏ qua trong phiên trình duyệt này thì đừng hỏi lại. Giữ ở bộ nhớ phiên
 *  chứ không localStorage: người dùng đổi ý sau khi tải lại trang là hợp lý,
 *  còn hỏi lại ngay trong cùng phiên thì phiền. */
const dismissed = new Set<string>();

const MIN_TURNS = 2;

/**
 * Thẻ "hội thoại này có vẻ thuộc dự án X — thêm vào?".
 *
 * Chỉ hiện khi server đủ chắc (server tự áp ngưỡng). Không có gợi ý thì không
 * vẽ gì — thà im lặng còn hơn hỏi sai liên tục rồi bị bỏ qua như thông báo rác.
 */
export const ProjectSuggestionCard: React.FC<Props> = ({ conversationId, turnCount }) => {
  const { language } = useTranslation();
  const vi = language === 'vi';
  const accessToken = useAuthStore((s) => s.accessToken);
  const addToast = useAppStore((s) => s.addToast);
  const [suggestion, setSuggestion] = useState<ProjectSuggestion | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!accessToken || !conversationId || turnCount < MIN_TURNS) return;
    if (dismissed.has(conversationId)) return;
    let cancelled = false;
    void (async () => {
      const found = await fetchProjectSuggestion(accessToken, Number(conversationId));
      if (!cancelled) setSuggestion(found);
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, conversationId, turnCount]);

  if (!suggestion || !conversationId) return null;

  const handleAdd = async () => {
    if (!accessToken) return;
    setBusy(true);
    try {
      await addConversationToProject(accessToken, suggestion.projectId, Number(conversationId));
      setSuggestion(null);
      dismissed.add(conversationId);
      addToast({
        type: 'success',
        title: vi ? 'Đã thêm vào dự án' : 'Added to project',
        message: suggestion.projectName,
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: vi ? 'Không thêm được' : 'Could not add',
        message: error instanceof Error ? error.message : String(error),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-2xl rounded-2xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2.5">
          <FolderPlus className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
          <p className="text-sm text-[var(--color-text-secondary)]">
            {vi ? 'Hội thoại này có vẻ thuộc dự án ' : 'This conversation looks related to '}
            <span className="font-semibold text-[var(--color-text-primary)]">
              {suggestion.projectName}
            </span>
            {vi ? '. Thêm vào?' : '. Add it?'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            onClick={handleAdd}
            disabled={busy}
            className="rounded-lg bg-[var(--color-primary)] px-2.5 py-1 text-xs font-semibold text-[var(--color-on-primary)] disabled:opacity-60"
          >
            {vi ? 'Thêm' : 'Add'}
          </button>
          <button
            type="button"
            onClick={() => {
              dismissed.add(conversationId);
              setSuggestion(null);
            }}
            aria-label={vi ? 'Bỏ qua gợi ý' : 'Dismiss suggestion'}
            className="rounded-lg p-1 hover:bg-[var(--color-surface-hover)]"
          >
            <X className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
          </button>
        </div>
      </div>
    </div>
  );
};
