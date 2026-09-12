import React from 'react';
import { Calendar as CalendarIcon, ShieldAlert } from 'lucide-react';
import { ProgramSyncPanel } from '../components/calendar/ProgramSyncPanel';
import { CalendarWeekPanel } from '../components/calendar/CalendarWeekPanel';

export const CalendarPage: React.FC = () => {
  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-[var(--color-primary)] mb-1">
            <CalendarIcon className="w-4 h-4" /> Program Schedule
          </div>
          <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] font-heading">
            Program Calendar
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)] mt-1">
            Aggregated schedule of deadlines, office hours, and team check-ins with source attribution.
          </p>
        </div>

        <div className="flex items-center gap-2 bg-[#DFF0E6] dark:bg-[#0F1F38] border border-[#C4DDCB] dark:border-[#1E2E4A] p-2.5 rounded-xl text-xs text-[#2A6B4F] dark:text-[#8CC3A2] font-bold">
          <ShieldAlert className="w-4 h-4 shrink-0" /> User Control: No calendar event is automatically created without explicit confirmation.
        </div>
      </div>

      {/* Đồng bộ lịch chương trình sang lịch cá nhân (ADR-009). */}
      <ProgramSyncPanel />

      {/* Lịch tuần thật, đọc từ bộ nhớ đệm rồi làm mới ở nền (FR-102).
          Trước đây chỗ này là danh sách minh hoạ cứng trong mã. */}
      <CalendarWeekPanel />
    </div>
  );
};
