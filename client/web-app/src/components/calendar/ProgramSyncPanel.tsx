// Đồng bộ lịch chương trình sang lịch cá nhân (ADR-009).
//
// Luồng cố định ba bước: xem trước → tick → đồng bộ. Không có nút "đồng bộ tất
// cả" bỏ qua bước xem: bước xem trước chính là sự xác nhận của người dùng, bỏ nó
// đi là mondaiy tự ghi vào lịch Google của họ.
//
// Ba trạng thái phải hiện rõ, vì không có chúng người dùng không hiểu mình đang
// duyệt cái gì:
//   create    — chưa có trong lịch, tick sẵn
//   update    — ban tổ chức đã đổi sau lần duyệt trước, tick sẵn
//   unchanged — đã khớp, không tick và không cho tick

import React, { useState } from 'react';
import { CalendarPlus, AlertTriangle, Check, RefreshCw, Info } from 'lucide-react';
import { ApiError } from '../../lib/apiClient';
import {
  applyProgramSync,
  previewProgramSync,
  type ProgramSyncPlanItem,
  type ProgramSyncResult,
} from '../../lib/programCalendarApi';
import { useAuthStore } from '../../stores/useAuthStore';
import { useTranslation } from '../../i18n/useTranslation';

const gioVN = (iso: string | null): string =>
  iso ? new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) : '';

/** Thông báo lỗi theo mã trạng thái — mỗi mã là một việc khác nhau người dùng phải làm. */
const moTaLoi = (err: unknown, t: ReturnType<typeof useTranslation>['t']): string => {
  if (err instanceof ApiError) {
    // 403 = chưa khớp danh tính chương trình; 409 = chưa nối Google hoặc thiếu
    // quyền ghi. Backend đã trả câu tiếng người kèm cách sửa nên dùng lại.
    if (err.status === 403 || err.status === 409) return err.message;
    if (err.status === 401) return t.programSync.errorSession;
    return err.message;
  }
  return t.programSync.errorNetwork;
};

export const ProgramSyncPanel: React.FC = () => {
  const accessToken = useAuthStore((state) => state.accessToken);
  const { t } = useTranslation();

  const [items, setItems] = useState<ProgramSyncPlanItem[] | null>(null);
  const [chon, setChon] = useState<Set<number>>(new Set());
  const [gomDaily, setGomDaily] = useState(false);
  const [dangTai, setDangTai] = useState(false);
  const [dangGhi, setDangGhi] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [ketQua, setKetQua] = useState<ProgramSyncResult | null>(null);

  // `giuKetQua` để lần nạp lại ngay sau khi ghi không xoá mất bảng tổng kết
  // người dùng vừa nhận — đó là bằng chứng duy nhất cho biết mốc nào không ghi
  // được.
  const xemTruoc = async (batDaily = gomDaily, giuKetQua = false) => {
    if (!accessToken) return;
    setDangTai(true);
    setLoi(null);
    if (!giuKetQua) setKetQua(null);
    try {
      const data = await previewProgramSync(accessToken, {
        // Bỏ trống là dùng mặc định của backend (workshop, gate, weekly).
        eventTypes: batDaily
          ? ['custom', 'gate_deadline', 'weekly_deadline', 'daily_deadline']
          : undefined,
      });
      setItems(data.items);
      // Tick sẵn đúng những mốc có việc phải làm. Mốc đã khớp không tick — bấm
      // đồng bộ mà ghi lại cả chúng là gọi Google thừa cho không việc gì.
      setChon(
        new Set(
          data.items.filter((item) => item.action !== 'unchanged').map((item) => item.programEventId),
        ),
      );
    } catch (err) {
      setItems(null);
      setLoi(moTaLoi(err, t));
    } finally {
      setDangTai(false);
    }
  };

  const dongBo = async () => {
    if (!accessToken || chon.size === 0) return;
    setDangGhi(true);
    setLoi(null);
    try {
      const result = await applyProgramSync(accessToken, { programEventIds: [...chon] });
      setKetQua(result);
      await xemTruoc(gomDaily, true);
    } catch (err) {
      setLoi(moTaLoi(err, t));
    } finally {
      setDangGhi(false);
    }
  };

  const doiTick = (id: number, action: ProgramSyncPlanItem['action']) => {
    if (action === 'unchanged') return;
    setChon((truoc) => {
      const sau = new Set(truoc);
      if (sau.has(id)) sau.delete(id);
      else sau.add(id);
      return sau;
    });
  };

  const nhanHanhDong: Record<ProgramSyncPlanItem['action'], string> = {
    create: t.programSync.actionCreate,
    update: t.programSync.actionUpdate,
    unchanged: t.programSync.actionUnchanged,
  };

  return (
    <section
      aria-labelledby="program-sync-heading"
      className="rounded-2xl border border-[#D5DDEB] dark:border-[#1A2A42] p-4 sm:p-5 space-y-3"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2
            id="program-sync-heading"
            className="font-bold text-[#0F1F38] dark:text-white flex items-center gap-2"
          >
            <CalendarPlus className="w-4 h-4" /> {t.programSync.title}
          </h2>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{t.programSync.subtitle}</p>
        </div>
        <button
          onClick={() => xemTruoc()}
          disabled={dangTai}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-[#D5DDEB] dark:border-[#1A2A42] text-xs font-semibold text-[#2563A6] disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${dangTai ? 'animate-spin' : ''}`} />
          {items ? t.programSync.refresh : t.programSync.preview}
        </button>
      </div>

      {loi && (
        <p
          role="alert"
          className="text-xs text-red-700 dark:text-red-300 flex items-start gap-1.5 bg-red-50 dark:bg-red-950/30 rounded-xl p-3"
        >
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {loi}
        </p>
      )}

      {ketQua && (
        <div className="text-xs rounded-xl bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-200 p-3 space-y-1">
          <p className="flex items-center gap-1.5 font-semibold">
            <Check className="w-3.5 h-3.5" />
            {t.programSync.resultSummary
              .replace('{created}', String(ketQua.created))
              .replace('{updated}', String(ketQua.updated))}
          </p>
          {/* Mốc ghi hỏng phải hiện ra: im lặng bỏ qua khiến người dùng tin
              lịch đã đủ trong khi không đủ. */}
          {ketQua.skipped.length > 0 && (
            <ul className="list-disc pl-4 text-amber-800 dark:text-amber-200">
              {ketQua.skipped.map((dong) => (
                <li key={dong}>{dong}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {items && (
        <>
          <label className="flex items-center gap-2 text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            <input
              type="checkbox"
              checked={gomDaily}
              onChange={(e) => {
                setGomDaily(e.target.checked);
                void xemTruoc(e.target.checked);
              }}
            />
            {t.programSync.includeDaily}
          </label>

          {items.length === 0 ? (
            <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">{t.programSync.empty}</p>
          ) : (
            <ul className="divide-y divide-[#D5DDEB] dark:divide-[#1A2A42]">
              {items.map((item) => (
                <li key={item.programEventId} className="py-2 flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={chon.has(item.programEventId)}
                    disabled={item.action === 'unchanged'}
                    onChange={() => doiTick(item.programEventId, item.action)}
                    aria-label={item.title}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm text-[#0F1F38] dark:text-white truncate">{item.title}</div>
                    <div className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
                      {gioVN(item.startAt)}
                      {item.endAt ? ` → ${gioVN(item.endAt)}` : ''}
                    </div>
                    <div
                      className={`text-[11px] mt-0.5 ${
                        item.action === 'update'
                          ? 'text-amber-700 dark:text-amber-300'
                          : 'text-[#5A6A85] dark:text-[#8B98AB]'
                      }`}
                    >
                      {nhanHanhDong[item.action]} · {item.reason}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-[11px] text-[#5A6A85] dark:text-[#8B98AB] flex items-start gap-1.5">
              <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {t.programSync.notice}
            </p>
            <button
              onClick={dongBo}
              disabled={dangGhi || chon.size === 0}
              className="shrink-0 px-3 py-1.5 rounded-xl bg-[#2563A6] text-white text-xs font-semibold disabled:opacity-50"
            >
              {t.programSync.confirm.replace('{count}', String(chon.size))}
            </button>
          </div>
        </>
      )}
    </section>
  );
};
