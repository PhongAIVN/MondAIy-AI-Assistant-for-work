// Hook nạp dữ liệu cho các trang admin. Ba trang đầu đều lặp lại cùng một
// vòng loading → data → error nên gom vào đây thay vì chép ba lần.
//
// Không dùng thư viện data-fetching: dự án chưa có sẵn cái nào, mà thêm một
// dependency chỉ cho năm trang admin thì đắt hơn ba chục dòng này.

import { useCallback, useEffect, useState } from 'react';
import { ApiError } from './apiClient';
import { useAuthStore } from '../stores/useAuthStore';

export type AdminDataState<T> = {
  data: T | null;
  loading: boolean;
  /** Thông báo tiếng người, đã phân biệt hết phiên với lỗi thật. */
  error: string | null;
  reload: () => void;
};

const moTaLoi = (err: unknown): string => {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục.';
    if (err.status === 403) return 'Tài khoản này không có quyền quản trị.';
    return err.message;
  }
  // Fetch ném TypeError khi không nối được máy chủ — khác hẳn lỗi 4xx/5xx.
  return 'Không gọi được máy chủ. Kiểm tra kết nối rồi thử lại.';
};

export function useAdminData<T>(
  fetcher: (accessToken: string) => Promise<T>,
  deps: unknown[] = [],
): AdminDataState<T> {
  const accessToken = useAuthStore((state) => state.accessToken);
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!accessToken) return;
    let huy = false;
    setLoading(true);
    setError(null);

    fetcher(accessToken)
      .then((ketQua) => {
        // Người dùng có thể đã rời trang trước khi request về — set state lúc
        // đó là cảnh báo "update on unmounted component" và ghi đè dữ liệu mới.
        if (!huy) setData(ketQua);
      })
      .catch((err) => {
        if (!huy) setError(moTaLoi(err));
      })
      .finally(() => {
        if (!huy) setLoading(false);
      });

    return () => {
      huy = true;
    };
    // fetcher được tạo lại mỗi lần render nên không đưa vào deps — trang tự
    // khai deps thật của nó (từ khoá tìm kiếm, bộ lọc, số ngày).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, nonce, ...deps]);

  return { data, loading, error, reload };
}
