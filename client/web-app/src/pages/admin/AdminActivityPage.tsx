import React, { useCallback, useState } from 'react';
import { Activity, Filter, RefreshCw } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { listAudit, type AdminAuditRow } from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';

// Loại đối tượng có thể lọc. Danh sách cứng vì audit_events chỉ ghi những loại
// này (xem emit_audit trong src/services/telemetry.py) — thêm loại mới ở backend
// thì thêm ở đây, chứ tự suy từ dữ liệu thì bộ lọc rỗng khi chưa có bản ghi nào.
const LOAI_DOI_TUONG = ['user', 'connection', 'task', 'run'];

const NHAN_ACTION: Record<string, string> = {
  admin_user_updated: 'Cập nhật quyền hoặc trạng thái tài khoản',
};

const thoiGian = (iso: string): string =>
  new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });

// details là JSON tự do nên hiển thị dạng before → after nếu có, còn lại thì in
// nguyên. Không đưa vào <pre> quá dài để bảng khỏi vỡ.
const tomTatChiTiet = (details: Record<string, unknown> | null): string => {
  if (!details) return '—';
  const before = details.before as Record<string, unknown> | undefined;
  const after = details.after as Record<string, unknown> | undefined;
  if (before && after) {
    const doi = Object.keys(after)
      .filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]))
      .map((k) => `${k}: ${JSON.stringify(before[k])} → ${JSON.stringify(after[k])}`);
    return doi.length ? doi.join(', ') : 'không có thay đổi';
  }
  return JSON.stringify(details).slice(0, 200);
};

export const AdminActivityPage: React.FC = () => {
  const { t } = useTranslation();
  const [objectType, setObjectType] = useState('');

  const nap = useCallback(
    (token: string) => listAudit(token, { objectType, limit: 100 }),
    [objectType],
  );
  const { data, loading, error, reload } = useAdminData<{
    items: AdminAuditRow[];
    total: number;
  }>(nap, [objectType]);

  const rows = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.activity}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Nhật ký thay đổi theo FR-070 — ai làm gì, lúc nào, trên bản ghi nào. Không xoá theo
            thời hạn lưu của dữ liệu đo lường.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-[#5A6A85]" />
          <select
            value={objectType}
            onChange={(e) => setObjectType(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white font-medium"
          >
            <option value="">Tất cả đối tượng</option>
            {LOAI_DOI_TUONG.map((loai) => (
              <option key={loai} value={loai}>
                {loai}
              </option>
            ))}
          </select>
          <button
            onClick={reload}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] text-xs font-semibold text-[#2563A6] hover:bg-[#EDF2FB] dark:hover:bg-[#0A1628] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Tải lại
          </button>
        </div>
      </div>

      {loading && <AdminLoading label="Đang tải nhật ký…" />}
      {error && <AdminError message={error} onRetry={reload} />}
      {data && rows.length === 0 && (
        <AdminEmpty
          title="Chưa có thao tác nào được ghi"
          hint={
            objectType
              ? `Không có bản ghi nào cho đối tượng "${objectType}".`
              : 'Mọi thay đổi quyền hoặc cấu hình sẽ xuất hiện ở đây.'
          }
        />
      )}

      {rows.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] overflow-hidden shadow-xs">
          <div className="p-4 border-b border-[#E1EBFA] dark:border-[#1A2A42] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#2563A6]" />
              <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
                {rows.length} bản ghi gần nhất
              </h3>
            </div>
            <span className="text-[10px] font-semibold text-[#5A6A85]">
              tổng cộng {data?.total ?? 0}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#EDF2FB] dark:bg-[#0A1628] border-b border-[#D5DDEB] dark:border-[#1A2A42] text-[#5A6A85] dark:text-[#8B98AB] font-medium text-[10px]">
                <tr>
                  <th className="p-4">Thời điểm</th>
                  <th className="p-4">Người thực hiện</th>
                  <th className="p-4">Thao tác</th>
                  <th className="p-4">Đối tượng</th>
                  <th className="p-4">Thay đổi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42] font-medium text-[#0F1F38] dark:text-slate-200">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-[#EDF2FB]/50 dark:hover:bg-[#0A1628]/40 transition-colors"
                  >
                    <td className="p-4 text-[#5A6A85] whitespace-nowrap">
                      {thoiGian(row.createdAt)}
                    </td>
                    <td className="p-4">
                      <span className="font-bold">{row.actorType}</span>
                      {row.actorId && (
                        <span className="text-[11px] text-[#5A6A85] block">#{row.actorId}</span>
                      )}
                    </td>
                    <td className="p-4">{NHAN_ACTION[row.action] ?? row.action}</td>
                    <td className="p-4 text-[#5A6A85]">
                      {row.objectType} #{row.objectId}
                    </td>
                    <td className="p-4 text-[#5A6A85] max-w-sm truncate">
                      {tomTatChiTiet(row.details)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
