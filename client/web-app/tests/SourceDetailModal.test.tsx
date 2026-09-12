// @vitest-environment jsdom

import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SourceDetailModal } from '../src/components/briefing/SourceDetailModal';

const mocks = vi.hoisted(() => ({
  closeModal: vi.fn(),
  addToast: vi.fn(),
  language: 'vi' as 'vi' | 'en',
}));

const source = {
  platform: 'Discord',
  timestamp: '2026-08-10 09:00',
  location: '#announcements',
  author: 'Mentor Chen',
  rawContent: 'Nộp báo cáo trước 22:00 Chủ nhật.',
};

vi.mock('../src/stores/useAppStore', () => ({
  useAppStore: () => ({
    activeModal: 'source_detail',
    modalData: source,
    closeModal: mocks.closeModal,
    addToast: mocks.addToast,
  }),
}));

vi.mock('../src/i18n/useTranslation', () => ({
  useTranslation: () => ({ language: mocks.language }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('SourceDetailModal', () => {
  it('renders every label in Vietnamese when the app language is vi', () => {
    mocks.language = 'vi';
    render(<SourceDetailModal />);

    expect(screen.getByText('Bằng chứng nguồn gốc')).toBeTruthy();
    expect(screen.getByText('Bài đăng gốc, chưa chỉnh sửa')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sao chép trích đoạn' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Đóng' })).toBeTruthy();
    expect(screen.queryByText('Original Source Evidence')).toBeNull();
    expect(screen.queryByText('Copy Excerpt')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Close' })).toBeNull();
  });

  it('renders every label in English when the app language is en, with no stray Vietnamese', () => {
    mocks.language = 'en';
    render(<SourceDetailModal />);

    expect(screen.getByText('Original Source Evidence')).toBeTruthy();
    expect(screen.getByText('Unedited Raw Source Post')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Copy Excerpt' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Close' })).toBeTruthy();
    expect(screen.queryByText('Bằng chứng nguồn gốc')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Đóng' })).toBeNull();
  });
});
