import React from 'react';
import { Eye } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { Button } from '../../components/ui/Button';
import { AdminMockBanner } from '../../components/admin/AdminStates';

type BriefingLog = {
  id: string;
  user: string;
  program: string;
  generatedAt: string;
  sourceCoverage: string;
  certainCount: number;
  possibleCount: number;
  askMentorCount: number;
  status: 'active' | 'archived';
};

const MOCK_BRIEFINGS: BriefingLog[] = [
  {
    id: 'brf-901',
    user: 'Alex Nguyen',
    program: 'AI Product Development',
    generatedAt: 'Today, 08:00 AM',
    sourceCoverage: '3 / 4 sources',
    certainCount: 2,
    possibleCount: 1,
    askMentorCount: 0,
    status: 'active',
  },
  {
    id: 'brf-902',
    user: 'Sarah Jenkins',
    program: 'AI Product Development',
    generatedAt: 'Today, 08:00 AM',
    sourceCoverage: '4 / 4 sources',
    certainCount: 3,
    possibleCount: 0,
    askMentorCount: 1,
    status: 'active',
  },
  {
    id: 'brf-903',
    user: 'Marcus Vance',
    program: 'AI Product Development',
    generatedAt: 'Yesterday, 08:00 AM',
    sourceCoverage: '2 / 4 sources',
    certainCount: 1,
    possibleCount: 2,
    askMentorCount: 1,
    status: 'archived',
  },
];

export const AdminBriefingsPage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <AdminMockBanner lyDo="Bảng briefs có thật nhưng nội dung bản tóm lược là dữ liệu cá nhân, PRD §5 không cho admin xem mặc định." />

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-[#0F1F38] dark:text-white tracking-tight">
            {t.admin.briefings}
          </h1>
          <p className="text-xs text-[#5A6A85] dark:text-[#8B98AB]">
            Audit log of daily briefings generated across active scholar accounts.
          </p>
        </div>
      </div>

      {/* Briefings Table */}
      <div className="rounded-2xl bg-white dark:bg-[#122038] border border-[#D5DDEB] dark:border-[#1A2A42] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#EDF2FB] dark:bg-[#0A1628] border-b border-[#D5DDEB] dark:border-[#1A2A42] text-[#5A6A85] dark:text-[#8B98AB] font-medium text-[10px]">
              <tr>
                <th className="p-4">Briefing ID</th>
                <th className="p-4">User</th>
                <th className="p-4">Program</th>
                <th className="p-4">Generated Time</th>
                <th className="p-4">Coverage</th>
                <th className="p-4">Confidence Spread</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E1EBFA] dark:divide-[#1A2A42] font-medium text-[#0F1F38] dark:text-slate-200">
              {MOCK_BRIEFINGS.map((b) => (
                <tr key={b.id} className="hover:bg-[#EDF2FB]/50 dark:hover:bg-[#0A1628]/40 transition-colors">
                  <td className="p-4 font-bold text-[#2563A6]">{b.id}</td>
                  <td className="p-4 font-bold">{b.user}</td>
                  <td className="p-4 text-[#5A6A85]">{b.program}</td>
                  <td className="p-4 text-[#5A6A85]">{b.generatedAt}</td>
                  <td className="p-4 text-[#5A6A85]">{b.sourceCoverage}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold">
                      <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                        Certain: {b.certainCount}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300">
                        Possible: {b.possibleCount}
                      </span>
                      {b.askMentorCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300">
                          Ask Mentor: {b.askMentorCount}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="p-4 text-right">
                    <Button size="xs" variant="outline" className="flex items-center gap-1">
                      <Eye className="w-3 h-3" /> Inspect Evidence
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
