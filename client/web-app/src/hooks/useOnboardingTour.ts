import { driver, type Config, type DriveStep } from 'driver.js';
import 'driver.js/dist/driver.css';
import { useCallback } from 'react';

const STORAGE_PREFIX = 'mondaiy_onboarding_tour_seen_';

/** Đã xem tour này chưa, dựa trên cờ lưu trong localStorage theo tourId. */
export function hasSeenTour(tourId: string): boolean {
  if (typeof window === 'undefined') return true;
  return localStorage.getItem(STORAGE_PREFIX + tourId) === '1';
}

/** Đánh dấu tour đã xem, để không tự động chạy lại lần sau. */
export function markTourSeen(tourId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_PREFIX + tourId, '1');
}

/** Xoá cờ đã xem, dùng khi user bấm "Xem lại hướng dẫn" trong Settings. */
export function resetTourSeen(tourId: string): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(STORAGE_PREFIX + tourId);
}

/**
 * Hook chạy driver.js để highlight tuần tự các phần tử UI cho người dùng mới.
 * Không tự quyết định khi nào chạy — page gọi startTour() theo điều kiện riêng
 * (ví dụ: chỉ khi hasSeenTour(tourId) === false).
 */
export function useOnboardingTour(tourId: string) {
  const startTour = useCallback(
    (steps: DriveStep[], options?: Omit<Config, 'steps'>) => {
      const driverObj = driver({
        showProgress: true,
        animate: true,
        allowClose: true,
        overlayOpacity: 0.65,
        popoverClass: 'mondaiy-tour',
        // Nhiều mục tiêu chỉ hiện có điều kiện (panel đóng/mở, banner lỗi, dialog) —
        // bỏ qua bước đó thay vì kẹt tour khi phần tử không có trong DOM. Chỉ còn
        // là lưới an toàn cuối — luồng điều hướng thật đã tự dò DOM riêng
        // (xem advanceWhenReady trong lib/tours/appTour.ts), không dựa vào cờ này.
        skipMissingElement: true,
        // Mũi tên trái/phải hay Enter mặc định tự nhảy bước, bỏ qua onNextClick
        // của mình (nơi thật sự điều hướng trang) — tắt hẳn, chỉ cho phép Next
        // qua đúng nút bấm trong popover.
        allowKeyboardControl: false,
        ...options,
        steps,
        onDestroyed: (...args) => {
          markTourSeen(tourId);
          options?.onDestroyed?.(...args);
        },
      });
      driverObj.drive();
      return driverObj;
    },
    [tourId],
  );

  return { startTour, hasSeenTour: () => hasSeenTour(tourId), resetTourSeen: () => resetTourSeen(tourId) };
}
