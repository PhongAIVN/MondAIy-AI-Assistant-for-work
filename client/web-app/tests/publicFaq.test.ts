import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { matchFaqEntry, type FaqEntry } from '../src/lib/publicFaq.ts';

const entries: FaqEntry[] = [
  {
    id: 'q1',
    question: 'Tổng quan hằng ngày là gì?',
    answer: 'Bản tổng quan hằng ngày là tóm tắt được tổng hợp tự động về các mốc công việc, hạn chót sắp tới và thông báo mới nhất.',
  },
  {
    id: 'q3',
    question: 'Tại sao mondaiy KHÔNG tự động tạo sự kiện trên Lịch?',
    answer: 'Để đảm bảo quyền kiểm soát tuyệt đối của người dùng, mondaiy không bao giờ tự ý thay đổi lịch, công việc hay gửi tin nhắn nếu chưa có sự xác nhận từ bạn.',
  },
];

describe('matchFaqEntry', () => {
  it('matches a question typed without exact wording, ignoring diacritics/case', () => {
    assert.equal(matchFaqEntry('tong quan hang ngay la gi vay', entries)?.id, 'q1');
  });

  it('matches on the original question wording', () => {
    assert.equal(matchFaqEntry('Tại sao mondaiy không tự động tạo sự kiện?', entries)?.id, 'q3');
  });

  it('returns null for a question sharing no meaningful words with any FAQ', () => {
    assert.equal(matchFaqEntry('xyzzy qwerty plugh', entries), null);
  });

  it('returns null for an empty or whitespace-only question', () => {
    assert.equal(matchFaqEntry('   ', entries), null);
  });
});
