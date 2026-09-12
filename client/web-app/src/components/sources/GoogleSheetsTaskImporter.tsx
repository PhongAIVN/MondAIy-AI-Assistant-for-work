import React, { useEffect, useRef, useState } from 'react';

import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { ApiError } from '../../lib/apiClient';
import { createTaskFromSuggestion } from '../../lib/tasksApi';
import { scanGoogleSheetTasks, type GoogleSheetsTaskProposal } from '../../lib/googleSheetsApi';
import { isGoogleSheetsUrl } from '../../lib/googleSheetsIntent';

type Props = { accessToken: string; initialSpreadsheetUrl?: string; initialSheetName?: string };

export const GoogleSheetsTaskImporter: React.FC<Props> = ({ accessToken, initialSpreadsheetUrl = '', initialSheetName = '' }) => {
  const [spreadsheetUrl, setSpreadsheetUrl] = useState(initialSpreadsheetUrl);
  const [sheetName, setSheetName] = useState(initialSheetName);
  const [availableSheetNames, setAvailableSheetNames] = useState<string[]>([]);
  const [proposals, setProposals] = useState<GoogleSheetsTaskProposal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Record<string, boolean>>({});
  const urlInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (initialSpreadsheetUrl) setSpreadsheetUrl(initialSpreadsheetUrl);
    if (initialSheetName) setSheetName(initialSheetName);
  }, [initialSheetName, initialSpreadsheetUrl]);

  const scan = async () => {
    if (!isGoogleSheetsUrl(spreadsheetUrl)) {
      setError('URL Google Sheets chưa đúng. Hãy dán đường dẫn dạng https://docs.google.com/spreadsheets/d/...');
      urlInputRef.current?.focus();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await scanGoogleSheetTasks(spreadsheetUrl, sheetName, accessToken);
      setSheetName(response.sheetName);
      setAvailableSheetNames(response.availableSheetNames ?? []);
      setProposals(response.proposals);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Không đọc được Google Sheet.');
    } finally {
      setLoading(false);
    }
  };

  const addTask = async (proposal: GoogleSheetsTaskProposal) => {
    try {
      await createTaskFromSuggestion(
        {
          title: proposal.title,
          detail: [proposal.detail, proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : '']
            .filter(Boolean)
            .join('\n'),
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
        <h2 className="font-heading text-sm font-bold text-[var(--color-text-primary)]">Nhận diện task từ Google Sheets</h2>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
          Chỉ đọc bảng. Task chỉ được tạo ở trạng thái đề xuất sau khi bạn bấm xác nhận.
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1fr_180px_auto]">
        <input
          ref={urlInputRef}
          aria-label="URL Google Sheets"
          value={spreadsheetUrl}
          onChange={(event) => setSpreadsheetUrl(event.target.value)}
          placeholder="Dán URL Google Sheets"
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none"
        />
        {availableSheetNames.length > 0 ? (
          <select
            aria-label="Tên sheet"
            value={sheetName}
            onChange={(event) => setSheetName(event.target.value)}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none"
          >
            {availableSheetNames.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        ) : (
          <input
            aria-label="Tên sheet"
            value={sheetName}
            onChange={(event) => setSheetName(event.target.value)}
            placeholder="Tự nhận diện tab"
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none"
          />
        )}
        <Button onClick={() => void scan()} disabled={loading || !spreadsheetUrl.trim()}>
          {loading ? 'Đang đọc…' : 'Đọc & nhận diện'}
        </Button>
      </div>
      {error && <p role="alert" className="text-sm text-[var(--color-danger)]">{error}</p>}
      {error && (
        <p className="text-xs text-[var(--color-text-secondary)]">
          Kiểm tra lại URL bảng và tên tab. Bạn có thể sửa hai ô trên rồi đọc lại.
        </p>
      )}
      {availableSheetNames.length > 0 && <p className="text-xs text-[var(--color-text-secondary)]">Đã chọn tab “{sheetName}”. Nếu chưa đúng, chọn tab khác rồi đọc lại.</p>}
      <div className="space-y-3">
        {proposals.map((proposal) => (
          <div key={proposal.externalKey} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-[var(--color-text-primary)]">{proposal.title}</h3>
              {proposal.needsConfirmation && <Badge variant="warning">Cần bạn xác nhận người phụ trách</Badge>}
              {!proposal.needsConfirmation && <Badge variant="success">Đã nhận ra là việc của bạn</Badge>}
            </div>
            {proposal.detail && <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{proposal.detail}</p>}
            <p className="mt-2 text-xs text-[var(--color-text-muted)]">
              {proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : 'Chưa có người phụ trách'} · Dòng {proposal.rowNumber}
            </p>
            {proposal.clarificationQuestion && (
              <p className="mt-2 rounded-lg bg-[var(--color-warning-soft)] p-2 text-xs text-[var(--color-text-secondary)]">{proposal.clarificationQuestion}</p>
            )}
            <div className="mt-3 flex items-center gap-2">
              {created[proposal.externalKey] ? (
                <Badge variant="success">Đã thêm vào task đề xuất</Badge>
              ) : (
                <Button size="xs" onClick={() => void addTask(proposal)}>
                  {proposal.needsConfirmation ? 'Xác nhận & thêm task' : 'Thêm task'}
                </Button>
              )}
              <a href={proposal.sourceUrl} target="_blank" rel="noreferrer" className="text-xs text-[var(--color-primary)] hover:underline">
                Mở dòng nguồn
              </a>
            </div>
          </div>
        ))}
        {!loading && proposals.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">Chưa có task nào được nhận diện.</p>}
      </div>
    </Card>
  );
};
