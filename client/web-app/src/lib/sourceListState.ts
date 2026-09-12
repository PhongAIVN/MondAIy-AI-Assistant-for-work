export type SourceListResult<T> = {
  sources: T[];
  unsupported?: string;
  warnings?: string[];
};

/** Chuyển response source API thành state hiển thị, giữ cảnh báo partial. */
export function loadedSourceListState<T>(result: SourceListResult<T>) {
  return {
    loading: false as const,
    items: result.sources,
    unsupported: result.unsupported,
    warnings: result.warnings,
  };
}

/** Nhận cả contract namespaced mới và source Gmail cũ đã lưu. */
export const isPrimaryGmailSource = (sourceId: string): boolean =>
  sourceId === 'gmail:INBOX' || sourceId === 'INBOX';
