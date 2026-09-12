// @vitest-environment jsdom
//
// Tầng state cũng phải giữ trần nguồn, không chỉ tầng UI: mọi đường vào
// toggleSource (bàn phím, command palette, khôi phục state) đều đi qua đây.

import { afterEach, describe, expect, it } from 'vitest';

import { usePipelineRunStore } from '../src/stores/usePipelineRunStore';
import { DEFAULT_RUN_LIMITS } from '../src/types/pipeline';

const reset = () =>
  usePipelineRunStore.setState({ selectedSources: [], limits: DEFAULT_RUN_LIMITS, error: null });

describe('usePipelineRunStore.toggleSource', () => {
  afterEach(reset);

  it('không cho chọn quá hạn mức và nói rõ lý do', () => {
    usePipelineRunStore.setState({
      limits: { ...DEFAULT_RUN_LIMITS, maxSyncSources: 2 },
      selectedSources: [
        { connectionId: 1, sourceId: 'a' },
        { connectionId: 1, sourceId: 'b' },
      ],
    });

    usePipelineRunStore.getState().toggleSource({ connectionId: 1, sourceId: 'c' });

    const state = usePipelineRunStore.getState();
    expect(state.selectedSources).toHaveLength(2);
    expect(state.error).toContain('2');
  });

  it('bỏ tick vẫn chạy được khi danh sách đang vượt hạn mức', () => {
    // Hạ hạn mức sau khi người dùng đã chọn nhiều nguồn không được khoá cứng
    // danh sách — nếu không họ không còn cách nào Sync lại được.
    usePipelineRunStore.setState({
      limits: { ...DEFAULT_RUN_LIMITS, maxSyncSources: 1 },
      selectedSources: [
        { connectionId: 1, sourceId: 'a' },
        { connectionId: 1, sourceId: 'b' },
      ],
    });

    usePipelineRunStore.getState().toggleSource({ connectionId: 1, sourceId: 'a' });

    expect(usePipelineRunStore.getState().selectedSources).toEqual([{ connectionId: 1, sourceId: 'b' }]);
  });

  it('xoá thông báo lỗi cũ khi lại chọn được nguồn', () => {
    usePipelineRunStore.setState({
      limits: { ...DEFAULT_RUN_LIMITS, maxSyncSources: 2 },
      selectedSources: [{ connectionId: 1, sourceId: 'a' }],
      error: 'lỗi cũ còn sót',
    });

    usePipelineRunStore.getState().toggleSource({ connectionId: 1, sourceId: 'b' });

    expect(usePipelineRunStore.getState().error).toBeNull();
  });
});
