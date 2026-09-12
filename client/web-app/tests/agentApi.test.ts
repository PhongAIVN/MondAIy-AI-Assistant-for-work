import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { AgentStreamError, streamAgentRequest, streamConversationMessageRequest } from '../src/lib/agentStream.ts';

describe('streamAgent', () => {
  it('parses token and done SSE frames split across chunks', async () => {
    const originalFetch = globalThis.fetch;
    const encoder = new TextEncoder();
    const frames = [
      'event: progress\ndata: {"phase":"thinking"}\n\n',
      'event: progress\ndata: {"phase":"calling","tool":"calendar_search_events"}\n\n',
      'event: progress\ndata: {"phase":"observing","tool":"calendar_search_events"}\n\n',
      'event: progress\ndata: {"phase":"responding"}\n\n',
      'event: token\ndata: {"delta":"Xin "}\n\n',
      'event: token\ndata: {"delta":"chào"}\n\n',
      'event: done\ndata: {"response":"Xin chào","analysis":"","messageId":17,"groundingStatus":"abstain","programQuestionHandoffEligible":true,"sources":[{"tool":"program_schedule","title":"Workshop AI","url":"https://example.test/event/1","occurred_at":"2026-08-11T20:00:00+07:00"}],"productivityAction":{"status":"pending_approval","kind":"todo","message":"Chờ duyệt"},"taskDrafts":[{"id":7,"title":"Mentor Duty","dueAt":"2026-08-11T20:00:00+07:00","allDay":false,"status":"proposed","calendarWriteReady":true,"calendarEventId":null}],"taskBacklogCount":4,"taskSuggestions":[{"title":"Nộp báo cáo","detail":"Gửi PDF","dueAt":null,"allDay":false,"source":"Gmail"}]}\n\n',
    ].join('');

    globalThis.fetch = async () => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode(frames.slice(0, 17)));
          controller.enqueue(encoder.encode(frames.slice(17)));
          controller.close();
        },
      });
      return new Response(body, { status: 200 });
    };

    try {
      const tokens: string[] = [];
      const progress: string[] = [];
      let done = '';
      let doneMessageId: number | undefined;
      let actionStatus = '';
      let draftTitle = '';
      let taskBacklogCount = 0;
      let suggestionTitle = '';
      let groundingStatus = '';
      let handoffEligible = false;
      let sourceUrl = '';
      await streamAgentRequest('', 'hello', 'token', {
        onProgress: (event) => progress.push(`${event.phase}:${event.tool || ''}`),
        onToken: (delta) => tokens.push(delta),
        onDone: (reply) => {
          done = reply.response;
          doneMessageId = reply.messageId;
          actionStatus = reply.productivityAction?.status || '';
          draftTitle = reply.taskDrafts[0]?.title || '';
          taskBacklogCount = reply.taskBacklogCount || 0;
          suggestionTitle = reply.taskSuggestions[0]?.title || '';
          groundingStatus = reply.groundingStatus || '';
          handoffEligible = reply.programQuestionHandoffEligible === true;
          sourceUrl = reply.sources?.[0]?.url || '';
        },
      });
      assert.deepEqual(progress, [
        'thinking:',
        'calling:calendar_search_events',
        'observing:calendar_search_events',
        'responding:',
      ]);
      assert.deepEqual(tokens, ['Xin ', 'chào']);
      assert.equal(done, 'Xin chào');
      assert.equal(doneMessageId, 17);
      assert.equal(actionStatus, 'pending_approval');
      assert.equal(draftTitle, 'Mentor Duty');
      assert.equal(taskBacklogCount, 4);
      assert.equal(suggestionTitle, 'Nộp báo cáo');
      assert.equal(groundingStatus, 'abstain');
      assert.equal(handoffEligible, true);
      assert.equal(sourceUrl, 'https://example.test/event/1');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('uses the persisted conversation streaming endpoint', async () => {
    const originalFetch = globalThis.fetch;
    let requestedUrl = '';
    let requestedBody = '';
    globalThis.fetch = async (input, init) => {
      requestedUrl = String(input);
      requestedBody = String(init?.body);
      return new Response('event: done\ndata: {"response":"Saved"}\n\n', { status: 200 });
    };

    try {
      await streamConversationMessageRequest('https://api.example', 42, 'Hello', 'token', {
        onToken: () => undefined,
      });
      assert.equal(requestedUrl, 'https://api.example/api/v1/conversations/42/messages/stream');
      assert.equal(requestedBody, '{"message":"Hello"}');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('preserves the backend quota message on a failed stream request', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(
      JSON.stringify({ detail: 'Bạn đã dùng hết 10 câu hỏi AI hôm nay.' }),
      { status: 429, headers: { 'Content-Type': 'application/json' } },
    );

    try {
      await assert.rejects(
        streamAgentRequest('', 'question 11', 'token', { onToken: () => undefined }),
        (error: unknown) => (
          error instanceof AgentStreamError
          && error.status === 429
          && error.message.includes('dùng hết 10 câu hỏi')
        ),
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
