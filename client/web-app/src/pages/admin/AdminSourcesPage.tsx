import React, { useCallback } from 'react';
import { Layers, AlertTriangle, CheckCircle2, RefreshCw, Clock } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { getSources, type AdminSources } from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';

// Trạng thái do backend đặt trong src/models/connection.py. Nhóm lại thành ba
// mức để bảng đọc được: bình thường / đang chờ đồng bộ / hỏng.
const HONG = new Set(['error', 'revoked', 'expired']);
const CHO = new Set(['connected_pending_sync', 'syncing']);

const NHAN_TRANG_THAI: Record<string, string> = {
  connected: 'đã kết nối',
  connected_pending_sync: 'chờ đồng bộ lần đầu',
  syncing: 'đang đồng bộ',
  error: 'lỗi',
  revoked: 'đã thu hồi quyền',
  expired: 'token hết hạn',
};

const thoiGian = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : 'chưa lần nào';

export const AdminSourcesPage: React.FC = () => {
  const { t } = useTranslation();
  const nap = useCallback((token: string) => getSources(token, 100), []);
  const { data, loading, error, reload } = useAdminData<AdminSources>(nap);

  const providers = data?.providers ?? [];
  const connections = data?.connections ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.sources}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Trạng thái đồng bộ của từng kết nối. Không hiển thị nội dung đã đồng bộ.
          </p>
        </div>
        <button
          onClick={reload}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] text-xs font-semibold text-[#2563A6] hover:bg-[#EDF2FB] dark:hover:bg-[#0A1628] transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Tải lại
        </button>
      </div>

      {loading && <AdminLoading label="Đang tải trạng thái nguồn…" />}
      {error && <AdminError message={error} onRetry={reload} />}
      {data && providers.length === 0 && (
        <AdminEmpty
          title="Chưa có kết nối nguồn nào"
          hint="Trang này có dữ liệu khi người dùng đầu tiên kết nối Gmail hoặc Discord."
        />
      )}

      {providers.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map((p) => (
            <div
              key={p.provider}
              className="p-4 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] shadow-xs space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-[#0F1F38] dark:text-white capitalize">
                  {p.provider}
                </span>
                {p.failed > 0 ? (
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                )}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-2xl font-extrabold text-[#0F1F38] dark:text-white">
                  {p.connected}
                </span>
                <span className="text-xs text-[#5A6A85]">/ {p.total} kết nối ổn</span>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] font-semibold">
                {p.syncing > 0 && (
                  <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300">
                    {p.syncing} đang chờ
                  </span>
                )}
                {p.failed > 0 && (
                  <span className="px-2 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300">
                    {p.failed} lỗi
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-[#5A6A85] dark:text-[#8B98AB]">
                <Clock className="w-3 h-3" /> đồng bộ gần nhất {thoiGian(p.lastSyncedAt)}
              </div>
            </div>
          ))}
        </div>
      )}

      {connections.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] overflow-hidden shadow-xs">
          <div className="p-4 border-b border-[#E1EBFA] dark:border-[#1A2A42] flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#2563A6]" />
            <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
              Từng kết nối — hỏng xếp lên đầu
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#EDF2FB] dark:bg-[#0A1628] border-b border-[#D5DDEB] dark:border-[#1A2A42] text-[#5A6A85] dark:text-[#8B98AB] font-medium text-[10px]">
                <tr>
                  <th className="p-4">Nguồn</th>
                  <th className="p-4">Tài khoản</th>
                  <th className="p-4">Trạng thái</th>
                  <th className="p-4">Đồng bộ gần nhất</th>
                  <th className="p-4">Lỗi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42] font-medium text-[#0F1F38] dark:text-slate-200">
                {connections.map((c) => {
                  const hong = HONG.has(c.status);
                  const cho = CHO.has(c.status);
                  return (
                    <tr
                      key={c.id}
                      className="hover:bg-[#EDF2FB]/50 dark:hover:bg-[#0A1628]/40 transition-colors"
                    >
                      <td className="p-4 font-bold capitalize">{c.provider}</td>
                      <td className="p-4 text-[#5A6A85]">{c.userEmail || `#${c.userId}`}</td>
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                            hong
                              ? 'bg-rose-100 dark:bg-rose-950/80 text-rose-800 dark:text-rose-300'
                              : cho
                                ? 'bg-blue-100 dark:bg-blue-950/80 text-blue-800 dark:text-blue-300'
                                : 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${hong ? 'bg-rose-500' : cho ? 'bg-blue-500' : 'bg-emerald-500'}`}
                          />
                          {NHAN_TRANG_THAI[c.status] ?? c.status}
                        </span>
                      </td>
                      <td className="p-4 text-[#5A6A85]">{thoiGian(c.lastSyncedAt)}</td>
                      <td className="p-4 text-[#5A6A85] max-w-xs truncate" title={c.lastError ?? ''}>
                        {c.lastError ?? '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
