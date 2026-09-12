import assert from 'node:assert/strict';
import test from 'node:test';
import { sendConversationTurn } from '../src/chatSession.ts';

test('the first chat turn creates its conversation before posting the message', async () => {
  const originalFetch = globalThis.fetch;
  const requests: Request[] = [];
  globalThis.fetch = async (input, init) => {
    const request = new Request(input, init);
    requests.push(request);
    if (requests.length === 1) {
      return new Response(JSON.stringify({ id: 42, title: 'Ưu tiên hôm nay', createdAt: '', updatedAt: '', messages: [] }), { status: 200 });
    }
    return new Response(JSON.stringify({ conversationId: 42, messageId: 99, response: 'Đây là phản hồi đầu tiên.' }), { status: 200 });
  };

  try {
    const result = await sendConversationTurn({ conversationId: null, message: 'Ưu tiên hôm nay', token: 'mobile-token' });

    assert.equal(result.conversationId, 42);
    assert.equal(result.createdConversationId, 42);
    assert.equal(result.reply.messageId, 99);
    assert.equal(requests[0]?.url.endsWith('/api/v1/conversations'), true);
    assert.equal(requests[1]?.url.endsWith('/api/v1/conversations/42/messages'), true);
    assert.equal(await requests[0]?.text(), JSON.stringify({ title: 'Ưu tiên hôm nay' }));
    assert.equal(await requests[1]?.text(), JSON.stringify({ message: 'Ưu tiên hôm nay' }));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
