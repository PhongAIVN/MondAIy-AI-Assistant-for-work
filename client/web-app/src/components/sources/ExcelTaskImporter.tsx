import React, { useRef, useState } from 'react';

import { ApiError } from '../../lib/apiClient';
import { uploadExcelTaskFile } from '../../lib/excelTasksApi';
import type { GoogleSheetsTaskProposal } from '../../lib/googleSheetsApi';
import { createTaskFromSuggestion } from '../../lib/tasksApi';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Card } from '../ui/Card';

const MAX_FILE_BYTES = 200 * 1024;

export const ExcelTaskImporter: React.FC<{ accessToken: string }> = ({ accessToken }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [proposals, setProposals] = useState<GoogleSheetsTaskProposal[]>([]);
  const [agentResponse, setAgentResponse] = useState('');
  const [agentWarning, setAgentWarning] = useState<string | null>(null);
  const [searchName, setSearchName] = useState('');
  const [needsNameQuery, setNeedsNameQuery] = useState(false);
  const [suggestedNames, setSuggestedNames] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Record<string, boolean>>({});

  const selectFiles = (candidates: FileList | null) => {
    setError(null);
    setProposals([]);
    setAgentResponse('');
    setAgentWarning(null);
    setNeedsNameQuery(false);
    setSuggestedNames([]);
    setCreated({});
    const selected = Array.from(candidates ?? []);
    if (selected.length === 0) {
      setFiles([]);
      return;
    }
    if (selected.length > 5) {
      setFiles([]);
      setError('Mỗi lần chỉ được tải tối đa 5 tệp.');
      return;
    }
    if (selected.some((candidate) => !/\.(xlsx|docx)$/i.test(candidate.name))) {
      setFiles([]);
      setError('Chỉ hỗ trợ tệp .xlsx hoặc .docx.');
      return;
    }
    if (selected.some((candidate) => candidate.size > MAX_FILE_BYTES)) {
      setFiles([]);
      setError('Tệp vượt quá giới hạn 200 KB.');
      return;
    }
    setFiles(selected);
  };

  const scan = async (nameOverride?: string) => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadExcelTaskFile(files, accessToken, nameOverride ?? searchName);
      setProposals(result.proposals);
      setAgentResponse(result.agentResponse);
      setAgentWarning(result.agentWarning);
      setNeedsNameQuery(result.needsNameQuery);
      setSuggestedNames(result.suggestedNames);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Không thể đọc tệp.');
    } finally {
      setLoading(false);
    }
  };

  const addTask = async (proposal: GoogleSheetsTaskProposal) => {
    try {
      await createTaskFromSuggestion(
        {
          title: proposal.title,
          detail: [proposal.detail, proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : ''].filter(Boolean).join('\n'),
          dueAt: proposal.dueAt,
          allDay: proposal.allDay,
          source: proposal.source,
        },
        accessToken,
      );
      setCreated((current) => ({ ...current, [proposal.externalKey]: true }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Không thể tạo task.');
    }
  };

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="font-heading text-sm font-bold text-[var(--color-text-primary)]">Nhập task từ tệp</h2>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
          Tải tối đa 5 tệp .xlsx hoặc .docx, mỗi tệp tối đa 200 KB. Hệ thống chỉ tìm dòng khớp hoặc gần với tên hồ sơ của bạn; tệp không được lưu lại.
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          aria-label="Tệp công việc"
          type="file"
          multiple
          accept=".xlsx,.docx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={(event) => selectFiles(event.target.files)}
          className="max-w-full text-sm text-[var(--color-text-secondary)]"
        />
        <Button onClick={() => void scan()} disabled={files.length === 0 || loading}>
          {loading ? 'Đang phân tích…' : needsNameQuery ? 'Lọc task theo tên' : 'Phân tích tệp'}
        </Button>
      </div>
      <label className="block space-y-1 text-xs text-[var(--color-text-secondary)]">
        <span>Tên cần tìm <span className="text-[var(--color-text-muted)]">(để trống để dùng tên hồ sơ)</span></span>
        <input
          aria-label="Tên cần tìm"
          value={searchName}
          onChange={(event) => setSearchName(event.target.value)}
          placeholder="Ví dụ: Nguyễn Hồng Đức"
          maxLength={120}
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none"
        />
      </label>
      {files.length > 0 && <p className="text-xs text-[var(--color-text-muted)]">Đã chọn: {files.map((file) => `${file.name} (${Math.ceil(file.size / 1024)} KB)`).join(', ')}</p>}
      {error && <p role="alert" className="text-sm text-[var(--color-danger)]">{error}</p>}
      {agentResponse && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-accent-soft)] p-3">
          <p className="text-xs font-bold text-[var(--color-text-primary)]">Phân tích của trợ lý</p>
          <p className="mt-1 whitespace-pre-wrap text-sm text-[var(--color-text-secondary)]">{agentResponse}</p>
        </div>
      )}
      {agentWarning && <p className="text-xs text-[var(--color-text-muted)]">{agentWarning}</p>}
      {needsNameQuery && (
        <div className="rounded-xl border border-[var(--color-warning)] bg-[var(--color-warning-soft)] p-3 text-xs text-[var(--color-text-secondary)]">
          <p>Chọn một người phụ trách bên dưới hoặc nhập tên ở trên. Tệp đã chọn vẫn được giữ để lọc lại.</p>
          {suggestedNames.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {suggestedNames.map((name) => (
                <button key={name} type="button" onClick={() => { setSearchName(name); void scan(name); }} disabled={loading} className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 hover:bg-[var(--color-accent-soft)] disabled:cursor-not-allowed disabled:opacity-60">
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="space-y-3">
        {proposals.map((proposal) => (
          <div key={proposal.externalKey} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-[var(--color-text-primary)]">{proposal.title}</h3>
              {proposal.needsConfirmation ? <Badge variant="warning">Cần xác nhận</Badge> : <Badge variant="success">Khớp tên hồ sơ</Badge>}
            </div>
            {proposal.detail && <p className="mt-1 whitespace-pre-wrap text-xs text-[var(--color-text-secondary)]">{proposal.detail}</p>}
            <p className="mt-2 text-xs text-[var(--color-text-muted)]">
              {proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : 'Chưa có người phụ trách'} · Dòng {proposal.rowNumber}
            </p>
            {proposal.clarificationQuestion && <p className="mt-2 rounded-lg bg-[var(--color-warning-soft)] p-2 text-xs text-[var(--color-text-secondary)]">{proposal.clarificationQuestion}</p>}
            <div className="mt-3">
              {created[proposal.externalKey] ? <Badge variant="success">Đã thêm vào task đề xuất</Badge> : (
                <Button size="xs" onClick={() => void addTask(proposal)}>
                  {proposal.needsConfirmation ? 'Xác nhận & thêm task' : 'Thêm task'}
                </Button>
              )}
            </div>
          </div>
        ))}
        {!loading && files.length > 0 && proposals.length === 0 && !error && <p className="text-xs text-[var(--color-text-muted)]">Không tìm thấy task nào khớp với tên hồ sơ của bạn.</p>}
      </div>
    </Card>
  );
};
