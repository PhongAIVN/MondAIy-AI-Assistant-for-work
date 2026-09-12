import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { ApiConnectionError, apiUrl, DEFAULT_API_URL, deleteAccount, exchangeAppleIdentityToken, exchangeGoogleLoginCode, getTasks, googleLoginUrl, listCalendarEvents, listMeetingNotes, request, uploadTaskImportFiles } from '../src/api/client.ts';

describe('mobile API endpoint construction', () => {
  it('uses production API by default and does not duplicate slashes', () => {
    assert.equal(apiUrl('/api/v1/chat'), `${DEFAULT_API_URL}/api/v1/chat`);
    assert.equal(apiUrl('/api/v1/tasks', 'https://example.test/'), 'https://example.test/api/v1/tasks');
  });

  it('reads the backend task envelope and sends the bearer token', async () => {
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(JSON.stringify({ tasks: [{ id: 7, title: 'Review brief', detail: 'Today', status: 'proposed' }] }), { status: 200 });
    };
    try {
      const tasks = await getTasks('mobile-token');
      assert.equal(tasks[0]?.id, 7);
      assert.equal(request?.headers.get('Authorization'), 'Bearer mobile-token');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('fails a stalled request with a retryable connection error', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (_input, init) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
    });
    try {
      await assert.rejects(
        request('/api/v1/health', {}, undefined, 5),
        (error: unknown) => error instanceof ApiConnectionError && /thử lại/i.test(error.message),
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('uses the backend-owned OAuth start and exchanges only the returned one-time code', async () => {
    assert.equal(
      googleLoginUrl('mondaiy://auth/callback'),
      `${DEFAULT_API_URL}/api/v1/auth/google/login?extRedirectUri=mondaiy%3A%2F%2Fauth%2Fcallback`,
    );
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(JSON.stringify({ accessToken: 'access', refreshToken: 'refresh' }), { status: 200 });
    };
    try {
      const tokens = await exchangeGoogleLoginCode('single-use-code');
      assert.equal(tokens.accessToken, 'access');
      assert.equal(request?.url, `${DEFAULT_API_URL}/api/v1/auth/google/session`);
      assert.equal(await request?.text(), JSON.stringify({ code: 'single-use-code' }));
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('exchanges the native Apple identity token and authorization code only with the P-004 backend', async () => {
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(JSON.stringify({ accessToken: 'access', refreshToken: 'refresh' }), { status: 200 });
    };
    try {
      await exchangeAppleIdentityToken('apple-identity-token', 'Apple User', 'apple-authorization-code');
      assert.equal(request?.url, `${DEFAULT_API_URL}/api/v1/auth/apple/session`);
      assert.equal(await request?.text(), JSON.stringify({ identityToken: 'apple-identity-token', displayName: 'Apple User', authorizationCode: 'apple-authorization-code' }));
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('loads the requested calendar range with the signed-in user token', async () => {
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(JSON.stringify({ events: [] }), { status: 200 });
    };
    try {
      const events = await listCalendarEvents('2026-08-16T00:00:00.000Z', '2026-08-23T00:00:00.000Z', 'mobile-token');
      assert.deepEqual(events.events, []);
      assert.equal(request?.url, `${DEFAULT_API_URL}/api/v1/calendar/events?timeFrom=2026-08-16T00%3A00%3A00.000Z&timeTo=2026-08-23T00%3A00%3A00.000Z`);
      assert.equal(request?.headers.get('Authorization'), 'Bearer mobile-token');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('loads Meeting Notes from the same authenticated backend as the web app', async () => {
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(JSON.stringify({ meetings: [] }), { status: 200 });
    };
    try {
      assert.deepEqual((await listMeetingNotes('mobile-token')).meetings, []);
      assert.equal(request?.url, `${DEFAULT_API_URL}/api/v1/meeting-notes`);
      assert.equal(request?.headers.get('Authorization'), 'Bearer mobile-token');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('deletes the signed-in account through the backend confirmation endpoint', async () => {
    const originalFetch = globalThis.fetch;
    let request: Request | undefined;
    globalThis.fetch = async (input, init) => {
      request = new Request(input, init);
      return new Response(null, { status: 204 });
    };
    try {
      await deleteAccount('current-password', 'mobile-token');
      assert.equal(request?.url, `${DEFAULT_API_URL}/api/v1/auth/me`);
      assert.equal(request?.method, 'DELETE');
      assert.equal(request?.headers.get('Authorization'), 'Bearer mobile-token');
      assert.equal(await request?.text(), JSON.stringify({ password: 'current-password' }));
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('uploads shared office files as multipart with the signed-in user token', async () => {
    const originalFetch = globalThis.fetch;
    let init: RequestInit | undefined;
    let url = '';
    globalThis.fetch = async (input, next) => {
      url = String(input);
      init = next;
      return new Response(JSON.stringify({ fileNames: ['ke-hoach.xlsx'], timezone: 'Asia/Ho_Chi_Minh', proposals: [], agentResponse: '', agentAnalysis: '', agentWarning: null, searchedName: '', needsNameQuery: false, suggestedNames: [] }), { status: 200 });
    };
    try {
      await uploadTaskImportFiles([{ uri: 'file:///tmp/ke-hoach.xlsx', name: 'ke-hoach.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', size: 42 }], 'mobile-token', 'Nguyễn An');
      assert.equal(url, `${DEFAULT_API_URL}/api/v1/excel/task-proposals`);
      assert.equal((init?.headers as Record<string, string>)?.Authorization, 'Bearer mobile-token');
      assert.equal((init?.headers as Record<string, string>)?.['Content-Type'], undefined);
      assert.ok(init?.body instanceof FormData);
      assert.equal((init?.body as FormData).getAll('files').length, 1);
      assert.equal((init?.body as FormData).get('search_name'), 'Nguyễn An');
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
