import React, { useCallback, useState } from 'react';
import {
  Users,
  Layers,
  FileCheck2,
  AlertTriangle,
  MessageSquare,
  Activity,
  ArrowUpRight,
  CheckCircle2,
  PlayCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from '../../i18n/useTranslation';
import { getOverview, listAudit, type AdminAuditRow, type AdminOverview } from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';

const CUA_SO = [7, 30, 90];

const thoiGianTuongDoi = (iso: string): string => {
  const phut = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (phut < 1) return 'vừa xong';
  if (phut < 60) return `${phut} phút trước`;
  const gio = Math.round(phut / 60);
  if (gio < 24) return `${gio} giờ trước`;
  return `${Math.round(gio / 24)} ngày trước`;
};

// Audit lưu action dạng khoá máy đọc; đổi sang câu người đọc ngay tại đây thay
// vì bắt backend trả chuỗi hiển thị — chuỗi hiển thị phải đổi theo ngôn ngữ.
const MO_TA_ACTION: Record<string, string> = {
  admin_user_updated: 'Cập nhật quyền hoặc trạng thái tài khoản',
};

export const AdminDashboardPage: React.FC = () => {
  const { t } = useTranslation();
  const [days, setDays] = useState(7);

  const napOverview = useCallback((token: string) => getOverview(token, days), [days]);
  const napAudit = useCallback((token: string) => listAudit(token, { limit: 5 }), []);

  const overview = useAdminData<AdminOverview>(napOverview, [days]);
  const audit = useAdminData<{ items: AdminAuditRow[]; total: number }>(napAudit);

  const soLieu = overview.data;
  const metrics = soLieu
    ? [
        {
          label: t.admin.metrics.totalUsers,
          value: String(soLieu.totalUsers),
          icon: Users,
          change: `${soLieu.roles.admin} admin · ${soLieu.roles.mentor} mentor`,
          color: 'text-blue-600',
        },
        {
          label: t.admin.metrics.activeUsers,
          value: String(soLieu.activeUsers),
          icon: Users,
          change: `có hoạt động trong ${soLieu.windowDays} ngày`,
          color: 'text-emerald-600',
        },
        {
          label: t.admin.metrics.connectedSources,
          value: String(soLieu.totalConnections),
          icon: Layers,
          change: `${soLieu.failedConnections} kết nối lỗi`,
          color: 'text-cyan-600',
        },
        {
          label: t.admin.metrics.sourceHealth,
          value: `${soLieu.sourceHealthPercent}%`,
          icon: CheckCircle2,
          change:
            soLieu.totalConnections === 0 ? 'chưa có kết nối nào' : 'trên tổng số kết nối',
          color: soLieu.failedConnections > 0 ? 'text-amber-600' : 'text-emerald-600',
        },
        {
          label: 'Lượt chạy pipeline',
          value: String(soLieu.runsTotal),
          icon: PlayCircle,
          change: `${soLieu.runsSucceeded} xong · ${soLieu.runsFailed} lỗi · ${soLieu.runsRunning} đang chạy`,
          color: soLieu.runsFailed > 0 ? 'text-amber-600' : 'text-indigo-600',
        },
        {
          label: t.admin.metrics.briefingsGenerated,
          value: String(soLieu.briefsGenerated),
          icon: FileCheck2,
          change: `trong ${soLieu.windowDays} ngày gần nhất`,
          color: 'text-blue-600',
        },
        {
          label: t.admin.metrics.openConflicts,
          value: String(soLieu.openConflicts),
          icon: AlertTriangle,
          change: 'việc thời gian chưa rõ, chưa xử lý',
          color: soLieu.openConflicts > 0 ? 'text-amber-600' : 'text-emerald-600',
        },
        {
          label: t.admin.metrics.feedbackCount,
          value: String(soLieu.feedbackTotal),
          icon: MessageSquare,
          change:
            soLieu.feedbackTotal > 0
              ? `${Math.round((soLieu.feedbackHelpful / soLieu.feedbackTotal) * 100)}% đánh giá hữu ích`
              : 'chưa có đánh giá nào',
          color: 'text-purple-600',
        },
      ]
    : [];

  const heThongOn =
    soLieu !== null && soLieu.failedConnections === 0 && soLieu.runsFailed === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.overview}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Số liệu tổng hợp toàn hệ thống. Không có nội dung email, tin nhắn hay câu hỏi của
            người dùng ở đây.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-1.5 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white font-medium"
            aria-label="Khoảng thời gian"
          >
            {CUA_SO.map((d) => (
              <option key={d} value={d}>
                {d} ngày
              </option>
            ))}
          </select>

          {soLieu && (
            <span
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold ${
                heThongOn
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  : 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${heThongOn ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`}
              />
              {heThongOn ? 'Hệ thống bình thường' : 'Có sự cố cần xem'}
            </span>
          )}
        </div>
      </div>

      {overview.loading && <AdminLoading />}
      {overview.error && <AdminError message={overview.error} onRetry={overview.reload} />}

      {soLieu && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="p-4 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] shadow-xs space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[#5A6A85] dark:text-[#8B98AB] truncate">
                  {m.label}
                </span>
                <m.icon className={`w-4 h-4 ${m.color}`} />
              </div>
              <div className="text-xl sm:text-2xl font-extrabold text-[#0F1F38] dark:text-white">
                {m.value}
              </div>
              <div className="text-[10px] font-medium text-[#5A6A85] dark:text-[#8B98AB]">
                {m.change}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        <div className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E1EBFA] dark:border-[#1A2A42]">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-[#2563A6]" />
              <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
                Sức khoẻ kết nối nguồn
              </h3>
            </div>
            <Link
              to="/admin/sources"
              className="text-xs text-[#2563A6] hover:underline font-bold flex items-center gap-1"
            >
              Xem tất cả <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          {soLieu && soLieu.totalConnections === 0 && (
            <AdminEmpty
              title="Chưa có kết nối nào"
              hint="Số liệu ở đây xuất hiện khi có người kết nối nguồn đầu tiên."
            />
          )}

          {soLieu && soLieu.totalConnections > 0 && (
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#EDF2FB] dark:bg-[#0A1628]">
                <span className="text-[#5A6A85] dark:text-[#8B98AB] font-semibold">
                  Kết nối đang lỗi
                </span>
                <strong
                  className={
                    soLieu.failedConnections > 0
                      ? 'text-rose-600 dark:text-rose-400'
                      : 'text-emerald-600 dark:text-emerald-400'
                  }
                >
                  {soLieu.failedConnections}/{soLieu.totalConnections}
                </strong>
              </div>
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#EDF2FB] dark:bg-[#0A1628]">
                <span className="text-[#5A6A85] dark:text-[#8B98AB] font-semibold">
                  Lượt chạy pipeline lỗi
                </span>
                <strong
                  className={
                    soLieu.runsFailed > 0
                      ? 'text-rose-600 dark:text-rose-400'
                      : 'text-emerald-600 dark:text-emerald-400'
                  }
                >
                  {soLieu.runsFailed}/{soLieu.runsTotal || 0}
                </strong>
              </div>
            </div>
          )}
        </div>

        <div className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#E1EBFA] dark:border-[#1A2A42]">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#2563A6]" />
              <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
                Thao tác quản trị gần đây
              </h3>
            </div>
            <Link
              to="/admin/activity"
              className="text-xs text-[#2563A6] hover:underline font-bold flex items-center gap-1"
            >
              Nhật ký <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          {audit.loading && <AdminLoading label="Đang tải nhật ký…" />}
          {audit.error && <AdminError message={audit.error} onRetry={audit.reload} />}
          {audit.data && audit.data.items.length === 0 && (
            <AdminEmpty
              title="Chưa có thao tác nào"
              hint="Mọi thay đổi quyền hoặc cấu hình sẽ hiện ở đây."
            />
          )}

          {audit.data && audit.data.items.length > 0 && (
            <div className="space-y-3 text-xs">
              {audit.data.items.map((row) => (
                <div key={row.id} className="flex items-start gap-3">
                  <div className="w-2 h-2 rounded-full bg-[#2563A6] mt-1.5 shrink-0" />
                  <div>
                    <p className="font-semibold text-[#0F1F38] dark:text-white">
                      {MO_TA_ACTION[row.action] ?? row.action}
                    </p>
                    <span className="text-[10px] text-[#5A6A85]">
                      {row.actorType} {row.actorId ?? ''} · {thoiGianTuongDoi(row.createdAt)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
