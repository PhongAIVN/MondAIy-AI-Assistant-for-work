// Màn hình chờ trong lúc khôi phục phiên đăng nhập.
//
// Tồn tại vì một lý do cụ thể: trước đây hai route guard trả về `null` khi
// đang bootstrap, nên nếu bước khôi phục phiên chậm hoặc treo thì người dùng
// chỉ thấy một màn hình trống trơn đúng màu nền — không phân biệt được "đang
// tải", "mất mạng" hay "app hỏng". Trên điện thoại đó là kiểu hỏng tệ nhất vì
// không có console để tự đoán.

import React from 'react';

export const BootstrapScreen: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    className="flex min-h-dvh items-center justify-center bg-[var(--color-app-bg)]"
  >
    <span
      aria-hidden
      className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-border-strong)] border-t-[var(--color-primary)]"
    />
    <span className="sr-only">Đang tải…</span>
  </div>
);
