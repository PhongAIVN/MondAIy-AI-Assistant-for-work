import React, { useCallback, useEffect, useState } from 'react';
import { useAppStore } from '../../stores/useAppStore';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';
import { resolveBrandIcon } from '../ui/BrandIcons';
import {
  listConnections,
  disconnect as disconnectProvider,
  type ConnectionProvider,
  type ConnectionStatus,
} from '../../lib/connectionsApi';
import { ApiError } from '../../lib/apiClient';
import { X, CheckCircle2, ShieldCheck, Layers, Unplug, Loader2 } from 'lucide-react';
import { Dialog } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { usePipelineRunStore } from '../../stores/usePipelineRunStore';

const PROVIDER_LABEL: Record<ConnectionProvider, string> = {
  google: 'Google',
  discord: 'Discord',
  telegram: 'Telegram',
  jira: 'Jira',
  outlook: 'Outlook',
  slack: 'Slack',
};

export const SourceLibraryModal: React.FC = () => {
  const { activeModal, closeModal, addToast } = useAppStore();
  const { t, language } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);

  const [connections, setConnections] = useState<ConnectionStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [disconnectingProvider, setDisconnectingProvider] = useState<ConnectionProvider | null>(null);
  const [disconnectTarget, setDisconnectTarget] = useState<ConnectionProvider | null>(null);

  // Chỉ nạp danh sách nguồn thật mỗi lần modal mở — trạng thái kết nối có thể
  // đã đổi từ lúc đóng modal lần trước (vd. vừa disconnect ở trang Sources).
  const reload = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setLoadError(null);
    try {
      const { connections: conns } = await listConnections(accessToken);
      setConnections(conns.filter((c) => c.connected));
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : t.sourcesPage.loadError);
    } finally {
      setLoading(false);
    }
  }, [accessToken, t.sourcesPage.loadError]);

  useEffect(() => {
    if (activeModal === 'source_library') {
      void reload();
    }
  }, [activeModal, reload]);

  if (activeModal !== 'source_library') return null;

  const handleDisconnect = async (provider: ConnectionProvider) => {
    if (!accessToken) return;
    setDisconnectingProvider(provider);
    try {
      await disconnectProvider(provider, accessToken);
      addToast({
        type: 'info',
        title: t.sourcesPage.disconnectTitle,
        message: t.sourcesPage.disconnectMsg.replace('{provider}', PROVIDER_LABEL[provider]),
      });
      setDisconnectTarget(null);
      await reload();
      void usePipelineRunStore.getState().loadConnections();
    } catch (err) {
      addToast({
        type: 'error',
        title: t.sourcesPage.disconnectFail,
        message: err instanceof ApiError ? err.message : t.sourcesPage.unknownError,
      });
    } finally {
      setDisconnectingProvider(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div
        className="relative w-full max-w-2xl bg-white dark:bg-[#122038] rounded-2xl shadow-xl border border-[#D5DDEB] dark:border-[#1E2E4A] overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-5 border-b border-[#D5DDEB] dark:border-[#1E2E4A] flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-[#2563A6] dark:text-[#7EB0E8] mb-1">
              <Layers className="w-4 h-4" />
              <span>
                {language === 'vi' ? 'Thư viện Nguồn dữ liệu' : 'Source Library'}
              </span>
            </div>
            <h2 className="text-2xl font-semibold text-[#0F1F38] dark:text-[#E2E8F0] font-heading">
              {language === 'vi' ? 'Nguồn đã kết nối' : 'Connected sources'}
            </h2>
            <p className="text-xs text-[#8B98AB] dark:text-[#AEB9CC] mt-1">
              {language === 'vi'
                ? 'Những nguồn mondaiy đang dùng để tạo briefing có căn cứ.'
                : 'Sources mondaiy is currently using to prepare grounded briefings.'}
            </p>
          </div>

          <button
            onClick={closeModal}
            className="p-1.5 text-[#8B98AB] dark:text-[#AEB9CC] hover:text-[#0F1F38] dark:hover:text-white hover:bg-[#EBEFF8] dark:hover:bg-[#0F1F38] rounded-xl transition-colors"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Sources List */}
        <div className="p-5 overflow-y-auto space-y-3 flex-1">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-[#8B98AB] dark:text-[#AEB9CC]">
              <Loader2 className="w-4 h-4 animate-spin" />
              {language === 'vi' ? 'Đang tải...' : 'Loading...'}
            </div>
          )}

          {!loading && loadError && (
            <p className="text-sm text-[#A03D3D] py-6 text-center">{loadError}</p>
          )}

          {!loading && !loadError && connections.length === 0 && (
            <p className="text-sm text-[#8B98AB] dark:text-[#AEB9CC] py-10 text-center">
              {language === 'vi'
                ? 'Chưa kết nối nguồn dữ liệu nào. Vào trang Nguồn dữ liệu để kết nối.'
                : 'No sources connected yet. Visit the Sources page to connect one.'}
            </p>
          )}

          {!loading &&
            !loadError &&
            connections.map((conn) => (
              <div
                key={conn.provider}
                className="p-4 bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1E2E4A] rounded-xl hover:border-[#2563A6]/40 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-start gap-3.5">
                  <div className="p-2.5 bg-[#EDF2FB] dark:bg-[#0F1F38] rounded-xl border border-[#D5DDEB] dark:border-[#1E2E4A] shrink-0">
                    {resolveBrandIcon(conn.provider, 'w-5 h-5') ?? <Layers className="w-5 h-5 text-[#2563A6]" />}
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-sm font-bold text-[#0F1F38] dark:text-[#E2E8F0]">
                        {PROVIDER_LABEL[conn.provider]}
                      </h4>
                      <span className="text-[10px] font-bold px-2 py-0.5 bg-[#EBF7F1] text-[#2A6B4F] dark:bg-[#2A6B4F]/20 dark:text-[#8CC3A2] rounded-full inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        {t.sourcesPage.connected}
                      </span>
                    </div>

                    {conn.accountLabel && (
                      <p className="text-[11px] text-[#8B98AB] dark:text-[#AEB9CC]/70">
                        {conn.accountLabel}
                      </p>
                    )}
                  </div>
                </div>

                <div className="shrink-0">
                  <button
                    onClick={() => setDisconnectTarget(conn.provider)}
                    disabled={disconnectingProvider === conn.provider}
                    className="px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all inline-flex items-center gap-1.5 shadow-2xs bg-[#EBEFF8] dark:bg-[#0F1F38] hover:bg-[#F9DEDE] dark:hover:bg-[#2A1420] text-[#8B98AB] dark:text-[#AEB9CC] hover:text-[#A03D3D] dark:hover:text-[#DC9A91] border border-[#D5DDEB] dark:border-[#1E2E4A] disabled:opacity-60"
                  >
                    {disconnectingProvider === conn.provider ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Unplug className="w-3.5 h-3.5" />
                    )}
                    <span>{t.sourcesPage.disconnect}</span>
                  </button>
                </div>
              </div>
            ))}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-[#EDF2FB] dark:bg-[#0F1F38] border-t border-[#D5DDEB] dark:border-[#1E2E4A] flex items-center justify-between text-xs text-[#8B98AB] dark:text-[#AEB9CC]">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-[#2A6B4F]" />
            <span>
              {language === 'vi'
                ? 'Quyền chỉ đọc · Không bao giờ lưu trữ mật khẩu'
                : 'Read-only access · Credentials never stored'}
            </span>
          </div>

          <button
            onClick={closeModal}
            className="px-4 py-1.5 bg-[var(--color-primary)] text-[var(--color-on-primary)] rounded-xl font-semibold text-xs shadow-2xs hover:bg-[var(--color-primary-hover)] transition-all"
          >
            {language === 'vi' ? 'Đóng' : 'Done'}
          </button>
        </div>
      </div>

      <Dialog
        isOpen={disconnectTarget !== null}
        onClose={() => setDisconnectTarget(null)}
        title={t.sourcesPage.disconnectConfirmTitle.replace('{provider}', disconnectTarget ? PROVIDER_LABEL[disconnectTarget] : '')}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDisconnectTarget(null)}>{t.sourcesPage.disconnectConfirmCancel}</Button>
            <Button
              variant="danger"
              icon={<Unplug className="w-3.5 h-3.5" />}
              disabled={disconnectTarget !== null && disconnectingProvider === disconnectTarget}
              onClick={() => disconnectTarget && void handleDisconnect(disconnectTarget)}
            >
              {disconnectTarget !== null && disconnectingProvider === disconnectTarget
                ? t.sourcesPage.disconnecting
                : t.sourcesPage.disconnectConfirmAction}
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--color-text-secondary)]">{t.sourcesPage.disconnectConfirmBody}</p>
      </Dialog>
    </div>
  );
};
