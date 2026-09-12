import React, { useRef, useState } from 'react';
import { FilePlus2, FileSpreadsheet, Link2, LoaderCircle, MonitorUp, ShieldCheck } from 'lucide-react';
import { Dialog } from '../ui/Dialog';
import { ApiError } from '../../lib/apiClient';
import { uploadExcelTaskFile } from '../../lib/excelTasksApi';
import { scanGoogleSheetTasks } from '../../lib/googleSheetsApi';
import { scanGoogleDocTasks } from '../../lib/googleDocsApi';
import { isGoogleSheetsUrl } from '../../lib/googleSheetsIntent';
import { isGoogleDocsUrl } from '../../lib/googleDocsIntent';
import { normalizeDocProposal, normalizeSheetProposal, type NormalizedTaskProposal } from '../../lib/googleTaskProposals';
import { createTaskFromSuggestion } from '../../lib/tasksApi';

const MAX_FILE_BYTES = 200 * 1024;
type Step = 'choose' | 'local' | 'google' | 'results';

export const TaskImportTool: React.FC<{ accessToken: string }> = ({ accessToken }) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<Step>('choose');
  const [url, setUrl] = useState('');
  const [proposals, setProposals] = useState<NormalizedTaskProposal[]>([]);
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);
  const [created, setCreated] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setStep('choose'); setUrl(''); setProposals([]); setSummary(''); setCreated({}); setError(null); setLoading(false); };
  const close = () => { setOpen(false); reset(); };
  const showResults = (items: NormalizedTaskProposal[], message: string) => { setProposals(items); setSummary(message); setStep('results'); };
  const upload = async (files: FileList | null) => {
    const selected = Array.from(files ?? []);
    if (!selected.length) return;
    setError(null);
    if (selected.length > 5) { setError('Mỗi lần chỉ chọn tối đa 5 tệp.'); return; }
    if (selected.some((file) => !/\.(xlsx|docx)$/i.test(file.name))) { setError('Chỉ hỗ trợ tệp .xlsx hoặc .docx.'); return; }
    if (selected.some((file) => file.size > MAX_FILE_BYTES)) { setError('Mỗi tệp tối đa 200 KB. Hãy rút gọn tệp trước khi gửi.'); return; }
    setLoading(true);
    try {
      const response = await uploadExcelTaskFile(selected, accessToken);
      showResults(response.proposals.map(normalizeSheetProposal), response.agentResponse || `Đã đọc ${response.fileNames.join(', ')}.`);
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'Không thể phân tích tệp.'); }
    finally { setLoading(false); }
  };
  const analyseGoogle = async () => {
    const source = url.trim();
    if (!source) { setError('Dán link Google Docs hoặc Google Sheets để tiếp tục.'); return; }
    setLoading(true); setError(null);
    try {
      if (isGoogleSheetsUrl(source)) {
        const response = await scanGoogleSheetTasks(source, '', accessToken);
        showResults(response.proposals.map(normalizeSheetProposal), `Đã đọc Google Sheets${response.sheetName ? ` · tab ${response.sheetName}` : ''}.`);
      } else if (isGoogleDocsUrl(source)) {
        const response = await scanGoogleDocTasks({ documentUrl: source }, accessToken);
        showResults(response.proposals.map((item) => normalizeDocProposal(item, response.documentId)), 'Đã đọc Google Docs.');
      } else { setError('Link chưa đúng. Hãy dùng link Google Docs hoặc Google Sheets.'); }
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'Không thể đọc tài liệu Google.'); }
    finally { setLoading(false); }
  };
  const addTask = async (proposal: NormalizedTaskProposal) => {
    try {
      await createTaskFromSuggestion({ title: proposal.title, detail: [proposal.detail, proposal.assignee ? `Người phụ trách: ${proposal.assignee}` : ''].filter(Boolean).join('\n'), dueAt: proposal.dueAt, allDay: proposal.allDay, source: proposal.source }, accessToken);
      setCreated((current) => ({ ...current, [proposal.key]: true }));
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : 'Không thể tạo task.'); }
  };

  return <><button type="button" onClick={() => setOpen(true)} className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-accent-soft)] rounded-lg transition-colors text-xs flex items-center gap-1.5" title="Nhập task từ tệp hoặc Google"><FilePlus2 className="w-4 h-4" /><span className="hidden sm:inline font-semibold">Nhập task</span></button><Dialog isOpen={open} onClose={close} title="Nhập task để MondAIy phân tích" description="Chọn nguồn, hệ thống sẽ đọc ngay và trả về task đề xuất để bạn duyệt." maxWidth="lg"><div className="rounded-xl bg-[var(--color-accent-soft)] p-3 text-xs text-[var(--color-text-secondary)]"><ShieldCheck className="mr-1 inline h-4 w-4 text-[var(--color-success)]" />Không cần viết thêm câu hỏi. Tệp cục bộ không được lưu lại; mỗi tệp tối đa 200 KB.</div>{step === 'choose' && <div className="grid gap-3 sm:grid-cols-2"><button onClick={() => { setStep('local'); setTimeout(() => fileRef.current?.click(), 0); }} className="rounded-2xl border border-[var(--color-border)] p-5 text-left hover:border-[var(--color-primary)] hover:bg-[var(--color-accent-soft)]"><MonitorUp className="h-6 w-6 text-[var(--color-primary)]" /><h4 className="mt-3 font-semibold">Từ máy cá nhân</h4><p className="mt-1 text-xs text-[var(--color-text-secondary)]">Chọn .xlsx hoặc .docx. Vừa chọn xong, MondAIy phân tích ngay.</p></button><button onClick={() => setStep('google')} className="rounded-2xl border border-[var(--color-border)] p-5 text-left hover:border-[var(--color-primary)] hover:bg-[var(--color-accent-soft)]"><Link2 className="h-6 w-6 text-[var(--color-primary)]" /><h4 className="mt-3 font-semibold">Từ Google</h4><p className="mt-1 text-xs text-[var(--color-text-secondary)]">Dán link Google Docs hoặc Google Sheets để MondAIy chỉ đọc và nhận diện task.</p></button></div>}{step === 'local' && <div className="space-y-3"><input ref={fileRef} type="file" multiple accept=".xlsx,.docx" onChange={(event) => { void upload(event.currentTarget.files); event.currentTarget.value = ''; }} className="sr-only"/><button onClick={() => fileRef.current?.click()} disabled={loading} className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-primary)] bg-[var(--color-accent-soft)] px-4 py-8 font-semibold text-[var(--color-primary)] disabled:opacity-60">{loading ? <LoaderCircle className="h-5 w-5 animate-spin" /> : <FileSpreadsheet className="h-5 w-5" />}{loading ? 'Đang phân tích…' : 'Chọn tệp để phân tích ngay'}</button><p className="text-center text-xs text-[var(--color-text-secondary)]">.xlsx hoặc .docx · tối đa 5 tệp · mỗi tệp 200 KB</p></div>}{step === 'google' && <div className="space-y-3"><label className="block text-sm font-medium">Dán link tài liệu<input autoFocus value={url} onChange={(event) => setUrl(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void analyseGoogle(); }} placeholder="https://docs.google.com/..." className="mt-2 block w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none" /></label><button onClick={() => void analyseGoogle()} disabled={loading || !url.trim()} className="inline-flex items-center gap-2 rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{loading && <LoaderCircle className="h-4 w-4 animate-spin" />}{loading ? 'Đang phân tích…' : 'Phân tích link'}</button></div>}{step === 'results' && <div><p className="mb-3 text-sm text-[var(--color-text-secondary)]">{summary} {proposals.length ? `Tìm thấy ${proposals.length} task để bạn duyệt.` : 'Chưa tìm thấy task nào.'}</p><div className="space-y-2">{proposals.map((proposal) => <article key={proposal.key} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3"><h4 className="font-semibold">{proposal.title}</h4>{proposal.detail && <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{proposal.detail}</p>}<p className="mt-2 text-xs text-[var(--color-text-muted)]">{proposal.positionLabel}{proposal.assignee ? ` · ${proposal.assignee}` : ''}</p>{created[proposal.key] ? <p className="mt-3 text-xs font-semibold text-[var(--color-success)]">Đã thêm vào task đề xuất</p> : <button onClick={() => void addTask(proposal)} className="mt-3 rounded-lg bg-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-white">{proposal.needsConfirmation ? 'Xác nhận & thêm task' : 'Thêm task'}</button>}</article>)}</div></div>}{error && <p role="alert" className="text-sm text-[var(--color-danger)]">{error}</p>}</Dialog></>;
};
