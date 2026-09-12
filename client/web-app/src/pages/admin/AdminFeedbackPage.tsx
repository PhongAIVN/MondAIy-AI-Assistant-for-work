import React, { useCallback, useState } from 'react';
import { MessageSquare, ShieldCheck, Star, Timer } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { getAppRatings, getTelemetry, type AdminAppRatingSummary, type AdminTelemetry } from '../../lib/adminApi';
import { useAdminData } from '../../lib/useAdminData';
import { AdminEmpty, AdminError, AdminLoading } from '../../components/admin/AdminStates';

const CUA_SO = [7, 30, 90];

// Ba mức đánh giá do FeedbackRequest ở backend quy định (src/models/schemas.py).
const MAU_VERDICT: Record<string, string> = {
  helpful: 'bg-emerald-500',
  partly: 'bg-amber-500',
  incorrect: 'bg-rose-500',
};

const NHAN_VERDICT: Record<string, string> = {
  helpful: 'hữu ích',
  partly: 'đúng một phần',
  incorrect: 'sai',
};

export const AdminFeedbackPage: React.FC = () => {
  const { t } = useTranslation();
  const [days, setDays] = useState(30);

  const nap = useCallback((token: string) => getTelemetry(token, days), [days]);
  const { data, loading, error, reload } = useAdminData<AdminTelemetry>(nap, [days]);
  const napRatings = useCallback((token: string) => getAppRatings(token, days), [days]);
  const ratings = useAdminData<AdminAppRatingSummary>(napRatings, [days]);

  const feedback = data?.feedback ?? [];
  const tong = feedback.reduce((sum, f) => sum + f.count, 0);
  const events = data?.events ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.feedback}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Tỷ lệ đánh giá và số liệu vận hành, tổng hợp trên toàn hệ thống.
          </p>
        </div>
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
      </div>

      <div className="p-4 rounded-2xl bg-[#EDF2FB] dark:bg-[#0A1628] border border-[#D5DDEB] dark:border-[#1A2A42] flex items-start gap-3">
        <ShieldCheck className="w-4 h-4 text-[#2563A6] mt-0.5 shrink-0" />
        <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB] leading-relaxed">
          Phần rating sản phẩm hiển thị nhận xét beta mà người dùng chủ động gửi qua popup để đội
          sản phẩm xử lý. Các nội dung email, câu hỏi và câu trả lời cá nhân vẫn không hiển thị.
        </p>
      </div>

      {loading && <AdminLoading label="Đang tải số liệu…" />}
      {error && <AdminError message={error} onRetry={reload} />}

      {ratings.error && <AdminError message={ratings.error} onRetry={ratings.reload} />}

      {ratings.data && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-3 border-b border-[#E1EBFA] dark:border-[#1A2A42]">
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-[#D39B3D] fill-[#D39B3D]" />
              <div>
                <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">Đánh giá sản phẩm beta</h3>
                <p className="text-[11px] text-[#5A6A85]">Phản hồi trực tiếp từ popup hàng ngày</p>
              </div>
            </div>
            <div className="text-sm font-bold text-[#0F1F38] dark:text-white">
              {ratings.data.averageRating ?? '—'} / 5 <span className="text-xs font-normal text-[#5A6A85]">({ratings.data.total} lượt)</span>
            </div>
          </div>
          {ratings.loading && <AdminLoading label="Đang tải rating sản phẩm…" />}
          {ratings.data.items.length === 0 ? (
            <AdminEmpty title="Chưa có rating sản phẩm" hint={`Không có phản hồi nào trong ${days} ngày gần nhất.`} />
          ) : (
            <div className="space-y-3">
              {ratings.data.items.map((item) => (
                <article key={item.id} className="rounded-xl border border-[#E1EBFA] dark:border-[#1A2A42] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-1" aria-label={`${item.rating} trên 5 sao`}>
                      {[1, 2, 3, 4, 5].map((star) => <Star key={star} className={`w-3.5 h-3.5 ${star <= item.rating ? 'fill-[#D39B3D] text-[#D39B3D]' : 'text-slate-300'}`} />)}
                    </div>
                    <time className="text-[10px] text-[#5A6A85]">{new Date(item.createdAt).toLocaleString('vi-VN')}</time>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[#0F1F38] dark:text-slate-200">{item.feedback}</p>
                </article>
              ))}
            </div>
          )}
        </div>
      )}

      {data && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-[#E1EBFA] dark:border-[#1A2A42]">
              <MessageSquare className="w-4 h-4 text-[#2563A6]" />
              <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
                Đánh giá câu trả lời
              </h3>
            </div>

            {tong === 0 ? (
              <AdminEmpty
                title="Chưa có đánh giá nào"
                hint={`Không có lượt đánh giá nào trong ${days} ngày gần nhất.`}
              />
            ) : (
              <div className="space-y-3">
                <div className="text-3xl font-extrabold text-[#0F1F38] dark:text-white">
                  {tong}
                  <span className="text-xs font-semibold text-[#5A6A85] ml-2">lượt đánh giá</span>
                </div>
                {feedback.map((f) => {
                  const phanTram = Math.round((f.count / tong) * 100);
                  return (
                    <div key={f.verdict} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-semibold">
                        <span className="text-[#0F1F38] dark:text-white">
                          {NHAN_VERDICT[f.verdict] ?? f.verdict}
                        </span>
                        <span className="text-[#5A6A85]">
                          {f.count} · {phanTram}%
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-[#EDF2FB] dark:bg-[#0A1628] overflow-hidden">
                        <div
                          className={`h-full rounded-full ${MAU_VERDICT[f.verdict] ?? 'bg-slate-400'}`}
                          style={{ width: `${phanTram}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-5 rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-[#E1EBFA] dark:border-[#1A2A42]">
              <Timer className="w-4 h-4 text-[#2563A6]" />
              <h3 className="text-sm font-bold text-[#0F1F38] dark:text-white">
                Sự kiện đo lường
              </h3>
            </div>

            {events.length === 0 ? (
              <AdminEmpty
                title="Chưa ghi sự kiện nào"
                hint={`Không có sự kiện nào trong ${days} ngày gần nhất.`}
              />
            ) : (
              <div className="overflow-x-auto -mx-1">
                <table className="w-full text-left text-xs">
                  <thead className="text-[#5A6A85] dark:text-[#8B98AB] font-medium text-[10px] border-b border-[#E1EBFA] dark:border-[#1A2A42]">
                    <tr>
                      <th className="py-2 px-1">Sự kiện</th>
                      <th className="py-2 px-1 text-right">Số lượt</th>
                      <th className="py-2 px-1 text-right">Độ trễ TB</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42] font-medium text-[#0F1F38] dark:text-slate-200">
                    {events.map((ev) => (
                      <tr key={ev.name}>
                        <td className="py-2 px-1 text-[11px]">{ev.name}</td>
                        <td className="py-2 px-1 text-right">{ev.count}</td>
                        <td className="py-2 px-1 text-right text-[#5A6A85]">
                          {ev.avgDurationMs !== null ? `${ev.avgDurationMs} ms` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
