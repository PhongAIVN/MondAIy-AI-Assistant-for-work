// Hợp đồng của phần quyết định trong service worker khi có thông báo đẩy.
//
// Ba nhóm điều kiện:
//   parse    — payload hỏng vẫn phải ra một thông báo thật, không được im lặng
//   url      — bấm vào luôn mở được một thứ gì đó, và không chạy URL lạ giao thức
//   click    — tab Mondaiy đang mở thì kéo lên, liên kết ngoài thì mở tab mới

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  DEFAULT_PUSH_TITLE,
  buildNotificationOptions,
  parsePushPayload,
  planNotificationClick,
  resolveNotificationUrl,
} from '../src/lib/pushNotification.ts';

const ORIGIN = 'https://app.mondaiy.test';

describe('parsePushPayload', () => {
  it('đọc đúng payload backend gửi', () => {
    const payload = parsePushPayload(
      JSON.stringify({ title: 'Nhắc việc', body: '• Nộp báo cáo', tag: 'batch-7', url: 'https://mail.test/1' }),
    );

    assert.deepEqual(payload, {
      title: 'Nhắc việc',
      body: '• Nộp báo cáo',
      tag: 'batch-7',
      url: 'https://mail.test/1',
    });
  });

  it('không có dữ liệu thì vẫn ra được một thông báo có tiêu đề', () => {
    // Web Push đăng ký userVisibleOnly: không hiện gì là bị trình duyệt thay
    // bằng thông báo rác của nó, rồi thu hồi quyền đẩy của tên miền.
    assert.equal(parsePushPayload(null).title, DEFAULT_PUSH_TITLE);
    assert.equal(parsePushPayload('').title, DEFAULT_PUSH_TITLE);
  });

  it('dữ liệu không phải JSON thì giữ nguyên làm phần thân thay vì nuốt mất', () => {
    const payload = parsePushPayload('máy chủ gửi chuỗi thô');

    assert.equal(payload.title, DEFAULT_PUSH_TITLE);
    assert.equal(payload.body, 'máy chủ gửi chuỗi thô');
  });

  it('bỏ qua trường sai kiểu thay vì để nó chảy vào giao diện', () => {
    const payload = parsePushPayload(JSON.stringify({ title: 42, body: null, tag: '', url: 7 }));

    assert.equal(payload.title, DEFAULT_PUSH_TITLE);
    assert.equal(payload.body, '');
    assert.ok(payload.tag);
    assert.equal(payload.url, null);
  });
});

describe('buildNotificationOptions', () => {
  it('dùng bundle key làm tag để lần giao lại thay thế thông báo cũ', () => {
    const options = buildNotificationOptions({ title: 't', body: 'b', tag: 'batch-9', url: null });

    assert.equal(options.tag, 'batch-9');
    assert.equal(options.body, 'b');
  });

  it('mang liên kết theo trong data vì lúc bấm không còn payload gốc', () => {
    const options = buildNotificationOptions({ title: 't', body: '', tag: 'x', url: 'https://mail.test/9' });

    assert.deepEqual(options.data, { url: 'https://mail.test/9' });
  });
});

describe('resolveNotificationUrl', () => {
  it('giữ nguyên liên kết bằng chứng ở nguồn ngoài', () => {
    assert.equal(
      resolveNotificationUrl('https://mail.google.com/mail/u/0/#inbox/1', ORIGIN),
      'https://mail.google.com/mail/u/0/#inbox/1',
    );
  });

  it('quy đường dẫn nội bộ về URL tuyệt đối', () => {
    assert.equal(resolveNotificationUrl('/tasks/12', ORIGIN), `${ORIGIN}/tasks/12`);
  });

  it('không có liên kết thì mở trang việc cần làm chứ không mở suông', () => {
    assert.equal(resolveNotificationUrl(null, ORIGIN), `${ORIGIN}/tasks`);
    assert.equal(resolveNotificationUrl('', ORIGIN), `${ORIGIN}/tasks`);
  });

  it('từ chối URL khác giao thức http/https', () => {
    // deep_link đến từ dữ liệu nguồn; một URL đã đi qua tay người khác không
    // được phép tự chạy trong ngữ cảnh của app.
    assert.equal(resolveNotificationUrl('javascript:alert(1)', ORIGIN), `${ORIGIN}/tasks`);
    assert.equal(resolveNotificationUrl('data:text/html,<script>x</script>', ORIGIN), `${ORIGIN}/tasks`);
  });
});

describe('planNotificationClick', () => {
  it('kéo tab Mondaiy đang mở lên và điều hướng tới đúng trang', () => {
    const plan = planNotificationClick(`${ORIGIN}/tasks/5`, [`${ORIGIN}/briefing`], ORIGIN);

    assert.deepEqual(plan, { action: 'focus', clientIndex: 0, navigateTo: `${ORIGIN}/tasks/5` });
  });

  it('không điều hướng lại khi tab đang đứng đúng trang đó', () => {
    // Tải lại đúng trang người dùng đang làm dở là làm mất thao tác của họ.
    const plan = planNotificationClick(`${ORIGIN}/tasks`, [`${ORIGIN}/tasks`], ORIGIN);

    assert.deepEqual(plan, { action: 'focus', clientIndex: 0, navigateTo: null });
  });

  it('chưa có tab nào thì mở tab mới', () => {
    const plan = planNotificationClick(`${ORIGIN}/tasks`, [], ORIGIN);

    assert.deepEqual(plan, { action: 'open', url: `${ORIGIN}/tasks` });
  });

  it('liên kết ngoài luôn mở tab mới, không chiếm tab app đang mở', () => {
    const plan = planNotificationClick('https://mail.google.com/x', [`${ORIGIN}/tasks`], ORIGIN);

    assert.deepEqual(plan, { action: 'open', url: 'https://mail.google.com/x' });
  });

  it('bỏ qua tab khác gốc — đó không phải cửa sổ Mondaiy', () => {
    const plan = planNotificationClick(`${ORIGIN}/tasks`, ['https://example.test/'], ORIGIN);

    assert.deepEqual(plan, { action: 'open', url: `${ORIGIN}/tasks` });
  });
});
