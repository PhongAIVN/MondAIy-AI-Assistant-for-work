export const MAX_TASK_IMPORT_FILES = 5;
export const MAX_TASK_IMPORT_FILE_BYTES = 200 * 1024;

export type TaskImportFile = {
  uri: string;
  name: string;
  mimeType: string;
  size: number | null;
};

export type ShareIntentFileLike = {
  path: string;
  fileName: string;
  mimeType: string;
  size: number | null;
};

const taskFileExtension = (name: string): string => name.trim().toLowerCase().split('.').pop() || '';

export const normalizeSharedTaskFiles = (files: ShareIntentFileLike[]): TaskImportFile[] => files.map((file) => ({
  uri: file.path,
  name: file.fileName,
  mimeType: file.mimeType || 'application/octet-stream',
  size: file.size,
}));

export const validateTaskImportFiles = (files: TaskImportFile[]): string | null => {
  if (!files.length) return 'Hãy chọn ít nhất một tệp DOCX hoặc Excel.';
  if (files.length > MAX_TASK_IMPORT_FILES) return 'Mỗi lần chỉ nhập tối đa 5 tệp.';
  for (const file of files) {
    if (!['docx', 'xlsx'].includes(taskFileExtension(file.name))) {
      return `Tệp "${file.name}" không phải DOCX hoặc Excel.`;
    }
    if (file.size !== null && file.size > MAX_TASK_IMPORT_FILE_BYTES) {
      return `Tệp "${file.name}" vượt quá giới hạn 200 KB.`;
    }
  }
  return null;
};
