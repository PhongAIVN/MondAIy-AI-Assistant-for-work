import React, { useEffect, useState } from 'react';
import { FileText, Table2, FolderSearch, Loader2, ArrowLeft, AlertTriangle, RefreshCw } from 'lucide-react';

import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { ApiError } from '../../lib/apiClient';
import { createTaskFromSuggestion } from '../../lib/tasksApi';
import { listGoogleDriveFiles, type GoogleDriveFile, type GoogleDriveFileKind } from '../../lib/googleDriveApi';
import { scanGoogleDocTasks } from '../../lib/googleDocsApi';
import { scanGoogleSheetTasksById } from '../../lib/googleSheetsApi';
import { normalizeDocProposal, normalizeSheetProposal, type NormalizedTaskProposal } from '../../lib/googleTaskProposals';

type Props = { accessToken: string };

type KindFilter = GoogleDriveFileKind | 'all';

type Mode = 'closed' | 'list' | 'confirmSheet' | 'results';

type ScanResult = {
  file: GoogleDriveFile;
  proposals: NormalizedTaskProposal[];
  truncated: boolean;
  quotaRemaining: number;
};

const KIND_OPTIONS: { value: KindFilter; label: string }[] = [
  { value: 'all', label: 'Tất cả' },
  { value: 'document', label: 'Google Docs' },
  { value: 'spreadsheet', label: 'Google Sheets' },
];

const fileIcon = (kind: GoogleDriveFileKind) =>
  kind === 'document' ? <FileText className="h-4 w-4 shrink-0 text-[var(--color-primary)]" aria-hidden /> : <Table2 className="h-4 w-4 shrink-0 text-[var(--color-primary)]" aria-hidden />;

const formatModifiedTime = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

export const GoogleDriveFilePicker: React.FC<Props> = ({ accessToken }) => {
  const [mode, setMode] = useState<Mode>('closed');
  const [query, setQuery] = useState('');
  const [kindFilter, setKindFilter] = useState<KindFilter>('all');
  const [files, setFiles] = useState<GoogleDriveFile[]>([]);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  // 'list' = 429 khi duyệt file (slowapi 30/phút, tạm thời, KHÔNG phải hết
  // hạn mức đọc nội dung trong ngày) · 'scan' = 429 khi đọc nội dung Docs/
  // Sheets (document_read_quota, 429 kèm giờ reset trong ngày). Hai loại
  // khác bản chất nên không dùng chung một câu tiêu đề.
  const [quotaInfo, setQuotaInfo] = useState<{ source: 'list' | 'scan'; message: string } | null>(null);
  const quotaLocked = quotaInfo !== null;

  const [selectedFile, setSelectedFile] = useState<GoogleDriveFile | null>(null);
  const [sheetNameDraft, setSheetNameDraft] = useState('Backlog');
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [created, setCreated] = useState<Record<string, boolean>>({});

  const fetchFiles = async (reset: boolean) => {
    if (quotaLocked) return;
    setListLoading(true);
    setListError(null);
    try {
      const response = await listGoogleDriveFiles(
        { q: query, kind: kindFilter, pageToken: reset ? undefined : nextPageToken, pageSize: 20 },
        accessToken,
      );
      setFiles((current) => (reset ? response.files : [...current, ...response.files]));
      setNextPageToken(response.nextPageToken);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        setQuotaInfo({ source: 'list', message: caught.message });
      } else {
        setListError(caught instanceof ApiError ? caught.message : 'Không tải được danh sách file Drive.');
      }
    } finally {
      setListLoading(false);
    }
  };

  const openPicker = () => {
    setMode('list');
    if (files.length === 0 && !quotaLocked) void fetchFiles(true);
  };

  useEffect(() => {
    if (mode !== 'list' || quotaLocked) return;
    void fetchFiles(true);
    // Chạy lại khi đổi bộ lọc loại file; đổi ô tìm dùng nút "Tìm" riêng để
    // tránh gọi API theo từng phím gõ.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kindFilter]);

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void fetchFiles(true);
  };

  const backToList = () => {
    setMode('list');
    setSelectedFile(null);
    setScanResult(null);
    setScanError(null);
  };

  const runScan = async (file: GoogleDriveFile, sheetName?: string) => {
    if (quotaLocked) return;
    setScanLoading(true);
    setScanError(null);
    try {
      if (file.kind === 'document') {
        const response = await scanGoogleDocTasks({ documentId: file.id }, accessToken);
        setScanResult({
          file,
          proposals: response.proposals.map((proposal) => normalizeDocProposal(proposal, response.documentId)),
          truncated: response.truncated,
          quotaRemaining: response.quotaRemaining,
        });
      } else {
        const response = await scanGoogleSheetTasksById(file.id, sheetName || 'Backlog', accessToken);
        setScanResult({
          file,
          proposals: response.proposals.map(normalizeSheetProposal),
          truncated: response.truncated,
          quotaRemaining: response.quotaRemaining,
        });
      }
      setMode('results');
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 429) {
        setQuotaInfo({ source: 'scan', message: caught.message });
        setMode('list');
      } else {
        setScanError(caught instanceof ApiError ? caught.message : 'Không đọc được nội dung file.');
      }
    } finally {
      setScanLoading(false);
    }
  };

  const handlePick = (file: GoogleDriveFile) => {
    setSelectedFile(file);
    setScanError(null);
    if (file.kind === 'spreadsheet') {
      setSheetNameDraft('Backlog');
      setMode('confirmSheet');
    } else {
      void runScan(file);
    }
  };

  const addTask = async (proposal: NormalizedTaskProposal) => {
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
      setCreated((current) => ({ ...current, [proposal.key]: true }));
    } catch (caught) {
      setScanError(caught instanceof ApiError ? caught.message : 'Không thể tạo task.');
    }
  };

  if (mode === 'closed') {
    return (
      <Card className="space-y-3">
        <div>
          <h2 className="font-heading text-sm font-bold text-[var(--color-text-primary)]">Nhận diện task từ Google Drive</h2>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
            Chọn thẳng một file Docs hoặc Sheets từ Drive của bạn — không cần dán URL.
          </p>
        </div>
        <Button icon={<FolderSearch className="h-3.5 w-3.5" />} onClick={openPicker}>
          Duyệt file trong Drive
        </Button>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-sm font-bold text-[var(--color-text-primary)]">Nhận diện task từ Google Drive</h2>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
            Chọn thẳng một file Docs hoặc Sheets từ Drive của bạn — không cần dán URL.
          </p>
        </div>
        <Button variant="ghost" size="xs" onClick={() => setMode('closed')}>
          Thu gọn
        </Button>
      </div>

      {quotaInfo && (
        <div role="alert" className="flex items-start gap-2 rounded-lg bg-[var(--color-danger-soft)] p-3 text-xs text-[var(--color-danger)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div>
            <p className="font-semibold">
              {quotaInfo.source === 'scan'
                ? 'Đã hết lượt đọc Google Docs/Sheets hôm nay.'
                : 'Đang duyệt Drive quá nhanh — chờ một chút rồi thử lại.'}
            </p>
            <p className="mt-0.5">{quotaInfo.message}</p>
          </div>
        </div>
      )}

      {mode === 'list' && (
        <div className="space-y-3">
          <form onSubmit={handleSearchSubmit} className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input
              aria-label="Tìm file Drive"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm theo tên file…"
              disabled={quotaLocked}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none"
            />
            <Button type="submit" variant="outline" size="sm" disabled={quotaLocked || listLoading}>
              Tìm
            </Button>
          </form>

          <div className="flex flex-wrap gap-2" role="group" aria-label="Lọc theo loại file">
            {KIND_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                aria-pressed={kindFilter === option.value}
                disabled={quotaLocked}
                onClick={() => setKindFilter(option.value)}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  kindFilter === option.value
                    ? 'border-[var(--color-primary)] bg-[var(--color-primary)] text-[var(--color-on-primary)]'
                    : 'border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)]'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {listError && <p role="alert" className="text-sm text-[var(--color-danger)]">{listError}</p>}

          <div className="space-y-2">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  {fileIcon(file.kind)}
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">{file.name}</p>
                    <p className="text-[11px] text-[var(--color-text-muted)]">
                      {file.kind === 'document' ? 'Google Docs' : 'Google Sheets'} · Sửa lần cuối {formatModifiedTime(file.modifiedTime)}
                    </p>
                  </div>
                </div>
                <Button size="xs" onClick={() => handlePick(file)} disabled={quotaLocked}>
                  Chọn
                </Button>
              </div>
            ))}
            {!listLoading && files.length === 0 && !listError && (
              <p className="text-xs text-[var(--color-text-muted)]">Không tìm thấy file nào.</p>
            )}
            {listLoading && (
              <p className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Đang tải danh sách file…
              </p>
            )}
          </div>

          {nextPageToken && !listLoading && (
            <Button variant="outline" size="sm" onClick={() => void fetchFiles(false)} disabled={quotaLocked}>
              Xem thêm
            </Button>
          )}
        </div>
      )}

      {mode === 'confirmSheet' && selectedFile && (
        <div className="space-y-3">
          <Button variant="ghost" size="xs" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={backToList}>
            Chọn file khác
          </Button>
          <p className="text-sm text-[var(--color-text-primary)]">
            Đọc bảng <span className="font-semibold">{selectedFile.name}</span> — tab nào?
          </p>
          <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
            <input
              aria-label="Tên sheet"
              value={sheetNameDraft}
              onChange={(event) => setSheetNameDraft(event.target.value)}
              placeholder="Tên tab, ví dụ Backlog"
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none"
            />
            <Button onClick={() => void runScan(selectedFile, sheetNameDraft)} disabled={scanLoading || !sheetNameDraft.trim()}>
              {scanLoading ? 'Đang đọc…' : 'Đọc & nhận diện'}
            </Button>
          </div>
          {scanError && <p role="alert" className="text-sm text-[var(--color-danger)]">{scanError}</p>}
        </div>
      )}

      {mode === 'results' && selectedFile && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Button variant="ghost" size="xs" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={backToList}>
              Chọn file khác
            </Button>
            <span className="truncate text-xs font-medium text-[var(--color-text-secondary)]">{selectedFile.name}</span>
          </div>

          {scanLoading && (
            <p className="flex items-center gap-2 text-xs text-[var(--color-text-muted)]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Đang đọc…
            </p>
          )}

          {scanResult?.truncated && (
            <div role="status" className="flex items-start gap-2 rounded-lg bg-[var(--color-warning-soft)] p-3 text-xs text-[var(--color-text-secondary)]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning)]" aria-hidden />
              <p>Tài liệu quá dài, hệ thống chỉ đọc được phần đầu. Một số task ở cuối tài liệu có thể chưa được nhận diện.</p>
            </div>
          )}

          {scanResult && scanResult.quotaRemaining <= 5 && (
            <div role="status" className="flex items-center gap-2 rounded-lg bg-[var(--color-info-soft)] p-2.5 text-xs text-[var(--color-info)]">
              <RefreshCw className="h-3.5 w-3.5 shrink-0" aria-hidden />
              <span>Còn {scanResult.quotaRemaining} lượt đọc Docs/Sheets hôm nay.</span>
            </div>
          )}

          {scanError && <p role="alert" className="text-sm text-[var(--color-danger)]">{scanError}</p>}

          <div className="space-y-3">
            {(scanResult?.proposals ?? []).map((proposal) => (
              <div key={proposal.key} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold text-[var(--color-text-primary)]">{proposal.title}</h3>
                  {proposal.needsConfirmation && <Badge variant="warning">Cần bạn xác nhận người phụ trách</Badge>}
                  {!proposal.needsConfirmation && <Badge variant="success">Đã nhận ra là việc của bạn</Badge>}
                </div>
                {proposal.detail && <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{proposal.detail}</p>}
                <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                  {proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : 'Chưa có người phụ trách'} · {proposal.positionLabel}
                </p>
                {proposal.clarificationQuestion && (
                  <p className="mt-2 rounded-lg bg-[var(--color-warning-soft)] p-2 text-xs text-[var(--color-text-secondary)]">{proposal.clarificationQuestion}</p>
                )}
                <div className="mt-3 flex items-center gap-2">
                  {created[proposal.key] ? (
                    <Badge variant="success">Đã thêm vào task đề xuất</Badge>
                  ) : (
                    <Button size="xs" onClick={() => void addTask(proposal)}>
                      {proposal.needsConfirmation ? 'Xác nhận & thêm task' : 'Thêm task'}
                    </Button>
                  )}
                  <a href={proposal.sourceUrl} target="_blank" rel="noreferrer" className="text-xs text-[var(--color-primary)] hover:underline">
                    Mở nguồn
                  </a>
                </div>
              </div>
            ))}
            {!scanLoading && scanResult && scanResult.proposals.length === 0 && (
              <p className="text-xs text-[var(--color-text-muted)]">Chưa có task nào được nhận diện trong file này.</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};
