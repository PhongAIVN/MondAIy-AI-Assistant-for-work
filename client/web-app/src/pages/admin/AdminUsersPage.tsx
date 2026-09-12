import React, { useCallback, useEffect, useState } from 'react';
import { Search, Filter, UserX, UserCheck, AlertCircle } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import {
  listUsers,
  updateUser,
  type AdminRole,
  type AdminProgramAccessLevel,
  type AdminUserList,
  type AdminUserRow,
} from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { useAuthStore } from '../../stores/useAuthStore';
import { useAppStore } from '../../stores/useAppStore';
import { ApiError } from '../../lib/apiClient';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';

const VAI_TRO: AdminRole[] = ['participant', 'mentor', 'admin'];
const PROGRAM_ACCESS_LEVELS: Array<AdminProgramAccessLevel | ''> = ['', 'A', 'B', 'C'];

const ngayNgan = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—';

export const AdminUsersPage: React.FC = () => {
  const { t } = useTranslation();
  const accessToken = useAuthStore((state) => state.accessToken);
  const nguoiDangDangNhap = useAuthStore((state) => state.user);
  const addToast = useAppStore((state) => state.addToast);

  const [search, setSearch] = useState('');
  const [tuKhoa, setTuKhoa] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [programAccessFilter, setProgramAccessFilter] = useState<AdminProgramAccessLevel | ''>('');
  const [dangKhoa, setDangKhoa] = useState<AdminUserRow | null>(null);
  const [dangGui, setDangGui] = useState<string | null>(null);

  // Gõ tới đâu gọi API tới đó là mỗi phím một request. Chờ người dùng ngừng gõ
  // 300ms rồi mới tìm.
  useEffect(() => {
    const timer = setTimeout(() => setTuKhoa(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const nap = useCallback(
    (token: string) =>
      listUsers(token, {
        search: tuKhoa,
        role: roleFilter,
        programAccessLevel: programAccessFilter || undefined,
        limit: 100,
      }),
    [tuKhoa, roleFilter, programAccessFilter],
  );
  const { data, loading, error, reload } = useAdminData<AdminUserList>(nap, [tuKhoa, roleFilter, programAccessFilter]);

  const goiCapNhat = async (
    user: AdminUserRow,
    patch: { role?: AdminRole; isActive?: boolean; programCohortSlug?: string },
  ): Promise<void> => {
    if (!accessToken) return;
    setDangGui(user.id);
    try {
      await updateUser(accessToken, user.id, patch);
      addToast({ type: 'success', title: 'Đã cập nhật', message: user.email });
      reload();
    } catch (err) {
      // Server chặn tự đổi quyền/tự khoá mình bằng 400 — hiện đúng câu đó ra
      // thay vì báo lỗi chung chung.
      addToast({
        type: 'error',
        title: 'Không cập nhật được',
        message: err instanceof ApiError ? err.message : 'Không gọi được máy chủ.',
      });
    } finally {
      setDangGui(null);
      setDangKhoa(null);
    }
  };

  const users = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.users}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Quản lý quyền và trạng thái tài khoản. Trang này không xem được nội dung của người dùng.
          </p>
        </div>
        {data && (
          <span className="text-xs font-semibold text-[#5A6A85] dark:text-[#8B98AB]">
            {users.length}/{data.total} tài khoản
          </span>
        )}
      </div>

      <div className="p-4 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-[#5A6A85] absolute left-3 top-1/2 -translate-y-1/2" />
          <label htmlFor="admin-user-search" className="sr-only">
            Tìm tài khoản
          </label>
          <input
            id="admin-user-search"
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo email hoặc tên hiển thị…"
            className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white focus:outline-none focus:ring-2 focus:ring-[#2563A6]"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto justify-end">
          <Filter className="w-3.5 h-3.5 text-[#5A6A85]" />
          <label htmlFor="admin-role-filter" className="sr-only">
            Lọc theo vai trò
          </label>
          <select
            id="admin-role-filter"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-1.5 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white font-medium"
          >
            <option value="">Tất cả vai trò</option>
            {VAI_TRO.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <label htmlFor="admin-program-access-filter" className="sr-only">
            {t.admin.userTable.programAccess}
          </label>
          <select
            id="admin-program-access-filter"
            value={programAccessFilter}
            onChange={(e) => setProgramAccessFilter(e.target.value as AdminProgramAccessLevel | '')}
            aria-label={t.admin.userTable.programAccess}
            className="px-3 py-1.5 text-xs rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] text-[#0F1F38] dark:text-white font-medium"
          >
            {PROGRAM_ACCESS_LEVELS.map((level) => (
              <option key={level || 'all'} value={level}>
                {level === ''
                  ? t.admin.userTable.programAccessAll
                  : level === 'A'
                    ? t.admin.userTable.programAccessVerified
                    : level === 'B'
                      ? t.admin.userTable.programAccessPending
                      : t.admin.userTable.programAccessOutside}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading && <AdminLoading label="Đang tải danh sách tài khoản…" />}
      {error && <AdminError message={error} onRetry={reload} />}
      {data && users.length === 0 && (
        <AdminEmpty
          title="Không có tài khoản nào khớp"
          hint={tuKhoa || roleFilter || programAccessFilter ? 'Thử bỏ bớt bộ lọc.' : 'Chưa có ai đăng ký.'}
        />
      )}

      {users.length > 0 && (
        <div className="rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#EDF2FB] dark:bg-[#0A1628] border-b border-[#D5DDEB] dark:border-[#1A2A42] text-[#5A6A85] dark:text-[#8B98AB] font-medium text-[10px]">
                <tr>
                  <th scope="col" className="p-4">{t.admin.userTable.user}</th>
                  <th scope="col" className="p-4">{t.admin.userTable.role}</th>
                  <th scope="col" className="p-4">{t.admin.userTable.programAccess}</th>
                  <th scope="col" className="p-4">Nguồn / Lượt chạy</th>
                  <th scope="col" className="p-4">{t.admin.userTable.status}</th>
                  <th scope="col" className="p-4">Đồng bộ gần nhất</th>
                  <th scope="col" className="p-4 text-right">{t.admin.userTable.actions}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42] font-medium text-[#0F1F38] dark:text-slate-200">
                {users.map((u) => {
                  const laChinhMinh = u.id === nguoiDangDangNhap?.id;
                  const dangXuLy = dangGui === u.id;
                  return (
                    <tr
                      key={u.id}
                      className="hover:bg-[#EDF2FB]/50 dark:hover:bg-[#0A1628]/40 transition-colors"
                    >
                      <td className="p-4">
                        <div className="font-bold">{u.displayName || u.email.split('@')[0]}</div>
                        <div className="text-[11px] text-[#5A6A85]">{u.email}</div>
                      </td>
                      <td className="p-4">
                        <select
                          value={u.role}
                          disabled={laChinhMinh || dangXuLy}
                          onChange={(e) => goiCapNhat(u, { role: e.target.value as AdminRole })}
                          title={
                            laChinhMinh
                              ? 'Không tự đổi quyền của chính mình được'
                              : 'Đổi vai trò'
                          }
                          className="px-2 py-1 rounded-lg text-[10px] font-bold uppercase border border-[#D5DDEB] dark:border-[#1A2A42] bg-white dark:bg-[#0A1628] disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {VAI_TRO.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center px-2 py-1 rounded-lg text-[10px] font-bold ${
                            u.programAccessLevel === 'A'
                              ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300'
                              : u.programAccessLevel === 'B'
                                ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300'
                                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}
                          title={
                            u.programAccessLevel === 'A'
                              ? t.admin.userTable.programAccessVerified
                              : u.programAccessLevel === 'B'
                                ? t.admin.userTable.programAccessPending
                                : t.admin.userTable.programAccessOutside
                          }
                        >
                          {u.programAccessLevel}
                        </span>
                        <div className="mt-1 text-[10px] text-[#5A6A85]">
                          {u.programAccessLevel === 'A'
                            ? t.admin.userTable.programAccessVerifiedShort
                            : u.programAccessLevel === 'B'
                              ? t.admin.userTable.programAccessPendingShort
                              : t.admin.userTable.programAccessOutsideShort}
                        </div>
                        <input
                          aria-label={`Cohort của ${u.email}`}
                          defaultValue={u.programCohortSlug ?? ''}
                          disabled={dangXuLy}
                          onBlur={(event) => {
                            const next = event.target.value.trim();
                            if (next !== (u.programCohortSlug ?? '')) {
                              void goiCapNhat(u, { programCohortSlug: next });
                            }
                          }}
                          placeholder="cohort-iii"
                          className="mt-2 w-28 rounded-lg border border-[#D5DDEB] bg-white px-2 py-1 text-[10px] dark:border-[#1A2A42] dark:bg-[#0A1628]"
                        />
                      </td>
                      <td className="p-4 text-[#5A6A85]">
                        {u.connectionCount} nguồn · {u.runCount} lượt
                      </td>
                      <td className="p-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${
                            u.isActive
                              ? 'bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300'
                              : 'bg-rose-100 dark:bg-rose-950/80 text-rose-800 dark:text-rose-300'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${u.isActive ? 'bg-emerald-500' : 'bg-rose-500'}`}
                          />
                          {u.isActive ? 'đang hoạt động' : 'đã khoá'}
                        </span>
                      </td>
                      <td className="p-4 text-[#5A6A85]">{ngayNgan(u.lastSyncedAt)}</td>
                      <td className="p-4 text-right">
                        <button
                          disabled={laChinhMinh || dangXuLy}
                          onClick={() =>
                            u.isActive ? setDangKhoa(u) : goiCapNhat(u, { isActive: true })
                          }
                          title={laChinhMinh ? 'Không tự khoá tài khoản của mình được' : undefined}
                          className={`p-1.5 rounded-lg border text-xs font-semibold inline-flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                            u.isActive
                              ? 'border-rose-200 dark:border-rose-900 text-rose-600 hover:bg-rose-50'
                              : 'border-emerald-200 dark:border-emerald-900 text-emerald-600 hover:bg-emerald-50'
                          }`}
                        >
                          {u.isActive ? (
                            <>
                              <UserX className="w-3.5 h-3.5" /> Khoá
                            </>
                          ) : (
                            <>
                              <UserCheck className="w-3.5 h-3.5" /> Mở lại
                            </>
                          )}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {dangKhoa && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-[#122038] rounded-2xl border border-[#D5DDEB] dark:border-[#1A2A42] p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600 dark:text-rose-400">
              <AlertCircle className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-bold text-[#0F1F38] dark:text-white">
                {t.admin.userTable.suspendConfirmTitle}
              </h3>
            </div>

            <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB] leading-relaxed">
              Tài khoản bị khoá mất quyền ngay lập tức, kể cả khi token đăng nhập còn hạn. Dữ liệu
              và nhật ký của họ được giữ nguyên.
            </p>

            <div className="p-3 rounded-xl bg-[#EDF2FB] dark:bg-[#0A1628] text-xs font-medium space-y-1">
              <div>
                <span className="text-[#5A6A85]">Tài khoản:</span>{' '}
                <strong className="text-[#0F1F38] dark:text-white">
                  {dangKhoa.displayName || dangKhoa.email}
                </strong>
              </div>
              <div>
                <span className="text-[#5A6A85]">Email:</span>{' '}
                <span className="text-[#0F1F38] dark:text-white">{dangKhoa.email}</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setDangKhoa(null)}>
                {t.actions.cancel}
              </Button>
              <Button
                onClick={() => goiCapNhat(dangKhoa, { isActive: false })}
                className="bg-rose-600 hover:bg-rose-700 text-white font-bold"
              >
                Khoá tài khoản
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
